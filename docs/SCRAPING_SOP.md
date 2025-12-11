# 스크래핑 요청 처리 SOP (Standard Operating Procedure)

## 📋 개요

사용자가 스크래핑을 요청하면 아래 단계를 순차적으로 실행합니다.

---

## 🔄 전체 플로우

```
사용자 요청
    ↓
1. 키워드 확인 및 중복 체크
    ↓
2. 쿠키 상태 확인
    ↓
3. 스크래핑 실행 (Search API - 빠름)
    ↓
4. 결과 확인 및 리포트
    ↓
5. [선택적] 프로필 데이터 보강 (느림)
    └─→ 팔로워 수 추출
```

**참고:**
- STEP 1-4는 **빠른 검색** (키워드당 15-20초)
- STEP 5는 **선택적** (필요할 때만 실행, 프로필당 0.5초)

---

## 📝 상세 단계

### STEP 1: 키워드 확인 및 중복 체크

**목적:** 이미 수집된 키워드인지 확인하여 중복 작업 방지

**실행 도구:**
```bash
Bash: python keyword_manager.py
```

**확인 사항:**
- [ ] 현재 수집된 키워드 목록
- [ ] 요청된 키워드가 이미 존재하는지
- [ ] 전체 통계 (총 키워드, 총 아이템 수)

**출력 예시:**
```
📝 사용된 키워드 목록:
   ✓ makeup (193 items)
   ✓ beauty (200 items)
   ...
```

**판단:**
- ✅ **새 키워드인 경우** → STEP 2로 진행
- ⚠️ **이미 수집된 경우** → 사용자에게 확인
  - "이미 수집된 키워드입니다. 재수집하시겠습니까?"
  - YES → `--force` 옵션으로 STEP 2 진행
  - NO → 종료

---

### STEP 2: 쿠키 상태 확인

**목적:** API 호출에 필요한 쿠키가 유효한지 확인

**실행 도구:**
```bash
# 쿠키 파일 존재 및 최신성 확인
Bash: ls -lh tiktok_cookies.json

# 간단한 API 테스트 (옵션)
Bash: python debug_api_response.py
```

**확인 사항:**
- [ ] `tiktok_cookies.json` 파일 존재
- [ ] 파일 수정 시간 (2시간 이내인지)
- [ ] API 응답 상태 (200 OK, status_code: 0)

**판단:**
- ✅ **쿠키 유효** (최근 2시간 이내, API 정상) → STEP 3 진행
- ⚠️ **쿠키 만료 의심** (2시간 이상, 또는 status_code: 2483) → 쿠키 갱신

**쿠키 갱신:**
```bash
Bash: source .venv/bin/activate && python -c "
from tiktok_keyword_scraper.fast_api_scraper_v4 import AutoCookieManager
manager = AutoCookieManager()
manager.refresh_cookies()
"
```

또는 간단히:
```bash
Bash: source .venv/bin/activate && python refresh_and_retry.py
```

---

### STEP 3: 스크래핑 실행

**목적:** 실제 데이터 수집

#### 3-1. 단일 키워드 수집

**사용자 요청 예시:**
- "makeup 키워드로 200개 수집해줘"
- "beautyinfluencer 스크래핑 해줘"

**실행 도구:**
```bash
Bash: source .venv/bin/activate && python -m tiktok_keyword_scraper.fast_api_scraper_v4 \
    -k "{keyword}" \
    -l 200 \
    --max-workers 3
```

**파라미터:**
- `-k`: 키워드 (필수)
- `-l`: 수집 개수 (기본: 200)
- `--max-workers`: 병렬 워커 수 (기본: 3)

**예시:**
```bash
Bash: source .venv/bin/activate && python -m tiktok_keyword_scraper.fast_api_scraper_v4 \
    -k "makeup" \
    -l 200 \
    --max-workers 3
```

#### 3-2. 복수 키워드 배치 수집

**사용자 요청 예시:**
- "makeup, beauty, skincare 이 3개 키워드 수집해줘"
- "리스트에 있는 키워드들 전부 수집해줘"

