# collabeauty-brand 통합 가이드

TikTok Analyzer를 collabeauty-brand와 통합하는 완전한 가이드입니다.

## 🏗️ 배포된 서비스 정보

### TikTok Analyzer (Private)
- **URL**: `https://tiktok-analyzer-475342403853.asia-northeast3.run.app`
- **인증**: OIDC (Google Cloud 서비스 계정 필요)
- **접근**: Private (프록시를 통해서만)

### TikTok Analyzer Proxy (Public with Token)
- **URL**: `https://tiktok-analyzer-proxy-475342403853.asia-northeast3.run.app`
- **인증**: Bearer Token (`APP_TOKEN`)
- **접근**: Public (토큰 검증 후)

## 🔧 collabeauty-brand 설정

### 1. 환경 변수 설정

`.env.local` 파일에 추가:

```bash
# 프록시 서비스 설정 (권장)
PROXY_URL=https://tiktok-analyzer-proxy-475342403853.asia-northeast3.run.app
PROXY_TOKEN=Gm1TcHe6+4vqZD68y+/XxU72ldC75mGnVqo8TFQL9c0=

# 직접 접근 설정 (대안)
ANALYZER_URL=https://tiktok-analyzer-475342403853.asia-northeast3.run.app
ANALYZER_AUDIENCE=https://tiktok-analyzer-475342403853.asia-northeast3.run.app
```

### 2. 서비스 계정 권한

collabeauty-brand가 사용하는 서비스 계정에 권한이 부여되어 있습니다:
- `collabeauty-brand-caller@collabeauty-tiktokanalyzer.iam.gserviceaccount.com`

## 🚀 API 사용 방법

### 프록시를 통한 호출 (권장)

```javascript
// 분석 요청
const analyzeResponse = await fetch(`${process.env.PROXY_URL}/analyze`, {
      method: 'POST',
  headers: {
    'Authorization': `Bearer ${process.env.PROXY_TOKEN}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    url: 'https://www.tiktok.com/@username/video/123456',
    comments: true
  })
});

const result = await analyzeResponse.json();
console.log(result);
// {
//   "status": "ok",
//   "gcs_prefix": "gs://collabeauty-tiktokanalyzer-tiktok-runs/runs/...",
//   "files": ["gs://...metadata.json", "gs://...video.mp4", ...]
// }
```

```javascript
// 다운로드 요청
const mp4File = result.files.find(file => file.endsWith('.mp4'));
const downloadResponse = await fetch(
  `${process.env.PROXY_URL}/proxy/download?gcs=${encodeURIComponent(mp4File)}&filename=video.mp4`,
  {
    headers: {
      'Authorization': `Bearer ${process.env.PROXY_TOKEN}`
    }
  }
);

// 스트리밍 다운로드
downloadResponse.body.pipe(res); // Express에서
```

### 직접 OIDC 호출 (대안)

```javascript
import { GoogleAuth } from 'google-auth-library';

const auth = new GoogleAuth();
const client = await auth.getIdTokenClient(process.env.ANALYZER_AUDIENCE);

const response = await client.request({
  url: `${process.env.ANALYZER_URL}/analyze`,
  method: 'POST',
  data: {
    url: 'https://www.tiktok.com/@username/video/123456',
    comments: true
  }
});
```

## 🔍 엔드포인트 상세

### `/analyze` (분석)

**요청:**
```bash
POST /analyze
Authorization: Bearer <PROXY_TOKEN>
Content-Type: application/json

{
  "url": "https://www.tiktok.com/@username/video/123456",
  "comments": true
}
```

**응답:**
```json
{
  "status": "ok",
  "gcs_prefix": "gs://collabeauty-tiktokanalyzer-tiktok-runs/runs/run-20250907-1234/",
  "files": [
    "gs://collabeauty-tiktokanalyzer-tiktok-runs/runs/run-20250907-1234/metadata.json",
    "gs://collabeauty-tiktokanalyzer-tiktok-runs/runs/run-20250907-1234/video.mp4",
    "gs://collabeauty-tiktokanalyzer-tiktok-runs/runs/run-20250907-1234/comments.json"
  ]
}
```

### `/proxy/download` (다운로드)

**요청:**
```bash
GET /proxy/download?gcs=gs://bucket/path/file.mp4&filename=video.mp4
Authorization: Bearer <PROXY_TOKEN>
```

**응답:**
```
Content-Type: video/mp4
Content-Disposition: attachment; filename="video.mp4"
Content-Length: 12345678

