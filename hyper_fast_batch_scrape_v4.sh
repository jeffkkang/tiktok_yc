#!/bin/bash

# 🚀 초고속 분산 수집 스크립트 V4
# Priority 2 개선: 병렬 처리 + 자동 쿠키 갱신
# 예상 시간: 5-7분 (키워드당 20초)

cd "$(dirname "$0")"
source .venv/bin/activate

LOG_FILE="hyper_fast_batch_scraping_v4.log"

# 키워드 로드
KEYWORDS=()
while IFS= read -r line; do
    KEYWORDS+=("$line")
done < keywords_fast_batch.txt

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "======================================"
log "🚀 초고속 분산 스크래핑 V4 시작"
log "======================================"
log "방식: 검색어 변형 + 병렬 처리 (3 workers)"
log "키워드: ${#KEYWORDS[@]}개"
log "각 키워드: 200개 목표"
log "예상 시간: 5-7분"
log "======================================"

total_collected=0
successful_keywords=0
start_total=$(date +%s)

for i in "${!KEYWORDS[@]}"; do
    keyword="${KEYWORDS[$i]}"
    num=$((i+1))

    log ""
    log "[$num/${#KEYWORDS[@]}] 키워드: $keyword"
    log "--------------------------------------"

    start_time=$(date +%s)
    log "⏰ 시작: $(date '+%H:%M:%S')"

    # V4 API 스크래퍼 실행 (병렬 처리 + 자동 쿠키 갱신)
    python -m tiktok_keyword_scraper.fast_api_scraper_v4 \
        -k "$keyword" \
        -l 200 \
        --max-workers 3 \
        > "log_v4_${keyword}.txt" 2>&1

    exit_code=$?

    # 결과 확인
    elapsed=$(($(date +%s) - start_time))

    log "⏰ 완료: ${elapsed}초"

    if [ -f "results/${keyword}_api_v4.csv" ]; then
        lines=$(wc -l < "results/${keyword}_api_v4.csv" 2>/dev/null || echo 1)
        count=$((lines - 1))  # 헤더 제외

        if [ $count -gt 0 ]; then
            log "✅ 저장: ${count}개"
            total_collected=$((total_collected + count))
            successful_keywords=$((successful_keywords + 1))
        else
            log "⚠️  데이터 없음"
        fi
    else
        log "⚠️  파일 없음"
    fi

    # 로그 병합
    if [ -f "log_v4_${keyword}.txt" ]; then
        echo "--- 상세 로그: $keyword ---" >> "$LOG_FILE"
        tail -10 "log_v4_${keyword}.txt" >> "$LOG_FILE"
        rm "log_v4_${keyword}.txt"
    fi

    # 짧은 대기 (레이트 리밋 대응)
    if [ $i -lt $((${#KEYWORDS[@]}-1)) ]; then
        sleep 2
    fi
done

elapsed_total=$(($(date +%s) - start_total))
minutes=$((elapsed_total / 60))
seconds=$((elapsed_total % 60))

log ""
log "======================================"
log "✅ 전체 완료!"
log "======================================"
log "📊 최종 통계:"
log "- 처리 키워드: ${#KEYWORDS[@]}개"
log "- 성공 키워드: ${successful_keywords}개"
log "- 수집 데이터: ${total_collected}개"
log "- 총 소요 시간: ${minutes}분 ${seconds}초"
log "- 로그: ${LOG_FILE}"
log ""

# 결과 파일 리스트
log "📁 수집된 파일:"
ls -lh results/*_api_v4.csv 2>/dev/null | awk '{print $9, $5}' | tee -a "$LOG_FILE"

log ""
log "🎉 스크래핑 완료! 총 ${total_collected}개 수집"
log "평균: $(awk "BEGIN {printf \"%.1f\", $total_collected / ${#KEYWORDS[@]}}")개/키워드"
log ""
log "🚀 V4 개선사항:"
log "  ✅ 병렬 처리 (3 workers) - 속도 3배 향상"
log "  ✅ 자동 쿠키 갱신 (100회마다)"
log "  ✅ Thread-safe Rate Limiter"
log "  ✅ 모든 Priority 1+2 개선사항 포함"
