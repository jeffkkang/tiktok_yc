# Cloud Run 배포 및 연동 (단계별)

전제
- GCP 프로젝트 생성 및 결제 활성화
- `gcloud` CLI 설치 및 로그인: `gcloud auth login`
- 기본 프로젝트/리전 설정: `gcloud config set project <PROJECT_ID>`, `gcloud config set run/region <REGION>`

0) API 활성화
```
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
  cloudbuild.googleapis.com secretmanager.googleapis.com
```

1) Artifact Registry 리포지토리 생성
```
export PROJECT_ID=<YOUR_PROJECT>
export REGION=asia-northeast3
export REPO=tiktokanalyzer
export IMAGE=api

gcloud artifacts repositories create $REPO \
  --repository-format=docker \
  --location=$REGION \
  --description="TikTok analyzer"
```

2) 컨테이너 빌드/푸시(Cloud Build)
```
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE:0.1.0
```

3) 서비스 계정과 버킷 준비
```
gcloud iam service-accounts create tiktok-analyzer-sa \
  --display-name="tiktok-analyzer"

gcloud storage buckets create gs://$PROJECT_ID-tiktok-runs --location=$REGION

gcloud storage buckets add-iam-policy-binding gs://$PROJECT_ID-tiktok-runs \
  --member=serviceAccount:tiktok-analyzer-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/storage.objectAdmin
```

4) Cloud Run 배포
```
gcloud run deploy tiktok-analyzer \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPO/$IMAGE:0.1.0 \
  --region $REGION \
  --platform managed \
  --cpu 1 --memory 1Gi --timeout 900 --concurrency 1 \
  --max-instances 3 \
  --service-account tiktok-analyzer-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --set-env-vars GCS_BUCKET=$PROJECT_ID-tiktok-runs \
  --no-allow-unauthenticated
```

5) collabeauty-brand에서 호출 권한 부여
- collabeauty-brand 백엔드 서비스 계정이 있다면 Run Invoker 권한을 부여합니다.
```
export CALLER_SA=<COLLABEAUTY_BRAND_SA_NAME>
gcloud run services add-iam-policy-binding tiktok-analyzer \
  --member=serviceAccount:$CALLER_SA@$PROJECT_ID.iam.gserviceaccount.com \
  --role=roles/run.invoker \
  --region $REGION
```

6) collabeauty-brand에서 호출 (Node 예시)
```
import { GoogleAuth } from 'google-auth-library';

const url = 'https://tiktok-analyzer-XXXXXXXX-xx.a.run.app/analyze';
const targetAudience = url; // Cloud Run OIDC 대상

const auth = new GoogleAuth();
const client = await auth.getIdTokenClient(targetAudience);
const res = await client.request({
  url,
  method: 'POST',
  data: {
    url: 'https://www.tiktok.com/@USER/video/VIDEO_ID',
    comments: true
  }
});
console.log(res.data);
```

7) 응답 형식(예시)
```
{
  "status": "ok",
  "gcs_prefix": "gs://<PROJECT_ID>-tiktok-runs/runs/<run>-<ts>/",
  "files": ["gs://.../metadata.json", "gs://.../...mp4", ...]
}
```

권장 리소스/파라미터
- CPU/메모리: 전사 비활성화 기준 1 vCPU, 1–2GiB 메모리로 시작
- 타임아웃: 900s(15분) → `yt-dlp` 다운로드 여유 고려
- 동시성: 1(안정성), 상황에 따라 확장

보안
- 외부 공개를 피하려면 `--no-allow-unauthenticated` 유지 후 서비스 계정 OIDC로만 호출
- 필요 시 API Gateway/IAP 연동으로 범용 인증 계층 추가 가능