**실행 방법:**

1. **키워드 파일 생성**
```bash
Write: /Users/im-yechan/CodeCollabeauty/tiktokscaperforseeding/requested_keywords.txt
내용:
makeup
beauty
skincare
```

2. **스마트 배치 스크래퍼 실행**
```bash
Bash: source .venv/bin/activate && python smart_batch_scraper.py \
    -f requested_keywords.txt \
    -l 200 \
    --max-workers 3
```

**참고:**
- 스마트 배치 스크래퍼는 자동으로 중복을 체크하므로 STEP 1 생략 가능
- 하지만 사용자에게 사전 정보 제공을 위해 STEP 1 실행 권장

#### 3-3. 강제 재수집

**사용자 요청 예시:**
- "makeup 다시 수집해줘"
- "이미 수집한 키워드인데 업데이트 해줘"

**실행 도구:**
```bash
Bash: source .venv/bin/activate && python smart_batch_scraper.py \
    -f requested_keywords.txt \
    --force
```

---

### STEP 4: 결과 확인 및 리포트

**목적:** 수집 성공 여부 확인 및 사용자에게 결과 전달

#### 4-1. 수집된 파일 확인

**실행 도구:**
```bash
# 최신 생성된 CSV 파일 확인
Bash: ls -lht results/*_api_v4.csv | head -5

# 특정 키워드 파일 확인
Bash: wc -l results/{keyword}_api_v4.csv
```

**확인 사항:**
- [ ] CSV 파일 생성 여부
- [ ] 파일 크기 (너무 작으면 실패 의심)
- [ ] 수집된 아이템 수

#### 4-2. 히스토리 업데이트

**실행 도구:**
```bash
Bash: source .venv/bin/activate && python keyword_manager.py
```

**효과:**
- `keyword_history.json` 자동 업데이트
- `used_keywords.txt` 업데이트
- 중복 파일 자동 통합

#### 4-3. 결과 요약 출력

**실행 도구:**
```bash
# CSV 파일 읽어서 요약
Read: /Users/im-yechan/CodeCollabeauty/tiktokscaperforseeding/results/{keyword}_api_v4.csv
(limit=10으로 샘플 확인)
```

**사용자에게 전달할 정보:**
```
✅ 수집 완료!

키워드: makeup
파일: results/makeup_api_v4.csv
아이템 수: 193개
고유 크리에이터: 165명
소요 시간: 16초

샘플 데이터:
- @username1: "makeup tutorial..."
- @username2: "beauty tips..."
...
```

---

### STEP 5: [선택적] 프로필 데이터 보강

**목적:** 팔로워 수 등 상세 프로필 데이터 추가

**⚠️ 중요:**
- 이 단계는 **선택적**입니다
- Search API는 팔로워 수를 제공하지 않음
- 프로필 페이지를 방문해야 하므로 **느림** (프로필당 0.5초)
- **1,779개 프로필** → 약 **14분** 소요

**실행 시점:**
- ✅ 팔로워 수로 필터링이 필요할 때
- ✅ 영향력 분석이 필요할 때
- ✅ 최종 타겟팅 전 검증 단계
- ❌ 단순 키워드 검색 결과만 필요할 때는 **생략**

#### 5-1. 팔로워 수 추출

**실행 도구:**
```bash
Bash: source .venv/bin/activate && python enrich_follower_counts.py
```

**처리 과정:**
1. `final_filtered_results.csv` 읽기
2. 각 프로필에 대해 HTTP 요청 (병렬 3개)
3. Embedded JSON에서 팔로워 수 추출
4. 50개마다 중간 저장 (체크포인트)
5. `final_filtered_results_with_followers.csv` 생성

**진행 상황 모니터링:**
```bash
# 실시간 진행 상황 확인
Bash: tail -f enrich_follower_counts.log

# 또는 BashOutput으로 출력 확인
BashOutput: {bash_id}
```

