# TikTok Profile Scraper

TikTok 프로필 정보를 자동으로 수집하는 고급 스크래퍼입니다.

## 주요 기능

- 대량의 TikTok 프로필 정보 수집
- 이메일 주소 자동 추출
- 프록시 지원
- 병렬 처리로 빠른 수집
- 자동 재시도 및 에러 처리
- 쿠키 관리 시스템

## 설치 방법

1. 저장소 클론
```bash
git clone https://github.com/yourusername/tiktok-profile-scraper.git
cd tiktok-profile-scraper
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 의존성 패키지 설치
```bash
pip install -r requirements.txt
```

## 환경 변수 설정

`.env` 파일을 생성하고 다음 변수들을 설정하세요:

```env
DEBUG=False
LOG_LEVEL=INFO
COOKIES={"your":"cookies"}
CONCURRENT_WORKERS=5
REQUEST_DELAY_MIN=1.0
REQUEST_DELAY_MAX=3.0
MAX_RETRIES=3
BATCH_SIZE=100
```

## 사용 방법

1. 쿠키 설정
   - 브라우저에서 TikTok 로그인
   - 쿠키 추출 후 환경 변수에 설정

2. 수집할 사용자 목록 준비
   - `usernames.txt` 파일에 수집할 사용자명 작성
   - 한 줄에 하나의 사용자명

3. 스크래퍼 실행
```bash
python advanced_scraper.py
```

## Render 배포

1. Render 계정 생성
2. New Background Worker 생성
3. 환경 변수 설정
   - `COOKIES`: TikTok 쿠키
   - 기타 설정 변수들
4. 자동 배포 설정

## 주의사항

- TikTok의 이용약관을 준수하세요
- 과도한 요청은 IP 차단의 원인이 될 수 있습니다
- 수집된 정보는 개인정보 보호법을 준수하여 처리하세요

## 라이선스

MIT License

## 기여하기

1. Fork the Project
2. Create your Feature Branch
3. Commit your Changes
4. Push to the Branch
5. Open a Pull Request 