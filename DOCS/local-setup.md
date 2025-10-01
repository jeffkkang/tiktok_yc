# 로컬 환경 준비 및 테스트 (Whisper 비활성화)

전제
- Python 3.9+
- FFmpeg 설치(오디오 추출/yt-dlp에 필요)
  - macOS: `brew install ffmpeg`
  - Linux: `apt-get install -y ffmpeg`
  - Windows: choco/scoop 또는 공식 빌드 설치

의존성 설치
1) 가상환경 생성/활성화 후 필수 패키지 설치
```
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
python -m pip install -U pip setuptools wheel
pip install -r requirements.txt
```
2) (선택) 댓글 서드파티 스크래퍼
```
pip install -r thirdparty/tiktok-comment-scrapper/requirements.txt
```

빠른 실행 테스트
- 기본 실행(전사 비활성화 상태):
```
python -m src.default_runner "https://www.tiktok.com/@USER/video/VIDEO_ID"
```
- 파이프라인 옵션 실행(전사 없이):
```
python -m src.pipeline --url "https://www.tiktok.com/@USER/video/VIDEO_ID" --comments
```

참고
- 전사 기능을 쓰지 않으므로 Whisper/PyTorch 설치는 필요 없습니다.
- 산출물은 `runs/<uploader>_<videoId>_<timestamp>/` 하위에 저장됩니다.