**예상 시간:**
- 100개 프로필: 약 50초
- 500개 프로필: 약 4분
- 1,779개 프로필: 약 14분

#### 5-2. 결과 확인

**실행 도구:**
```bash
# 파일 생성 확인
Bash: ls -lh final_filtered_results_with_followers.csv

# 샘플 확인 (팔로워 수 포함 여부)
Read: /Users/im-yechan/CodeCollabeauty/tiktokscaperforseeding/final_filtered_results_with_followers.csv
(limit=20)
```

**확인 사항:**
- [ ] 파일 생성 완료
- [ ] follower_count 컬럼 존재
- [ ] 0이 아닌 값들이 채워져 있는지
- [ ] 성공률 확인 (99%+ 권장)

**통계 확인:**
```python
# Python으로 간단히 확인
import pandas as pd
df = pd.read_csv('final_filtered_results_with_followers.csv')

print(f"총 프로필: {len(df):,}개")
print(f"팔로워 수 보유: {len(df[df['follower_count'] > 0]):,}개")
print(f"평균 팔로워: {df['follower_count'].mean():,.0f}명")
print(f"중앙값: {df['follower_count'].median():,.0f}명")
print(f"최대: {df['follower_count'].max():,}명")
```

**사용자에게 전달:**
```
✅ 프로필 데이터 보강 완료!

입력: final_filtered_results.csv (1,779개)
출력: final_filtered_results_with_followers.csv

📊 통계:
- 총 프로필: 1,779개
- 팔로워 수 추출 성공: 1,779개 (100%)
- 평균 팔로워: 127,453명
- 중앙값: 8,421명
- 최대: 18,200,000명 (@meredithduxbury)

소요 시간: 14.3분
```

---

## 🎯 시나리오별 대응

### 시나리오 1: 단일 키워드 신규 수집

**사용자:** "makeup 키워드 200개 수집해줘"

**실행 순서:**
1. `Bash: python keyword_manager.py` → makeup 미수집 확인
2. `Bash: ls -lh tiktok_cookies.json` → 쿠키 유효 확인
3. `Bash: python -m tiktok_keyword_scraper.fast_api_scraper_v4 -k makeup -l 200`
4. `Bash: python keyword_manager.py` → 히스토리 업데이트
5. `Read: results/makeup_api_v4.csv` (limit=10) → 결과 확인
6. 사용자에게 요약 리포트 전달

---

### 시나리오 2: 이미 수집된 키워드 재요청

**사용자:** "beauty 키워드 수집해줘"

**실행 순서:**
1. `Bash: python keyword_manager.py` → beauty 이미 수집됨 확인
2. 사용자에게 확인: "beauty는 이미 200개 수집되어 있습니다. 재수집하시겠습니까?"
   - **NO** → 종료, 기존 파일 위치 안내
   - **YES** → 계속 진행
3. `Bash: python smart_batch_scraper.py -f <file> --force`
4. 결과 리포트

---

### 시나리오 3: 배치 수집 (5-10개)

**사용자:** "makeup, beauty, skincare, kbeauty, glowup 이 5개 수집해줘"

**실행 순서:**
1. `Bash: python keyword_manager.py` → 현재 상태 확인
2. `Write: requested_keywords.txt` → 5개 키워드 작성
3. 사용자에게 정보 제공:
   - "5개 중 2개는 이미 수집되어 있습니다"
   - "새로운 3개만 수집하시겠습니까? (추천)"
   - "또는 전체 5개를 재수집하시겠습니까?"
4. 선택에 따라:
   - 신규만: `Bash: python smart_batch_scraper.py -f requested_keywords.txt`
   - 전체: `Bash: python smart_batch_scraper.py -f requested_keywords.txt --force`
5. `Bash: python keyword_manager.py` → 최종 통계
6. 요약 리포트 전달

---

### 시나리오 4: 대량 배치 수집 (20개 이상)

**사용자:** "이미지에 있는 키워드들 전부 수집해줘" (40개 키워드)

