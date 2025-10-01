# TikTok 메타데이터 크롤링 크론잡 설정 가이드

## 🔧 설정 단계

### 1. Supabase 프로젝트 정보 확인
먼저 다음 정보를 수집하세요:
- **프로젝트 ID**: Supabase 대시보드에서 확인
- **Service Role Key**: Supabase 프로젝트 설정에서 확인

### 2. 크론잡 설정 쿼리 실행

`supabase/migrations/create_cron_jobs.sql` 파일을 열고 다음 부분을 수정하세요:

```sql
-- 수정 필요한 부분 1: 프로젝트 ID
'https://YOUR_PROJECT_ID.supabase.co/functions/v1/tiktok-metadata-crawling'

-- 수정 필요한 부분 2: Service Role Key
'Authorization': 'Bearer YOUR_SERVICE_ROLE_KEY'
```

### 3. 실제 설정 예시

```sql
-- 메타데이터 크롤링 크론잡 (매일 오전 2시)
SELECT cron.schedule(
  'tiktok-metadata-crawling-daily',
  '0 2 * * *',
  $$
  SELECT
    net.http_post(
      url := 'https://abcdefghijk.supabase.co/functions/v1/tiktok-metadata-crawling',
      headers := '{"Content-Type": "application/json", "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'::jsonb,
      body := '{}'::jsonb
    ) as request_id;
  $$
);

-- API 통계 크론잡 (매시간)
SELECT cron.schedule(
  'tiktok-stats-api-hourly',
  '0 * * * *',
  $$
  SELECT
    net.http_post(
      url := 'https://abcdefghijk.supabase.co/functions/v1/tiktok-stats-api-only',
      headers := '{"Content-Type": "application/json", "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}'::jsonb,
      body := '{}'::jsonb
    ) as request_id;
  $$
);
```

## 📅 크론 스케줄 설명

### 메타데이터 크롤링: `'0 2 * * *'`
- **실행 시간**: 매일 오전 2시
- **이유**: 크롤링은 무거운 작업이므로 트래픽이 적은 시간대 선택
- **빈도**: 메타데이터는 자주 변경되지 않으므로 하루 1회면 충분

### API 통계: `'0 * * * *'`
- **실행 시간**: 매시간 정각
- **이유**: 통계는 실시간으로 변경되므로 자주 업데이트 필요
- **빈도**: API는 안정적이므로 시간당 1회 실행 가능

## 🛠️ 크론잡 관리 쿼리

### 현재 크론잡 상태 확인
```sql
SELECT jobname, schedule, active 
FROM cron.job 
WHERE jobname LIKE '%tiktok%';
```

### 최근 실행 기록 확인
```sql
SELECT 
  j.jobname,
  jr.status,
  jr.start_time,
  jr.end_time,
  jr.return_message
FROM cron.job j
LEFT JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE j.jobname LIKE '%tiktok%'
ORDER BY jr.start_time DESC 
LIMIT 5;
```

### 크론잡 중지
```sql
SELECT cron.unschedule('tiktok-metadata-crawling-daily');
SELECT cron.unschedule('tiktok-stats-api-hourly');
```

## 📊 모니터링 쿼리

### 메타데이터 업데이트 현황
```sql
SELECT 
  DATE(metadata_updated_at) as date,
  COUNT(*) as videos_updated
FROM campaign_application_videos 
WHERE metadata_updated_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(metadata_updated_at)
ORDER BY date DESC;
```

### 업데이트가 필요한 비디오 수
```sql
SELECT 
  COUNT(*) as needs_update
FROM campaign_application_videos cav
JOIN campaign_applications ca ON cav.campaign_application_id = ca.id
WHERE ca.status = 'UPLOADED'
  AND ca.created_at >= NOW() - INTERVAL '30 days'
  AND cav.video_url IS NOT NULL
  AND (cav.metadata_updated_at IS NULL 
       OR cav.metadata_updated_at < NOW() - INTERVAL '1 day');
```

