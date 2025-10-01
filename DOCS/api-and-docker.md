# API 래퍼 작성 및 Docker 구성

이 단계에서는 FastAPI로 간단한 엔드포인트(`/analyze`)를 만들고, 컨테이너(Dockerfile)를 준비합니다. 전사는 기본 비활성화합니다.

1) FastAPI 앱 생성 예시(`app/main.py`)
아래 코드를 새 파일 `app/main.py`로 추가합니다. 작업 후 `uvicorn`으로 로컬 실행 테스트가 가능합니다.

```
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import os
import time
import glob
from google.cloud import storage

try:
    from src.pipeline import analyze_url
except ModuleNotFoundError:
    from pipeline import analyze_url  # type: ignore

GCS_BUCKET = os.getenv("GCS_BUCKET", "")

app = FastAPI(title="TikTok Analyzer API", version="1.0.0")

class AnalyzeRequest(BaseModel):
    url: str
    comments: bool = True
    # 전사 기능은 비활성화(무시)

def _latest_run_dir(base: str = None) -> Optional[str]:
    base = base or os.path.join(os.getcwd(), "runs")
    if not os.path.isdir(base):
        return None
    cands = [d for d in glob.glob(os.path.join(base, "*")) if os.path.isdir(d)]
    if not cands:
        return None
    return max(cands, key=os.path.getmtime)

def _upload_dir_to_gcs(local_dir: str, bucket_name: str, prefix: str) -> List[str]:
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    uploaded = []
    for root, _, files in os.walk(local_dir):
        for f in files:
            lp = os.path.join(root, f)
            rel = os.path.relpath(lp, local_dir)
            blob = bucket.blob(f"{prefix}/{rel}")
            blob.upload_from_filename(lp)
            uploaded.append(f"gs://{bucket_name}/{prefix}/{rel}")
    return uploaded

@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    try:
        analyze_url(
            req.url,
            do_comments=req.comments,
            transcribe=False,  # 전사 비활성화
            meta_fast=True,
            skip_metadata=False,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pipeline failed: {e}")

    run_dir = _latest_run_dir()
    if not run_dir:
        raise HTTPException(status_code=500, detail="run directory not found")

    if not GCS_BUCKET:
        # 로컬/개발 모드: GCS 미업로드, 로컬 경로만 반환
        return {"status": "ok", "local_run_dir": run_dir}

    # GCS 업로드
    stamp = int(time.time())
    prefix = f"runs/{os.path.basename(run_dir)}-{stamp}"
    try:
        uploaded = _upload_dir_to_gcs(run_dir, GCS_BUCKET, prefix)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"gcs upload failed: {e}")

    return {
        "status": "ok",
        "gcs_prefix": f"gs://{GCS_BUCKET}/{prefix}/",
        "files": uploaded,
    }
```

로컬 실행 테스트
```
uvicorn app.main:app --host 0.0.0.0 --port 8080
# POST 요청 예시
curl -X POST http://127.0.0.1:8080/analyze \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.tiktok.com/@USER/video/VIDEO_ID","comments":true}'
```

2) Dockerfile 작성 예시(Whisper 없음, 경량)
프로젝트 루트에 `Dockerfile`을 만들고 아래 내용을 사용합니다.

```
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install fastapi uvicorn[standard] google-cloud-storage

COPY . .

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

주의
- `src.pipeline.analyze_url`는 현재 run 디렉터리 경로를 반환하지 않으므로, 위 예시처럼 최신 디렉터리를 추정하는 보조 함수를 사용합니다. 필요 시 `analyze_url`이 run 경로를 반환하도록 개선해도 좋습니다.
- Whisper/PyTorch 미설치. 전사 관련 인자는 무시됩니다.
