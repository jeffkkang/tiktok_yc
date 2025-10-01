#!/bin/bash
# TikTok 키워드 스크래퍼 테스트 스크립트

echo "========================================="
echo "TikTok 키워드 스크래퍼 테스트"
echo "========================================="
echo ""

# 테스트 출력 디렉토리 생성
mkdir -p test_results

# 테스트 1: 한글 키워드
echo "📝 테스트 1: 한글 키워드 'K뷰티'"
python tiktok_keyword_scraper.py \
  --keyword "K뷰티" \
  --limit 5 \
  --out test_results/test_kbeauty.csv \
  --delay-min 0.5 \
  --delay-max 1.0

echo ""
echo "----------------------------------------"
echo ""

# 테스트 2: 영어 키워드
echo "📝 테스트 2: 영어 키워드 'skincare routine'"
python tiktok_keyword_scraper.py \
  --keyword "skincare routine" \
  --limit 5 \
  --out test_results/test_skincare.csv \
  --delay-min 0.5 \
  --delay-max 1.0

echo ""
echo "----------------------------------------"
echo ""

# 테스트 3: 이모지 포함 키워드
echo "📝 테스트 3: 이모지 포함 'makeup tutorial 💄'"
python tiktok_keyword_scraper.py \
  --keyword "makeup tutorial 💄" \
  --limit 5 \
  --out test_results/test_emoji.csv \
  --delay-min 0.5 \
  --delay-max 1.0

echo ""
echo "========================================="
echo "✅ 모든 테스트 완료"
echo "========================================="
echo ""

# 결과 파일 확인
echo "📊 생성된 파일 목록:"
ls -lh test_results/

echo ""
echo "📄 CSV 내용 미리보기 (첫 3줄):"
for file in test_results/*.csv; do
  echo ""
  echo "=== $file ==="
  head -n 3 "$file"
done