**실행 순서:**
1. `Write: batch_keywords.txt` → 이미지의 키워드 작성
2. `Bash: python keyword_manager.py` → 중복 확인
3. 사용자에게 예상 소요 시간 안내:
   - "40개 중 15개는 신규입니다"
   - "예상 소요 시간: 약 5-7분"
   - "진행하시겠습니까?"
4. `Bash: ls -lh tiktok_cookies.json` → 쿠키 확인 (대량 작업 전 필수)
5. `Bash: python smart_batch_scraper.py -f batch_keywords.txt -l 200`
6. 중간 진행 상황 모니터링 (필요시)
7. `Bash: python keyword_manager.py` → 최종 통계
8. 상세 리포트 전달

---

### 시나리오 5: API 오류 발생

**증상:** "API 오류: Please login your account first" (status_code: 2483)

**실행 순서:**
1. 사용자에게 상황 설명: "쿠키가 만료되었습니다. 갱신 중..."
2. `Bash: source .venv/bin/activate && python refresh_and_retry.py`
3. 쿠키 갱신 완료 확인
4. 처음부터 재시도

---

### 시나리오 6: 팔로워 수 필터링 필요

**사용자:** "makeup 키워드로 수집한 결과에서 팔로워 10만 이상만 추출해줘"

**실행 순서:**
1. STEP 1-4로 기본 검색 완료 (이미 완료되어 있음)
2. 사용자에게 안내:
   - "팔로워 수 필터링을 위해 프로필 데이터를 추출해야 합니다"
   - "현재 1,779개 프로필 → 약 14분 소요됩니다"
   - "진행하시겠습니까?"
3. `Bash: python enrich_follower_counts.py` (백그라운드 실행)
4. 완료 후 필터링:
   ```python
   import pandas as pd
   df = pd.read_csv('final_filtered_results_with_followers.csv')
   df_filtered = df[df['follower_count'] >= 100000]
   df_filtered.to_csv('high_followers_results.csv', index=False)

   print(f"10만 이상: {len(df_filtered)}개")
   ```
5. 필터링 결과 리포트

---

### 시나리오 7: 영향력 분석

**사용자:** "beauty 인플루언서들의 영향력 순위를 보여줘"

**실행 순서:**
1. STEP 5 실행하여 팔로워 수 추출
2. 팔로워 수 기준 정렬:
   ```python
   df = pd.read_csv('final_filtered_results_with_followers.csv')
   df_sorted = df.sort_values('follower_count', ascending=False)

   # 상위 20명 출력
   for idx, row in df_sorted.head(20).iterrows():
       print(f"{idx+1}. @{row['creator_username']}: {row['follower_count']:,}명")
   ```
3. 영향력 분석 리포트 제공

---

## ⚡ 빠른 참조

### 자주 사용하는 명령어

```bash
# 1. 현재 상태 확인
python keyword_manager.py

# 2. 단일 키워드 수집 (빠름)
python -m tiktok_keyword_scraper.fast_api_scraper_v4 -k "{keyword}" -l 200

# 3. 배치 수집 (중복 자동 제외)
python smart_batch_scraper.py -f keywords.txt

# 4. 강제 재수집
python smart_batch_scraper.py -f keywords.txt --force

# 5. 쿠키 갱신
python refresh_and_retry.py

# 6. 결과 파일 확인
ls -lht results/*_api_v4.csv | head -5

# 7. [선택적] 팔로워 수 추출 (느림, 14분)
python enrich_follower_counts.py
```

---

## 📊 도구 선택 가이드

| 상황 | 도구 | 속도 | 이유 |
|------|------|------|------|
| 키워드 1개 수집 | `fast_api_scraper_v4.py` | ⚡ 빠름 (15초) | 빠르고 직접적 |
| 키워드 5-10개 수집 | `smart_batch_scraper.py` | ⚡ 빠름 (1-2분) | 중복 자동 체크 |
| 키워드 20개 이상 수집 | `smart_batch_scraper.py` | ⚡ 빠름 (5-7분) | 진행 상황 추적 |
| 재수집 필요 | `smart_batch_scraper.py --force` | ⚡ 빠름 | 강제 실행 |
| 쿠키 만료 | `refresh_and_retry.py` | ⚡ 즉시 | 자동 갱신 |
| 중복 파일 정리 | `keyword_manager.py` | ⚡ 즉시 | 통합 및 정리 |
| **팔로워 수 필요** | `enrich_follower_counts.py` | 🐢 **느림 (14분)** | **선택적 사용** |