## ⚠️ 주의사항

### 1. Service Role Key 보안
- Service Role Key는 매우 강력한 권한을 가지고 있습니다
- 반드시 안전한 곳에 보관하고 노출되지 않도록 주의하세요

### 2. 크론잡 실행 시간 조정
- 서버 시간대를 확인하세요 (보통 UTC)
- 한국 시간 기준으로 조정이 필요하면 9시간을 빼세요
  - 한국 시간 오전 11시 = UTC 오전 2시

### 3. 함수 배포 확인
- 크론잡 설정 전에 두 함수가 정상 배포되었는지 확인하세요:
  - `tiktok-stats-api-only`
  - `tiktok-metadata-crawling`

### 4. 권한 설정
- pg_cron 확장이 활성화되어 있는지 확인하세요
- 필요한 경우 Supabase 지원팀에 문의하세요

## 🚀 배포 순서

1. **함수 배포**
   ```bash
   supabase functions deploy tiktok-stats-api-only
   supabase functions deploy tiktok-metadata-crawling
   ```

2. **크론잡 설정**
   - Supabase SQL Editor에서 `create_cron_jobs.sql` 실행

3. **동작 확인**
   - `cron_management.sql`의 쿼리들로 상태 확인

4. **모니터링 설정**
   - 실행 결과를 정기적으로 확인하는 대시보드 구성

## 📞 문제 해결

### "column "undefined" does not exist" 에러
**원인**: `YOUR_PROJECT_ID`나 `YOUR_SERVICE_ROLE_KEY`가 실제 값으로 교체되지 않음

**해결방법**:
1. `create_cron_jobs_template.sql` 사용
2. 실제 프로젝트 ID와 Service Role Key로 교체
3. 크론잡 재생성

```sql
-- 올바른 형식 예시
SELECT cron.schedule(
  'tiktok-metadata-crawling-daily',
  '0 2 * * *',
  $$
  SELECT
    net.http_post(
      'https://abcdefghijk.supabase.co/functions/v1/tiktok-metadata-crawling',
      '{}',
      'application/json',
      '{"Authorization": "Bearer eyJhbGciOiJIUzI1NiIs...", "Content-Type": "application/json"}'::jsonb
    ) as request_id;
  $$
);
```

### 크론잡이 실행되지 않는 경우
1. **pg_cron 확장 확인**: `SELECT * FROM pg_extension WHERE extname = 'pg_cron';`
2. **http 확장 확인**: `SELECT * FROM pg_extension WHERE extname = 'http';`
3. **Service Role Key 유효성**: Supabase 대시보드에서 재확인
4. **함수 URL 정확성**: 프로젝트 ID 확인

### 디버깅 단계
1. `debug_cron_errors.sql` 실행하여 상태 확인
2. 수동 HTTP 테스트로 함수 호출 확인
3. 크론잡 실행 로그 분석
4. 필요시 크론잡 재생성

### 함수 실행 오류
1. **환경 변수**: `COLLABEAUTY_BRAND_DOMAIN` 등 설정 확인
2. **함수 로그**: Supabase 대시보드에서 실시간 로그 모니터링
3. **권한 설정**: Service Role Key 권한 확인

### 긴급 복구 방법
```sql
-- 1. 기존 크론잡 삭제
SELECT cron.unschedule('tiktok-metadata-crawling-daily');

-- 2. 수동 함수 테스트
SELECT net.http_post(
  'https://YOUR_PROJECT.supabase.co/functions/v1/tiktok-metadata-crawling',
  '{}',
  'application/json',
  '{"Authorization": "Bearer YOUR_KEY"}'::jsonb
);

-- 3. 성공하면 크론잡 재생성
```

더 자세한 내용은 `supabase/queries/debug_cron_errors.sql`의 디버깅 쿼리들을 참고하세요.
