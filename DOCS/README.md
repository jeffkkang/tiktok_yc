# CollaBeauty TikTok Analyzer 배포 가이드 (Whisper 비활성화)

이 문서는 collabeauty-brand에서 본 레포의 기능(메타데이터/댓글/다운로드)을 Google Cloud에 올려 재사용하기 위한 단계별 안내입니다. 전사(Whisper)는 기본 비활성화 상태로 진행합니다.

구성 파일:
- `DOCS/overview.md`: 아키텍처 개요와 선택지
- `DOCS/local-setup.md`: 로컬 환경 준비와 테스트
- `DOCS/api-and-docker.md`: FastAPI 래퍼 작성 및 Dockerfile
- `DOCS/deploy-cloud-run.md`: Cloud Run 배포 및 권한/연동
- `DOCS/troubleshooting.md`: 운영 팁과 문제 해결
 - `DOCS/AGENTS.md`: 에이전트 온보딩/이용 가이드(코드 구조, API 스펙)

권장 흐름:
1) overview를 읽고 Cloud Run 아키텍처를 확정
2) local-setup에 따라 의존성 설치 및 로컬 테스트
3) api-and-docker의 예시 코드로 API 래퍼와 Dockerfile 추가
4) deploy-cloud-run 순서대로 빌드/배포/권한 설정
5) collabeauty-brand에서 서비스 계정 OIDC로 호출 연동
