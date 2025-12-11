# 프로젝트 구조 (정리 후)

## 📁 디렉토리 구조

```
tiktokscaperforseeding/
├── 📂 tiktok_keyword_scraper/     # 메인 스크래퍼 패키지
│   ├── __init__.py
│   ├── main.py                    # CLI 진입점
│   ├── scraper.py                 # DOM 기반 스크래퍼
│   ├── fast_api_scraper_v3.py     # API 스크래퍼 V3
│   ├── fast_api_scraper_v4.py     # ⭐ API 스크래퍼 V4 (현재 버전)
│   ├── fast_api_scraper_v5.py     # API 스크래퍼 V5 (프록시+페이지네이션)
│   ├── profile.py                 # 프로필 추출
│   ├── email.py                   # 이메일 추출
│   ├── cookie.py                  # 쿠키 관리
│   ├── config.py                  # 설정 관리
│   ├── output.py                  # 출력 처리
│   ├── logger.py                  # 로깅
│   └── utils.py                   # 유틸리티
│
├── 📂 results/                    # 수집된 CSV 파일들
│   ├── makeup_api_v4.csv
│   ├── beauty_api_v4.csv
│   └── ... (22개 키워드)
│
├── 📂 archive/                    # 아카이브된 파일들
│   ├── old_scripts/               # 오래된 배치 스크립트
│   ├── old_logs/                  # 오래된 로그 파일
│   ├── old_docs/                  # 오래된 문서
│   ├── test_files/                # 테스트 파일
│   └── debug_images/              # 디버그 이미지
│
├── 🐍 Python 스크립트
│   ├── run_scraper.py             # V2 스크래퍼 진입점
│   ├── keyword_manager.py         # ⭐ 키워드 관리 시스템
│   ├── smart_batch_scraper.py     # ⭐ 스마트 배치 스크래퍼
│   ├── refresh_and_retry.py       # 쿠키 갱신 + 재시도
│   ├── extract_all_cookies.py     # 전체 쿠키 추출 (Selenium)
│   └── extract_cookies.py         # 쿠키 추출 (기본)
│
├── 📜 배치 스크립트
│   └── hyper_fast_batch_scrape_v4.sh  # ⭐ V4 배치 스크립트
│
├── 📋 설정 파일
│   ├── config.yaml                # 기본 설정
│   ├── cookies.json               # TikTok 쿠키 (게스트)
│   ├── tiktok_cookies.json        # TikTok 쿠키 (갱신용)
│   ├── tiktok_api_endpoints.json  # API 엔드포인트
│   ├── keyword_history.json       # 키워드 사용 이력
│   └── used_keywords.txt          # 사용된 키워드 목록
│
├── 📖 문서
│   ├── README.md                  # 프로젝트 소개
│   ├── SCRAPING_SOP.md            # ⭐ 스크래핑 SOP (필수)
│   ├── KEYWORD_MANAGEMENT_GUIDE.md # 키워드 관리 가이드
│   ├── SUMMARY.md                 # 프로젝트 요약
│   ├── KEYWORD_SCRAPER_GUIDE.md   # V2 스크래퍼 가이드
│   └── PROJECT_STRUCTURE.md       # 이 파일
│
├── 📝 기타
│   ├── requirements.txt           # Python 의존성
│   ├── LICENSE                    # MIT 라이센스
│   ├── .gitignore                 # Git 무시 목록
│   ├── .clauderc                  # Claude 프로젝트 설정
│   └── new_keywords.txt           # 새 키워드 템플릿
│
└── 📂 히든 디렉토리
    ├── .git/                      # Git 저장소
    ├── .venv/                     # Python 가상환경
    └── .claude/                   # Claude 캐시
```

---

## ⭐ 핵심 파일

### 스크래핑 시스템

| 파일 | 설명 | 사용법 |
|------|------|--------|
| `keyword_manager.py` | 키워드 관리 시스템 | `python keyword_manager.py` |
| `smart_batch_scraper.py` | 스마트 배치 스크래퍼 | `python smart_batch_scraper.py -f keywords.txt` |
| `fast_api_scraper_v4.py` | API 스크래퍼 V4 | `python -m tiktok_keyword_scraper.fast_api_scraper_v4 -k keyword` |
| `hyper_fast_batch_scrape_v4.sh` | V4 배치 스크립트 | `./hyper_fast_batch_scrape_v4.sh` |

