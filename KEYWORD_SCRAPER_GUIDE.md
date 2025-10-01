# TikTok 키워드 검색 → 크리에이터 프로필 CSV Exporter

## 📋 개요

터미널에서 키워드를 입력하여 TikTok에서 관련 영상을 조회수 기준으로 수집하고, 각 크리에이터의 프로필 정보(이메일, 팔로워 등)를 추출하여 CSV로 저장하는 CLI 유틸리티입니다.

**핵심 특징:**
- ✅ 기존 `tiktok-profile-scraper` 코드 재사용
- ✅ 조회수 기준 자동 정렬
- ✅ 각 영상별 크리에이터 정보 + 영상 링크 추출
- ✅ 이메일 자동 추출 (프로필 설명, mailto 링크, 페이지 소스)
- ✅ CSV 형식 출력

---

## 🚀 빠른 시작

### 1. 기본 실행

```bash
python tiktok_keyword_scraper.py --keyword "K뷰티" --limit 50 --out kbeauty_creators.csv
```

### 2. 브라우저 모드 (캡챠 수동 해결용)

```bash
python tiktok_keyword_scraper.py --keyword "메이크업" --limit 30 --out makeup.csv --use-browser
```

### 3. 고급 옵션

```bash
python tiktok_keyword_scraper.py \
  --keyword "skincare routine" \
  --limit 200 \
  --out skincare.csv \
  --cookies-file tiktok-hashtag-scraper/cookies.json \
  --delay-min 1.0 \
  --delay-max 2.0
```

---

## 📝 CLI 옵션

| 옵션 | 단축키 | 설명 | 기본값 |
|------|--------|------|--------|
| `--keyword` | `-k` | 검색 키워드 (필수) | - |
| `--limit` | `-l` | 수집할 최대 비디오 수 | 100 |
| `--out` | `-o` | 출력 CSV 파일 경로 | `creators.csv` |
| `--cookies-file` | `-c` | 쿠키 JSON 파일 경로 | `tiktok-hashtag-scraper/cookies.json` |
| `--use-browser` | - | 브라우저 표시 (헤드리스 비활성화) | False |
| `--delay-min` | - | 최소 지연 시간 (초) | 0.5 |
| `--delay-max` | - | 최대 지연 시간 (초) | 1.5 |

---

## 📊 CSV 출력 형식

생성되는 CSV 파일의 컬럼:

| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| `keyword` | 검색 키워드 | "K뷰티" |
| `video_id` | TikTok 비디오 ID | "7123456789012345678" |
| `video_url` | 비디오 전체 URL | "https://www.tiktok.com/@user/video/..." |
| `creator_id` | 크리에이터 ID (현재는 username) | "beauty_guru" |
| `creator_username` | 크리에이터 유저네임 | "beauty_guru" |
| `creator_email` | 추출된 이메일 | "contact@example.com" |
| `follower_count` | 팔로워 수 (정규화된 숫자) | 1200000 |
| `source_api` | 데이터 소스 | "page_dom" |
| `extraction_method` | 추출 방법 | "profile_dom" |
| `scraped_at` | 수집 시간 (ISO 8601) | "2025-01-15T10:30:45" |
| `notes` | 에러/경고 메시지 | "" |

### CSV 예시

```csv
keyword,video_id,video_url,creator_id,creator_username,creator_email,follower_count,source_api,extraction_method,scraped_at,notes
K뷰티,7123456789,https://www.tiktok.com/@user1/video/7123456789,user1,user1,contact@user1.com,1200000,page_dom,profile_dom,2025-01-15T10:30:45,
메이크업,7234567890,https://www.tiktok.com/@user2/video/7234567890,user2,user2,,345000,page_dom,profile_dom,2025-01-15T10:31:02,
```

---

## 🔧 기술 구현 상세

### 1. 코드 재사용 전략

기존 `tiktok-profile-scraper/advanced_scraper.py`의 다음 요소들을 재사용:

- **`EmailExtractor` 클래스**: 이메일 추출 로직 (정규식, 난독화 형식 처리)
- **`parse_count()` 함수**: 팔로워 수 정규화 (1.2M → 1200000)
- **`CookieManager` 클래스**: 쿠키 로드 및 Selenium 형식 변환
- **Selenium 드라이버 설정 패턴**: 봇 감지 우회, User-Agent 설정

### 2. 검색 → 프로필 수집 플로우

```
1. 키워드 입력 (예: "K뷰티")
   ↓
2. TikTok 검색 페이지 접속
   https://www.tiktok.com/search/video?q=K%EB%B7%B0%ED%8B%B0
   ↓
3. 스크롤하며 비디오 목록 수집
   - CSS 선택자: div[data-e2e='search_top-item'], div[data-e2e='search-video-item']
   - 추출: video_id, video_url, creator_username, view_count
   ↓
4. 조회수 기준 내림차순 정렬
   ↓
5. 각 비디오의 크리에이터 프로필 조회
   - URL: https://www.tiktok.com/@{username}
   - 추출: follower_count, bio, emails
   ↓
6. CSV 행 생성 및 배치 저장 (10개마다)
   ↓
7. 완료
```

### 3. 이메일 추출 우선순위

1. **프로필 설명 (bio)**: `[data-e2e='user-bio']`
2. **mailto 링크**: `a[href*='mailto:']`
3. **페이지 소스**: 정규식으로 전체 HTML 스캔
4. **난독화 형식**: `user [at] domain [dot] com` → `user@domain.com`

### 4. 팔로워 수 정규화

```python
"1.2M" → 1200000
"345K" → 345000
"1,234" → 1234
"500"  → 500
```

---

## 🧪 테스트 키워드 샘플

Issue 티켓에서 제안된 6개 테스트 키워드:

```bash
# 1. 한글
python tiktok_keyword_scraper.py -k "K뷰티" -l 10 -o test_kbeauty.csv

# 2. 한글 (공백 포함)
python tiktok_keyword_scraper.py -k "메이크업 튜토리얼" -l 10 -o test_makeup_tutorial.csv

# 3. 영어
python tiktok_keyword_scraper.py -k "skincare routine" -l 10 -o test_skincare.csv

# 4. 영어
python tiktok_keyword_scraper.py -k "beauty haul" -l 10 -o test_beauty_haul.csv

# 5. 이모지 포함
python tiktok_keyword_scraper.py -k "makeup tutorial 💄✨" -l 10 -o test_emoji.csv

# 6. 혼합 (한글+영어+이모지)
python tiktok_keyword_scraper.py -k "korean beauty 한국 화장품 🇰🇷" -l 10 -o test_mixed.csv
```

---

## ⚠️ 주의사항 및 제한사항

### 1. 속도 제한 (Rate Limiting)

- **기본 지연**: 0.5~1.5초 (요청 간)
- **권장 설정**: `--delay-min 1.0 --delay-max 2.0` (대량 수집 시)
- **IP 차단 방지**: 프록시 사용 권장 (현재 미구현, 향후 추가 예정)

### 2. 캡챠 (CAPTCHA)

- TikTok이 봇 감지 시 캡챠 표시 가능
- **해결 방법**: `--use-browser` 옵션으로 브라우저 표시 후 수동 해결
- 캡챠 화면에서 Enter 대기 중 메시지 표시됨

### 3. 쿠키 유효성

- 쿠키 파일: `tiktok-hashtag-scraper/cookies.json`
- **유효 기간**: 현재 쿠키는 2025-11-13까지 유효 (`sid_guard` 기준)
- **갱신 방법**: 브라우저에서 TikTok 로그인 후 새 쿠키 추출

### 4. 이메일 발견율

- **현실적 기대치**: 30% 미만
- 대부분의 크리에이터는 프로필에 이메일을 공개하지 않음
- `creator_email` 컬럼이 빈칸일 경우 정상

