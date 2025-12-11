# TikTok Rate Limiting 가이드 🚦

## 개요

TikTok의 Rate Limiting을 우회하기 위한 **Cookie Rotation** + **Sliding Window Rate Limiter** 구현

## TikTok Rate Limiting 정책

### 1. Multi-Tiered Rate Limiting
TikTok은 3가지 레벨에서 Rate Limiting 적용:
- **IP 기반**: IP 주소당 제한
- **Cookie/Session 기반**: 쿠키(세션)당 제한 ⭐
- **Account 기반**: 계정(로그인)당 제한

### 2. 측정 방식
- **1분 Sliding Window** 기반
- 요청이 제한 초과 시 **HTTP 429** 에러 반환
- `Retry-After` 헤더로 대기 시간 제공

### 3. 관찰된 제한
- 정확한 수치는 비공개
- 추정: **30-50 req/min** (쿠키당, 엔드포인트에 따라 다름)

---

## 구현된 솔루션

### 1. Cookie Rotation (쿠키 로테이션)

여러 쿠키 파일을 순환 사용하여 쿠키당 rate limit 우회

#### 기능
- **Round-robin 로테이션**: 순차적으로 쿠키 교체
- **Worker별 쿠키 할당**: 병렬 처리 시 워커마다 다른 쿠키 사용
- **자동 쿠키 교체**: 일정 요청 후 자동 교체

#### 파일 위치
```
tiktok_keyword_scraper/cookie_rotator.py
```

#### 사용법
```python
from cookie_rotator import CookieRotator

# 초기화 (data/ 디렉토리의 *cookies*.json 파일 자동 로드)
rotator = CookieRotator('data')

# 다음 쿠키 가져오기 (Round-robin)
cookies = rotator.get_next_cookies()

# 워커별 고정 쿠키 (병렬 처리용)
cookies = rotator.get_cookies_for_worker(worker_id=0)
```

### 2. Sliding Window Rate Limiter

1분 sliding window 기반으로 분당 요청 수 제한

#### 기능
- **1분 Sliding Window**: 최근 60초 내 요청 수 추적
- **자동 대기**: 제한 초과 시 자동으로 대기
- **Thread-safe**: 병렬 처리 안전

#### 파일 위치
```
tiktok_keyword_scraper/cookie_rotator.py
```

#### 사용법
```python
from cookie_rotator import SlidingWindowRateLimiter

# 초기화 (분당 30요청 제한)
limiter = SlidingWindowRateLimiter(max_requests_per_minute=30)

# 요청 전 호출 (필요 시 자동 대기)
limiter.acquire()

# 실제 요청 수행
response = requests.get(url)
```

---

## 적용된 파일

### enrich_follower_counts.py

팔로워 수 추출 스크립트에 Cookie Rotation + Rate Limiter 적용

#### 변경사항

**Before (기존 코드)**:
```python
# 단일 쿠키만 사용
cookies = {cookie['name']: cookie['value'] for cookie in cookies_list}

# 요청 간 랜덤 딜레이만 적용
time.sleep(random.uniform(0.4, 0.6))
```

**After (개선된 코드)**:
```python
# 쿠키 로테이션 활성화
self.cookie_rotator = CookieRotator('data')
self.cookies = self.cookie_rotator.get_next_cookies()

# Sliding Window Rate Limiter 초기화
self.rate_limiter = SlidingWindowRateLimiter(max_requests_per_minute=30)

# 요청 전 rate limit 체크
self.rate_limiter.acquire()

# 20요청마다 쿠키 자동 교체
if self.request_count % 20 == 0:
    self.cookies = self.cookie_rotator.get_next_cookies()
    self.session.cookies.update(self.cookies)
```

#### 429 에러 처리 강화
```python
if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    print(f"⚠️ Rate Limit (429)! {retry_after}초 대기...")
    time.sleep(retry_after)

    # 쿠키 강제 교체
    if self.use_cookie_rotation:
        self.cookies = self.cookie_rotator.get_next_cookies()
        self.session.cookies.update(self.cookies)
```

---

## 설정 가이드

### 1. 쿠키 파일 준비

`data/` 디렉토리에 여러 쿠키 파일 준비:

```bash
data/
├── tiktok_cookies.json        # 쿠키 세트 1
├── tiktok_session_cookies.json # 쿠키 세트 2
└── cookies.json                # 쿠키 세트 3
```