### 문서

| 파일 | 내용 | 중요도 |
|------|------|--------|
| `SCRAPING_SOP.md` | 스크래핑 요청 처리 절차 | ⭐⭐⭐ 필수 |
| `KEYWORD_MANAGEMENT_GUIDE.md` | 키워드 시스템 가이드 | ⭐⭐ 중요 |
| `SUMMARY.md` | 프로젝트 현황 및 통계 | ⭐⭐ 중요 |
| `README.md` | 전체 프로젝트 소개 | ⭐ 참고 |

### 설정/데이터

| 파일 | 용도 |
|------|------|
| `keyword_history.json` | 키워드 사용 이력 DB |
| `used_keywords.txt` | 사용된 키워드 목록 |
| `cookies.json` | TikTok 인증 쿠키 |
| `config.yaml` | 기본 설정 |

---

## 📊 통계 (정리 후)

### 파일 수

```
핵심 파일:           23개
아카이브 파일:        60+ 개
문서:                 6개
Python 패키지:        15개 모듈
```

### 디렉토리 크기

```
results/            ~5MB (CSV 파일들)
archive/            ~3MB (오래된 파일들)
tiktok_keyword_scraper/  ~200KB (소스코드)
```

---

## 🔄 버전 히스토리

### V4 (현재 사용 중) ✅
- API 기반 스크래핑
- 병렬 처리 (3 워커)
- 자동 쿠키 갱신 (100회마다)
- 검색어 변형 전략 (20가지)
- **성능**: 키워드당 15-20초

### V5 (연구 단계)
- 프록시 로테이션
- 커서 페이지네이션 (실패)
- 모바일 API 연구

### V2 (레거시)
- DOM 기반 스크래핑
- 브라우저 자동화
- **성능**: 키워드당 15-20분

---

## 🎯 주요 워크플로우

### 1. 단일 키워드 수집
```bash
python -m tiktok_keyword_scraper.fast_api_scraper_v4 -k "makeup" -l 200
```

### 2. 배치 수집
```bash
python smart_batch_scraper.py -f keywords.txt -l 200
```

### 3. 키워드 관리
```bash
python keyword_manager.py
```

### 4. 쿠키 갱신
```bash
python refresh_and_retry.py
```

---

## 📦 아카이브 내용

### archive/old_scripts/
- `batch_scrape*.sh` - 오래된 배치 스크립트 (12개)
- `parallel_scrape.sh`, `ultra_fast_batch_scrape.sh` 등

### archive/old_logs/
- 모든 `.log` 파일 (10개 이상)
- 총 ~500KB

### archive/old_docs/
- API 발견, 커서 페이지네이션 연구 문서
- V4/V5 개선 요약
- 로그인 세션 가이드

### archive/test_files/
- 모든 테스트 스크립트 (`test_*.py`)
- 유틸리티 스크립트

### archive/debug_images/
- 디버그용 스크린샷 (`.png`)

---

## 🚀 다음 단계

### 선택 1: 아카이브 완전 삭제
```bash
# 더 이상 필요없다면
rm -rf archive/
```

### 선택 2: 아카이브 압축
```bash
# 백업 목적으로 보관
tar -czf archive_backup_$(date +%Y%m%d).tar.gz archive/
rm -rf archive/
```

### 선택 3: 아카이브 유지
- 현재 상태 유지 (나중에 참고 가능)
- `.gitignore`에 포함되어 커밋 안 됨

---

## ✅ 정리 효과

### 이전
```
- 90개 이상의 파일
- 복잡한 디렉토리 구조
- 중복 스크립트 많음
- 혼란스러운 버전 관리
```

### 이후
```
- 23개의 핵심 파일
- 깔끔한 구조
- 명확한 버전 (V4)
- 체계적인 문서
```

---

**정리 완료일:** 2025-10-05
**정리 방법:** `cleanup_project.sh` 스크립트 사용
**아카이브 크기:** ~3MB
**삭제된 파일:** 0개 (모두 아카이브로 이동)