<binary_stream>
```

## 🔒 보안 고려사항

### 1. 토큰 보안
- `PROXY_TOKEN`은 안전하게 보관하세요
- 환경 변수로만 관리하고 코드에 하드코딩하지 마세요
- 주기적으로 토큰을 교체하는 것을 권장합니다

### 2. 접근 제어
- 프록시는 토큰 검증 후에만 요청을 전달합니다
- Analyzer 서비스는 완전히 private하게 유지됩니다
- OIDC를 통한 추가 인증 레이어가 있습니다

### 3. 네트워크 보안
- 모든 통신은 HTTPS로 암호화됩니다
- Organization 정책에 의해 추가 보안이 적용됩니다

## 🧪 테스트 방법

### 로컬 테스트

```bash
# 환경 변수 설정
export PROXY_URL='https://tiktok-analyzer-proxy-475342403853.asia-northeast3.run.app'
export PROXY_TOKEN='Gm1TcHe6+4vqZD68y+/XxU72ldC75mGnVqo8TFQL9c0='

# 분석 테스트
curl -H "Authorization: Bearer $PROXY_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"url":"https://www.tiktok.com/@tiktok/video/7016876107492569350","comments":false}' \
     "$PROXY_URL/analyze"

# 다운로드 테스트 (분석 결과의 GCS URL 사용)
curl -H "Authorization: Bearer $PROXY_TOKEN" \
     "$PROXY_URL/proxy/download?gcs=gs://bucket/path/file.mp4&filename=test.mp4" \
     -o test.mp4
```

### collabeauty-brand에서 테스트

1. **개발 서버 재시작**: 환경 변수 반영을 위해
2. **결과분석 탭 접근**: 기존 캠페인의 분석 결과 확인
3. **동영상 보기 클릭**: 모달 창 열기
4. **"동영상 원본 다운로드" 클릭**: 다운로드 기능 테스트

## 🚨 트러블슈팅

### 401 Unauthorized 에러
- `PROXY_TOKEN` 값이 정확한지 확인
- 환경 변수가 올바르게 로드되었는지 확인
- 서비스 계정 권한이 부여되었는지 확인

### 404 Not Found 에러
- 엔드포인트 URL이 올바른지 확인
  - ✅ `/analyze` (O)
  - ❌ `/proxy/analyze` (X)
- 서비스가 정상 배포되었는지 확인

### 500 Internal Server Error
- 프록시 서비스 로그 확인
- TikTok URL이 유효한지 확인
- GCS 권한이 올바른지 확인

### 다운로드 실패
- GCS URL이 올바른지 확인
- 파일이 실제로 존재하는지 확인
- 네트워크 연결 상태 확인

## 📊 모니터링

### 로그 확인

```bash
# 프록시 서비스 로그
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=tiktok-analyzer-proxy" --limit=50

# Analyzer 서비스 로그
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=tiktok-analyzer" --limit=50
```

### 성능 메트릭
- 평균 응답 시간: ~30-60초 (분석)
- 다운로드 속도: 네트워크 대역폭에 따라
- 최대 파일 크기: 제한 없음 (스트리밍)

## 🔄 업데이트 방법

### 프록시 서비스 업데이트

```bash
# 새 버전 빌드
cd proxy
gcloud builds submit --tag asia-northeast3-docker.pkg.dev/collabeauty-tiktokanalyzer/tiktokanalyzer/proxy:0.3.0

# 서비스 업데이트
gcloud run deploy tiktok-analyzer-proxy \
  --image asia-northeast3-docker.pkg.dev/collabeauty-tiktokanalyzer/tiktokanalyzer/proxy:0.3.0 \
  --region asia-northeast3
```

### Analyzer 서비스 업데이트

```bash
# 새 버전 빌드
gcloud builds submit --tag asia-northeast3-docker.pkg.dev/collabeauty-tiktokanalyzer/tiktokanalyzer/api:0.2.0

# 서비스 업데이트
gcloud run deploy tiktok-analyzer \
  --image asia-northeast3-docker.pkg.dev/collabeauty-tiktokanalyzer/tiktokanalyzer/api:0.2.0 \
  --region asia-northeast3
```

## 📞 지원

문제가 발생하면 다음을 확인하세요:

1. **환경 변수**: 올바른 URL과 토큰 설정
2. **권한**: 서비스 계정 IAM 권한
3. **네트워크**: HTTPS 연결 상태
4. **로그**: Cloud Run 서비스 로그

---

**마지막 업데이트**: 2025-09-07  
**버전**: Proxy v0.2.0, Analyzer v0.1.0