**쿠키 추출 방법**:
1. Chrome Extension: [Cookie Editor](https://chrome.google.com/webstore/detail/cookie-editor)
2. 브라우저: 개발자 도구 > Application > Cookies
3. Selenium: 자동 쿠키 추출 스크립트

### 2. 설정 파라미터

#### 보수적 모드 (안정성 우선)
```python
conservative_mode = True
max_workers = 3
requests_per_minute = 20
# 예상: 20 req/min
```

#### 일반 모드 (균형)
```python
conservative_mode = False
max_workers = 5
requests_per_minute = 30
# 예상: 30 req/min
```

#### 공격적 모드 (속도 우선, 위험)
```python
conservative_mode = False
max_workers = 8
requests_per_minute = 40
# 예상: 40 req/min (429 에러 발생 가능)
```

### 3. 실행 예시

```bash
# 기본 실행
python3 enrich_follower_counts.py

# 설정 변경 (파일 내부)
# enrich_follower_counts.py:732-744
conservative_mode = True   # 보수적 모드
use_cookie_rotation = True # 쿠키 로테이션 활성화
requests_per_minute = 30   # 분당 30요청
```

---

## 테스트

### 테스트 스크립트 실행

```bash
python3 test_rate_limiting.py
```

### 테스트 항목
1. ✅ CookieRotator: Round-robin, Worker별 할당
2. ✅ SlidingWindowRateLimiter: Sliding window 동작 검증
3. ✅ 통합 테스트: Cookie Rotation + Rate Limiter 조합

### 예상 출력
```
🎉 모든 테스트 통과!

💡 다음 단계:
   1. data/ 디렉토리에 여러 쿠키 파일 준비
   2. enrich_follower_counts.py 실행
   3. Rate limiting 로그 모니터링
```

---

## 성능 비교

| 설정 | 쿠키 수 | 분당 요청 | Rate Limit | 예상 처리량 | 안정성 |
|------|---------|----------|-----------|-----------|--------|
| **기존** | 1개 | 80-120 | 없음 | 80-120/min | ❌ 불안정 |
| **보수적** | 3개 | 20 | Sliding Window | 20/min | ✅✅ 매우 안정 |
| **일반** | 3개 | 30 | Sliding Window | 30/min | ✅ 안정 |
| **쿠키 많음** | 10개 | 30 | Sliding Window | 300/min | ✅✅✅ 최고 |

**핵심**: 쿠키 수 × 분당 요청 수 = 총 처리량

**예시**:
- 쿠키 3개 × 30 req/min = **90 req/min**
- 쿠키 10개 × 30 req/min = **300 req/min** 🚀

---

## 모니터링 및 디버깅

### 로그 확인

실행 시 다음 로그 확인:

```bash
✅ 쿠키 로테이션 활성화: 3개 쿠키
✅ Sliding Window Rate Limiter: 30 req/min
🔄 쿠키 로테이션: tiktok_cookies.json (43개 쿠키)
⏳ Rate limit 도달 (30/30). 5.2초 대기 중...
🔄 쿠키 교체 (20번째 요청)
⚠️ Rate Limit (429)! 60초 대기...
🔄 쿠키 강제 교체 (429 응답)
```

### 429 에러 발생 시

1. **즉시 조치**:
   - `requests_per_minute` 감소 (30 → 20)
   - `max_workers` 감소 (5 → 3)

2. **장기 조치**:
   - 쿠키 파일 추가 (3개 → 5개+)
   - 프록시 추가 사용

---

## 추가 개선 방안

### 1. 프록시 로테이션 추가
```python
# 이미 구현됨
extractor = FollowerCountExtractor(proxy_file='data/proxies.txt')
```

### 2. 쿠키 자동 갱신
```python
# fast_api_scraper_v4.py 참고
cookie_manager = AutoCookieManager(refresh_interval=100)
```

### 3. 분산 크롤링
- 여러 서버/IP에서 분산 실행
- 각 서버마다 다른 쿠키 세트 사용

---

## FAQ

### Q1. 쿠키는 몇 개나 필요한가요?
**A**: 최소 3개 권장. 처리량 향상을 위해 5-10개 준비.

### Q2. 429 에러가 계속 발생해요
**A**:
1. `requests_per_minute` 감소 (30 → 20)
2. 쿠키 파일 추가
3. 프록시 사용

### Q3. 쿠키 로테이션 없이 사용 가능한가요?
**A**: 가능. `use_cookie_rotation=False` 설정.

```python
extractor = FollowerCountExtractor(use_cookie_rotation=False)
```

### Q4. 여러 쿠키 파일 형식이 다른데요?
**A**: CookieRotator가 자동으로 처리. List, Dict 형식 모두 지원.

### Q5. Sliding Window vs Fixed Window 차이는?
**A**:
- **Sliding Window** (구현됨): 1분 내 요청 수 정확히 추적
- **Fixed Window**: 1분 단위로 초기화 (부정확)

---

## 참고 자료

- [TikTok API Rate Limits (공식)](https://developers.tiktok.com/doc/tiktok-api-v2-rate-limit)
- [Sliding Window Rate Limiting](https://www.scrapeless.com/en/blog/rate-limiting)
- [Cookie Rotation Best Practices](https://webscraping.ai/faq/tiktok-scraping)

---

## 라이선스

This project is for educational and research purposes only.

**중요**: TikTok의 Terms of Service를 준수하세요. 무단 스크래핑은 서비스 약관 위반일 수 있습니다.
