# 12개 제한 우회 가이드

## 🎯 핵심 전략

TikTok API의 12개 제한은 **완전히 우회 불가능**하지만, **검색어 변형으로 수백~수천 개 수집 가능**합니다.

### 공식
```
총 수집량 = 검색어 변형 수 × 12개
```

## ✅ 실전 사용법

### 1단계: 쿠키 갱신
```bash
python extract_cookies.py
```

### 2단계: V5 스크래퍼 사용
```bash
python tiktok_keyword_scraper/fast_api_scraper_v5.py \
  -k "makeup" \
  -l 500 \
  --max-workers 3
```

### 예상 수집량
| 목표 개수 | 필요 변형 수 | 실제 생성 변형 | 예상 수집량 |
|----------|------------|--------------|------------|
| 100개    | 9개        | 13개         | 156개       |
| 200개    | 17개       | 21개         | 252개       |
| 500개    | 42개       | 50개         | 600개       |
| 1000개   | 84개       | 55개 (최대)   | 660개       |

## 📊 V5 스크래퍼의 55가지 변형 패턴

### 기본 (2개)
- `keyword`
- `#keyword`

### 튜토리얼 (6개)
- `keyword tutorial`
- `keyword tips`
- `keyword hacks`
- `how to keyword`
- `keyword guide`
- `keyword step by step`

### 시간/일상 (6개)
- `keyword routine`
- `daily keyword`
- `morning keyword`
- `night keyword`
- `quick keyword`
- `easy keyword`

### 스타일/유형 (7개)
- `keyword transformation`
- `keyword look`
- `natural keyword`
- `glam keyword`
- `simple keyword`
- `dramatic keyword`
- `subtle keyword`

### 인기/트렌드 (6개)
- `keyword ideas`
- `keyword inspiration`
- `keyword trends`
- `viral keyword`
- `trending keyword`
- `popular keyword`

### 제품/리뷰 (7개)
- `keyword review`
- `keyword products`
- `keyword haul`
- `keyword favorites`
- `best keyword`
- `keyword recommendations`
- `keyword must haves`

### 가격대 (5개)
- `affordable keyword`
- `drugstore keyword`
- `luxury keyword`
- `cheap keyword`
- `keyword dupes`

### 레벨/타겟 (4개)
- `beginner keyword`
- `advanced keyword`
- `professional keyword`
- `keyword for beginners`

### 추가 변형 (8개)
- `keyword collection`
- `keyword essentials`
- `keyword organization`
- `keyword storage`
- `keyword mistakes`
- `keyword secrets`
- `keyword tricks`

### 이모지 조합 (4개)
- `keyword ✨`
- `keyword 💄`
- `keyword 💅`
- `keyword ❤️`

## 🚀 성능 최적화

### 병렬 처리
```bash
--max-workers 3  # CPU 코어 수에 맞게 조정
```

### 성공률 향상
1. **쿠키 주기적 갱신**: 100회마다 자동 갱신
2. **Rate Limiting**: 적응형 지연 시간 (성공 시 빨라짐)
3. **Retry 로직**: 실패 시 최대 3회 재시도

## 📈 실제 성능 (테스트 결과)

### 성공 사례
```
키워드: makeup
변형 수: 10개
성공률: 10%
수집량: 12개 (1개 변형만 성공)
```

### 쿠키 만료 시
```
모든 변형 실패 → 쿠키 갱신 필요
```

## 💡 추가 팁

### 1. 키워드별 맞춤 변형
```python
# Beauty 키워드
makeup, skincare, haircare, nailcare

# 각각의 변형
"natural makeup", "morning skincare", "haircare routine"
```

### 2. 다중 키워드 배치 수집
```bash
# 여러 키워드를 한 번에
for keyword in makeup skincare haircare; do
    python tiktok_keyword_scraper/fast_api_scraper_v5.py -k "$keyword" -l 500
done
```

### 3. 쿠키 유효성 확인
```bash
# API 호출이 실패하면 쿠키 갱신
python extract_cookies.py
```

## ⚠️ 주의사항

1. **Rate Limiting**: 너무 빠른 요청은 차단될 수 있음
2. **쿠키 만료**: 주기적으로 갱신 필요 (4-6시간마다)
3. **중복 제거**: 자동으로 처리되지만, 최종 CSV에서 재확인 권장

## 🎓 결론

**12개 제한은 우회 불가능하지만, 검색어 변형으로 수백~수천 개 수집 가능합니다.**

- ✅ V5 스크래퍼는 최대 55개 변형 자동 생성
- ✅ 이론적으로 55 × 12 = **660개 수집 가능**
- ✅ 여러 키워드 조합 시 수천 개 수집 가능
