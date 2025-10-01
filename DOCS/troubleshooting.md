# 운영 팁 및 문제 해결

일반 이슈
- yt-dlp 실패: TikTok 변경/차단 이슈일 수 있음 → `pip install -U yt-dlp`로 최신화, 재시도.
- ffmpeg 미설치: 오디오 추출/포맷 변환 실패 → 컨테이너/로컬에 ffmpeg 설치 확인.
- 네트워크 제한: Cloud Run egress 제한 시 다운로드 실패 가능 → VPC egress/서프넷 구성 검토.

성능/비용
- 전사 비활성화로 CPU/메모리 요구사항 낮음(1 vCPU, 1–2GiB로 시작).
- 다운로드 시간 상한은 영상 길이/네트워크에 따라 크게 변동 → 타임아웃을 여유 있게 설정.

로그/디버깅
- Cloud Run 로그: `gcloud logs tail --service tiktok-analyzer --region <REGION>`
- 업로드 확인: `gsutil ls -r gs://<PROJECT_ID>-tiktok-runs/runs/**`

보강 아이디어
- 비동기 처리: HTTP → Pub/Sub → Worker로 대기 시간 분리, 상태 조회 API 추가.
- 재현성: `analyze_url()`이 run 디렉터리 경로를 반환하도록 개선(현재는 최신 디렉터리 추정 방식).
- 안정성: 실패 시 재시도(지수 백오프), yt-dlp 포맷/리트라이 옵션 추가.
