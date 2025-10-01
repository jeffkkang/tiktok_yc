# TikTok Video Analytics Functions Guide

TikTok 비디오 통계 및 메타데이터 수집 기능이 안정성과 성능 향상을 위해 두 개의 별도 함수로 분리되었습니다.

## 🚀 함수 분리 구조

### 1. TikTok API 전용 통계 함수 (`tiktok-stats-api-only`)
- **역할**: TikTok Display API를 통한 비디오 통계 업데이트
- **수집 데이터**: `like_count`, `comment_count`, `share_count`, `view_count`
- **실행 빈도**: 더 자주 실행 가능 (API 안정성이 높음)
- **장점**: 빠르고 안정적, 런타임 에러 거의 없음

### 2. 크롤링 전용 메타데이터 함수 (`tiktok-metadata-crawling`)
- **역할**: 웹 크롤링을 통한 메타데이터 수집
- **수집 데이터**: `platform_labels`, `location_created`, `music_title`, `saves_count`
- **실행 빈도**: 하루 1회 이하 권장
- **장점**: 3회 배치 처리로 런타임 에러 최소화, 크롤링 과부하 방지

## 📅 권장 실행 스케줄

### TikTok API 통계 함수
```bash
# 매시간 실행 (통계는 자주 변경됨)
0 * * * * curl -X POST https://YOUR_PROJECT.supabase.co/functions/v1/tiktok-stats-api-only
```

### 크롤링 메타데이터 함수
```bash
# 매일 오전 2시 실행 (메타데이터는 덜 변경됨)
0 2 * * * curl -X POST https://YOUR_PROJECT.supabase.co/functions/v1/tiktok-metadata-crawling
```

## 🔧 함수별 상세 기능

### TikTok API 함수 특징
- ✅ TikTok 토큰 자동 리프레시
- ✅ 401 에러 시 재시도 로직
- ✅ 토큰 만료 시 DB 상태 업데이트
- ✅ 30일 이내 UPLOADED 애플리케이션만 처리
- ✅ 메타데이터 관련 필드 건드리지 않음

### 크롤링 함수 특징
- ✅ 3회 배치 처리로 런타임 에러 방지
- ✅ 배치 간 5초 지연, 비디오 간 2초 지연
- ✅ 1일 이내 업데이트된 메타데이터는 스킵
- ✅ 안전한 메타데이터 파싱 및 검증
- ✅ `video_url`이 있는 비디오만 처리

## 📊 응답 형태

### API 함수 응답
```json
{
  "processed": 15,
  "successful": 14,
  "failed": 1,
  "results": [...]
}
```

### 크롤링 함수 응답
```json
{
  "processed": 10,
  "successful": 8,
  "failed": 2,
  "metadata_fetched": 8,
  "metadata_updated": 8,
  "batches_processed": 3,
  "results": [...]
}
```

## 🛠️ 환경 변수

두 함수 모두 다음 환경 변수가 필요합니다:

```bash
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key

# TikTok API (API 함수에만 필요)
TIKTOK_CLIENT_KEY=your_tiktok_client_key
TIKTOK_CLIENT_SECRET=your_tiktok_client_secret

# Collabeauty Brand Domain (크롤링 함수에만 필요)
COLLABEAUTY_BRAND_DOMAIN=your_vercel_domain.vercel.app
```

## 🚨 주요 개선 사항

1. **런타임 에러 방지**: 크롤링과 API 호출 분리로 안정성 대폭 향상
2. **배치 처리**: 크롤링 함수는 3회로 나누어 처리하여 타임아웃 방지
3. **지연 시간**: 적절한 지연으로 외부 API 과부하 방지
4. **선택적 업데이트**: 메타데이터는 1일 이내 업데이트된 경우 스킵
5. **에러 핸들링**: 개별 비디오 실패가 전체 배치에 영향주지 않음

## 🔄 기존 함수 대체

기존의 통합 함수 대신 이 두 함수를 사용하면:
- 🎯 **더 안정적인 통계 업데이트** (API 함수)
- 🛡️ **런타임 에러 최소화** (크롤링 함수)
- ⚡ **더 빠른 실행 속도** (각각 최적화)
- 📈 **더 나은 모니터링** (분리된 로그)

## 📝 모니터링

각 함수의 실행 결과를 모니터링하여:
- API 함수는 높은 성공률 유지 확인
- 크롤링 함수는 배치 처리 상태 확인
- 토큰 만료나 크롤링 API 오류 시 알림 설정 권장
