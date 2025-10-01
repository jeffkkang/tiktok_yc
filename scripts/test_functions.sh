#!/bin/bash

# TikTok 함수 테스트 스크립트
# 사용법: ./scripts/test_functions.sh

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 설정값 (실제 값으로 수정 필요)
PROJECT_ID="nscecbxechxejddkmtlc"
SERVICE_ROLE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zY2VjYnhlY2h4ZWpkZGttdGxjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MjIyMTAwOSwiZXhwIjoyMDU3Nzk3MDA5fQ.hkr_j6pAyllTChgbsyZq68LZp-CaRlWQlhgRSOeFPKs"
BASE_URL="https://${PROJECT_ID}.supabase.co/functions/v1"

echo -e "${BLUE}🚀 TikTok Functions Test Script${NC}"
echo "=================================="

# 프로젝트 설정 확인
if [ "$PROJECT_ID" = "YOUR_PROJECT_ID" ] || [ "$SERVICE_ROLE_KEY" = "YOUR_SERVICE_ROLE_KEY" ]; then
    echo -e "${RED}❌ 에러: 스크립트 상단의 PROJECT_ID와 SERVICE_ROLE_KEY를 실제 값으로 수정하세요${NC}"
    exit 1
fi

echo -e "${YELLOW}📋 설정 정보${NC}"
echo "Project ID: $PROJECT_ID"
echo "Base URL: $BASE_URL"
echo ""

# 함수 1: TikTok API 통계 업데이트
echo -e "${BLUE}🔄 테스트 1: TikTok API 통계 업데이트${NC}"
echo "실행 중..."

response1=$(curl -s -w "HTTPSTATUS:%{http_code}" \
  -X POST \
  -H "Authorization: Bearer $SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  "$BASE_URL/tiktok-stats-api-only")

http_status1=$(echo $response1 | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
response_body1=$(echo $response1 | sed -e 's/HTTPSTATUS:.*//g')

if [ "$http_status1" -eq 200 ]; then
    echo -e "${GREEN}✅ 성공 (HTTP $http_status1)${NC}"
    echo "응답: $response_body1" | jq . 2>/dev/null || echo "$response_body1"
else
    echo -e "${RED}❌ 실패 (HTTP $http_status1)${NC}"
    echo "응답: $response_body1"
fi

echo ""

# 함수 2: 메타데이터 크롤링
echo -e "${BLUE}🕷️ 테스트 2: 메타데이터 크롤링${NC}"
echo "실행 중... (시간이 오래 걸릴 수 있습니다)"

response2=$(curl -s -w "HTTPSTATUS:%{http_code}" \
  -X POST \
  -H "Authorization: Bearer $SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  "$BASE_URL/tiktok-metadata-crawling")

http_status2=$(echo $response2 | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
response_body2=$(echo $response2 | sed -e 's/HTTPSTATUS:.*//g')

if [ "$http_status2" -eq 200 ]; then
    echo -e "${GREEN}✅ 성공 (HTTP $http_status2)${NC}"
    echo "응답: $response_body2" | jq . 2>/dev/null || echo "$response_body2"
else
    echo -e "${RED}❌ 실패 (HTTP $http_status2)${NC}"
    echo "응답: $response_body2"
fi

echo ""

# 요약
echo -e "${BLUE}📊 테스트 요약${NC}"
echo "=================================="
if [ "$http_status1" -eq 200 ]; then
    echo -e "API 통계 함수: ${GREEN}✅ 성공${NC}"
else
    echo -e "API 통계 함수: ${RED}❌ 실패${NC}"
fi

if [ "$http_status2" -eq 200 ]; then
    echo -e "메타데이터 크롤링: ${GREEN}✅ 성공${NC}"
else
    echo -e "메타데이터 크롤링: ${RED}❌ 실패${NC}"
fi

echo ""
echo -e "${YELLOW}💡 참고사항:${NC}"
echo "- 함수가 정상 실행되면 크론잡 설정을 진행하세요"
echo "- 에러가 발생하면 함수 로그를 확인하세요"
echo "- CRON_SETUP_GUIDE.md 파일을 참고하여 크론잡을 설정하세요"
