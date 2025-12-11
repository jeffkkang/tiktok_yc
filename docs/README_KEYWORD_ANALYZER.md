# 키워드 분석기 사용법

## 개요

`analyze_unanalyzed_keywords.py` 스크립트는 프로젝트에서 아직 분석되지 않은 키워드들을 찾아서 선택하고, 하이브리드 스크래핑을 실행하는 도구입니다.

## 주요 기능

- ✅ **다양한 키워드 소스 통합**: 여러 키워드 파일에서 키워드들을 수집
- 🚫 **중복 제외**: 이미 사용된/실패한/분석된 키워드들을 자동 제외
- 🎯 **스마트 선택**: 랜덤, 우선순위, 전체 선택 등 다양한 선택 방법 지원
- 🚀 **자동 실행**: 선택된 키워드로 하이브리드 스크래핑 자동 실행
- 📊 **결과 보고**: 성공/실패 결과 상세 보고

## 사용법

### 기본 사용법

```bash
# 랜덤하게 5개 키워드 선택 후 분석
python analyze_unanalyzed_keywords.py

# 특정 개수 지정
python analyze_unanalyzed_keywords.py -c 10

# 키워드만 확인하고 실행하지 않음
python analyze_unanalyzed_keywords.py --list-only -c 10
```

### 선택 방법 지정

```bash
# 랜덤 선택 (기본값)
python analyze_unanalyzed_keywords.py -m random -c 5

# 우선순위 기반 선택
python analyze_unanalyzed_keywords.py -m priority -c 5 --priority beauty skincare makeup

# 모든 남은 키워드 선택 (최대 개수까지)
python analyze_unanalyzed_keywords.py -m all -c 20
```

### 스크래핑 옵션

```bash
# 브라우저 모드 사용 (더 안정적)
python analyze_unanalyzed_keywords.py --browser

# 수집할 개수 지정 (기본값: 100)
python analyze_unanalyzed_keywords.py -l 200
```

### 모든 옵션 확인

```bash
python analyze_unanalyzed_keywords.py --help
```

## 키워드 소스 파일들

스크립트는 다음 키워드 파일들을 자동으로 확인합니다:

- `popular_beauty_keywords.txt` - 인기 뷰티 키워드들
- `mega_beauty_keywords.txt` - 대용량 뷰티 키워드들
- `high_volume_keywords.txt` - 고빈도 키워드들
- `popular_keywords_batch2.txt` - 추가 인기 키워드들

## 제외 키워드 파일들

다음 파일들에서 키워드들을 제외합니다:

- `used_keywords.txt` - 이미 사용한 키워드들
- `failed_keywords.txt` - 실패한 키워드들
- `keyword_history.json` - 키워드 실행 기록
- `results/` 디렉토리의 기존 결과 파일들

## 출력 예시

```
🔍 키워드 소스 파일들 로드 중...
✅ popular_beauty_keywords.txt: 50개 키워드 로드
✅ mega_beauty_keywords.txt: 100개 키워드 로드
🚫 제외 키워드 파일들 로드 중...
✅ used_keywords.txt: 500개 키워드 제외
✅ 이미 분석된 키워드: 150개
🎯 분석되지 않은 키워드: 300개

🎯 선택된 키워드들 (5개):
  1. newbeautytrend
  2. skincarehacks
  3. makeupinspo
  4. beautysecrets
  5. naturalmakeup

🚀 위 키워드들로 분석을 시작하시겠습니까? (y/N): y

🚀 5개 키워드 분석 시작...
[1/5] 'newbeautytrend' 분석 중...
[2/5] 'skincarehacks' 분석 중...
...

📊 분석 결과:
  newbeautytrend: ✅ 성공
  skincarehacks: ✅ 성공
  makeupinspo: ❌ 실패
  beautysecrets: ✅ 성공
  naturalmakeup: ✅ 성공

🎉 완료: 4/5 성공
```

## 로그 파일

스크립트 실행 시 다음 로그 파일들이 생성됩니다:

- `keyword_analysis.log` - 상세 실행 로그
- `batch_scraper.log` - 개별 키워드 스크래핑 로그들

## 주의사항

- 스크립트 실행 시 각 키워드 간 5초 간격을 두어 서버 부하를 방지합니다
- 타임아웃(10분)을 초과하면 해당 키워드는 실패로 처리됩니다
- 브라우저 모드를 사용하면 더 안정적이지만 느릴 수 있습니다
- 대량 키워드 분석 시 `--list-only` 옵션으로 먼저 확인 후 실행하세요

## 문제 해결

### 키워드가 선택되지 않는 경우
- 키워드 소스 파일들이 존재하는지 확인
- 제외 키워드 파일들이 올바른지 확인
- `results/` 디렉토리의 파일들이 올바른지 확인

### 스크래핑이 실패하는 경우
- VPN/프록시 설정 확인
- 쿠키 파일(`cookies.json`) 확인
- 브라우저 모드(`--browser`) 사용 시도

### 메모리 부족 오류
- 선택 개수를 줄여서 실행 (`-c 3` 등)
- 불필요한 프로그램 종료 후 실행