### 5. 검색 결과 한계

- TikTok API는 페이지네이션에 제한이 있을 수 있음
- 목표 `--limit` 수에 도달하지 못할 수 있음 (스크롤 한계)
- **권장**: 키워드를 세분화하여 여러 번 실행

---

## 🔍 문제 해결 (Troubleshooting)

### 1. `ModuleNotFoundError: No module named 'webdriver_manager'`

```bash
pip install webdriver-manager
```

### 2. `쿠키 파일을 찾을 수 없습니다`

```bash
# 쿠키 파일 경로 확인
ls tiktok-hashtag-scraper/cookies.json

# 또는 절대 경로 지정
python tiktok_keyword_scraper.py -k "test" -c /절대/경로/cookies.json
```

### 3. `검색 결과가 없습니다`

- 키워드가 너무 특수하거나 결과가 없을 수 있음
- 다른 키워드로 재시도
- `--use-browser`로 실행하여 검색 결과 페이지 확인

### 4. 프로필 조회 실패 (`User not found`)

- 사용자가 계정을 삭제했거나 비공개 설정
- 로그에서 `notes` 컬럼에 에러 메시지 확인

### 5. Chrome 드라이버 오류

```bash
# ChromeDriver 재설치
pip uninstall selenium
pip install selenium==4.16.0
```

---

## 📈 성능 및 예상 소요 시간

| 비디오 수 | 예상 시간 | 비고 |
|-----------|-----------|------|
| 10개 | ~2분 | 테스트용 |
| 50개 | ~10분 | 소규모 수집 |
| 100개 | ~20분 | 권장 |
| 200개 | ~40분 | 대량 수집 (IP 차단 주의) |

**계산식**: 비디오당 평균 12초 (검색 5초 + 프로필 조회 5초 + 지연 2초)

---

## 🚧 향후 개선 계획

- [ ] 비동기 처리 (asyncio) - 성능 3~5배 향상
- [ ] 프록시 지원 (`--proxy-file` 옵션)
- [ ] 재시도 로직 개선 (지수 백오프)
- [ ] API 기반 검색 (Selenium 대신 HTTP 요청, 서명 필요)
- [ ] 진행 상황 바 (tqdm)
- [ ] JSON 출력 지원 (`--format json`)
- [ ] 중복 제거 옵션 (`--deduplicate`)
- [ ] 필터링 옵션 (팔로워 수 최소값 등)

---

## 📞 지원 및 문의

Issue 티켓에 명시된 대로, 다음을 참고:

- **Acceptance Criteria**: 90% 이상 프로필 수집 성공률
- **Email Hit Rate**: 30% (현실적 목표)
- **Performance**: 프로필당 <3초 (재시도 포함)

---

## 📜 라이선스 및 법적 고지

**⚠️  중요**: TikTok의 서비스 약관 및 robots.txt를 준수하세요.

- 개인정보 보호법 (GDPR, CCPA) 준수
- 수집된 이메일은 내부 보관 정책에 따라 관리
- 상업적 사용 시 법무팀과 합의 필요
- Rate limiting 준수 (IP 차단 방지)

---

## 🎯 요약

```bash
# 한 줄 실행 예시
python tiktok_keyword_scraper.py -k "K뷰티" -l 100 -o kbeauty_creators.csv

# 생성된 CSV 확인
head kbeauty_creators.csv
```

**출력 예시**:
```
keyword,video_id,video_url,creator_id,creator_username,creator_email,follower_count,source_api,extraction_method,scraped_at,notes
K뷰티,7123456789,https://www.tiktok.com/@user1/video/7123456789,user1,user1,contact@user1.com,1200000,page_dom,profile_dom,2025-01-15T10:30:45,
```

---

**Last Updated**: 2025-01-15
**Version**: 1.0.0
**Author**: Based on existing `tiktok-profile-scraper` codebase
