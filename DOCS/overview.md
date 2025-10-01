# 개요 및 권장 아키텍처

목표: collabeauty-brand에서 TikTok URL을 받아 메타데이터를 수집하고, 필요 시 댓글을 스크랩하고, 동영상을 다운로드합니다. 전사(Whisper)는 비활성화합니다.

권장 배포 타깃: Google Cloud Run
- 이유: 컨테이너 기반, 무서버 운영, 오토스케일, 쉬운 권한/네트워킹 연계
- 저장소: 산출물(`runs/...`)은 Cloud Storage 버킷에 업로드하고 API는 업로드된 프리픽스만 반환
- 인증: collabeauty-brand 백엔드→Cloud Run 서비스 간 OIDC 서비스-투-서비스 권장

구성 요소
- Cloud Run 서비스: FastAPI로 `/analyze` API 제공
- Cloud Storage 버킷: `gs://<PROJECT_ID>-tiktok-runs` 예시
- Service Account: Cloud Run 실행용(버킷 쓰기 권한)

흐름
1) 클라이언트(collabeauty-brand)가 Cloud Run `/analyze` 호출(POST)
2) 서비스가 내부적으로 `src.pipeline.analyze_url()` 실행(전사 비활성화)
3) 생성된 `runs/<...>/` 폴더를 GCS에 업로드
4) 응답으로 `gcs_prefix` 또는 파일 목록 반환

비동기 확장(선택)
- 대기 시간이 길거나 트래픽이 많다면: HTTP 수신→Pub/Sub 큐→Cloud Run Jobs/Worker→GCS 저장→상태 조회 API