---

## ✅ 체크리스트 (수집 전)

- [ ] 키워드 중복 확인 완료
- [ ] 쿠키 상태 확인 완료 (2시간 이내)
- [ ] 수집 개수 확인 (기본 200개)
- [ ] 예상 소요 시간 안내
- [ ] 사용자 최종 확인

## ✅ 체크리스트 (수집 후)

- [ ] CSV 파일 생성 확인
- [ ] 아이템 수 확인
- [ ] 히스토리 업데이트 (`keyword_manager.py`)
- [ ] 사용자에게 결과 리포트
- [ ] 샘플 데이터 제공 (선택)

---

## 🚨 예외 상황 처리

### 오류 1: 쿠키 만료
```
Error: status_code: 2483
Action: python refresh_and_retry.py
```

### 오류 2: 네트워크 타임아웃
```
Error: TimeoutError
Action: 재시도 (자동으로 3회 재시도됨)
```

### 오류 3: 수집 결과 0개
```
Possible Causes:
1. 키워드 철자 오류
2. 결과가 실제로 없음
3. API 제한
Action: 다른 키워드로 테스트
```

### 오류 4: 중복 파일 생성
```
Example: beauty_api_v4.csv + beauty review_api_v4.csv
Action: python keyword_manager.py (자동 통합)
```

### 오류 5: 프로필 추출 실패 (일부)
```
증상: 일부 프로필의 follower_count가 0
원인:
1. 비공개 계정
2. 삭제된 계정
3. 일시적 네트워크 오류
Action:
- 99% 이상 성공률이면 정상
- 실패한 계정들 확인:
  df[df['follower_count'] == 0]['creator_username']
```

### 오류 6: 프로필 추출 중단
```
증상: 중간에 프로세스가 종료됨
원인: 네트워크 불안정, 시스템 리소스 부족
Action:
1. 체크포인트 파일 확인 (50개마다 저장됨)
2. final_filtered_results_with_followers.csv 로드
3. 남은 프로필만 재실행 또는 전체 재실행
```

---

---

## 📌 요약: 속도 최적화 전략

### 빠른 워크플로우 (권장)
```
1-4단계: 키워드 검색 (15-20초/키워드)
  ↓
결과 확인 및 기본 분석
  ↓
필요시에만 STEP 5 실행 (14분)
```

### 언제 STEP 5를 실행할까?

**✅ 실행해야 할 때:**
- 팔로워 수로 필터링 필요 (예: 10만 이상)
- 영향력 순위 분석 필요
- 최종 타겟팅 전 검증 단계

**❌ 생략해도 될 때:**
- 단순 키워드 검색 결과만 필요
- 프로필 목록만 수집
- 이메일 수집이 주 목적

### 속도 비교

| 작업 | 속도 | 비고 |
|------|------|------|
| 키워드 검색 (200개) | 15-20초 | Search API (빠름) |
| 프로필 추출 (1,779개) | 14분 | HTTP 요청 (느림) |
| **전체 (검색만)** | **5-7분** | 20개 키워드 기준 |
| **전체 (검색+프로필)** | **19-21분** | 검색 + 프로필 추출 |

### 핵심 원칙
1. **검색은 빠르게** - Search API 사용
2. **프로필은 선택적으로** - 필요할 때만
3. **분리하여 실행** - 속도 유지

---

**작성일:** 2025-10-05
**버전:** 1.1 (Profile Extraction 추가)
**목적:** 스크래핑 요청 처리 표준화
**업데이트:** STEP 5 (프로필 데이터 보강) 추가
