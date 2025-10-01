-- 3회 분할 TikTok 메타데이터 크롤링 크론잡 관리 쿼리

-- ============================================
-- 크론잡 상태 확인
-- ============================================

-- 1. 모든 TikTok 크롤링 크론잡 상태
SELECT 
  jobname,
  schedule,
  active,
  CASE jobname
    WHEN 'tiktok-metadata-crawling-1' THEN 'UTC 02:00 (한국 11:00)'
    WHEN 'tiktok-metadata-crawling-2' THEN 'UTC 02:30 (한국 11:30)'
    WHEN 'tiktok-metadata-crawling-3' THEN 'UTC 03:00 (한국 12:00)'
  END as korean_time,
  command
FROM cron.job 
WHERE jobname LIKE 'tiktok-metadata-crawling-%'
ORDER BY jobname;

-- 2. 최근 실행 기록 (모든 크론잡)
SELECT 
  j.jobname,
  jr.status,
  jr.start_time,
  jr.end_time,
  EXTRACT(EPOCH FROM (jr.end_time - jr.start_time)) as duration_seconds,
  jr.return_message
FROM cron.job j
LEFT JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE j.jobname LIKE 'tiktok-metadata-crawling-%'
  AND jr.start_time >= NOW() - INTERVAL '24 hours'
ORDER BY jr.start_time DESC;

-- 3. 크론잡별 성공률 (최근 7일)
SELECT 
  j.jobname,
  COUNT(jr.runid) as total_runs,
  COUNT(CASE WHEN jr.status = 'succeeded' THEN 1 END) as successful_runs,
  COUNT(CASE WHEN jr.status = 'failed' THEN 1 END) as failed_runs,
  ROUND(
    COUNT(CASE WHEN jr.status = 'succeeded' THEN 1 END) * 100.0 / NULLIF(COUNT(jr.runid), 0), 
    2
  ) as success_rate_percent,
  AVG(EXTRACT(EPOCH FROM (jr.end_time - jr.start_time))) as avg_duration_seconds
FROM cron.job j
LEFT JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE j.jobname LIKE 'tiktok-metadata-crawling-%'
  AND jr.start_time >= NOW() - INTERVAL '7 days'
GROUP BY j.jobname
ORDER BY j.jobname;

-- ============================================
-- 크론잡 제어
-- ============================================

-- 4. 모든 크론잡 중지
/*
SELECT cron.unschedule('tiktok-metadata-crawling-1');
SELECT cron.unschedule('tiktok-metadata-crawling-2');  
SELECT cron.unschedule('tiktok-metadata-crawling-3');
*/

-- 5. 특정 크론잡만 중지 (예: 크론잡 #2)
/*
SELECT cron.unschedule('tiktok-metadata-crawling-2');
*/

-- 6. 크론잡 재시작 (예: 크론잡 #1)
/*
SELECT cron.schedule(
  'tiktok-metadata-crawling-1',
  '0 2 * * *',
  $$
  SELECT
    net.http_post(
      url := 'https://nscecbxechxejddkmtlc.supabase.co/functions/v1/tiktok-metadata-crawling',
      body := '{}',
      headers := '{"Authorization": "Bearer YOUR_KEY", "Content-Type": "application/json"}'::jsonb
    ) as request_id;
  $$
);
*/

-- ============================================
-- 메타데이터 업데이트 현황
-- ============================================

-- 7. 오늘 메타데이터 업데이트 현황
SELECT 
  DATE_TRUNC('hour', metadata_updated_at) as update_hour,
  COUNT(*) as videos_updated
FROM campaign_application_videos 
WHERE DATE(metadata_updated_at) = CURRENT_DATE
GROUP BY DATE_TRUNC('hour', metadata_updated_at)
ORDER BY update_hour;

-- 8. 업데이트 대기 중인 비디오 수
SELECT 
  COUNT(*) as videos_needing_update
FROM campaign_application_videos cav
JOIN campaign_applications ca ON cav.campaign_application_id = ca.id
WHERE ca.status = 'UPLOADED'
  AND ca.created_at >= NOW() - INTERVAL '30 days'
  AND cav.video_url IS NOT NULL
  AND (cav.metadata_updated_at IS NULL 
       OR cav.metadata_updated_at < NOW() - INTERVAL '1 day');

-- ============================================
-- 실행 스케줄 분석
-- ============================================

-- 9. 다음 실행 예정 시간 (추정)
WITH next_runs AS (
  SELECT 
    'tiktok-metadata-crawling-1' as jobname,
    '0 2 * * *' as schedule,
    'UTC 02:00 (한국 11:00)' as korean_time
  UNION ALL
  SELECT 
    'tiktok-metadata-crawling-2',
    '30 2 * * *',
    'UTC 02:30 (한국 11:30)'
  UNION ALL
  SELECT 
    'tiktok-metadata-crawling-3',
    '0 3 * * *',
    'UTC 03:00 (한국 12:00)'
)
SELECT 
  nr.jobname,
  nr.schedule,
  nr.korean_time,
  j.active,
  CASE 
    WHEN j.active THEN '다음 실행 예정'
    ELSE '비활성화됨'
  END as status
FROM next_runs nr
LEFT JOIN cron.job j ON nr.jobname = j.jobname
ORDER BY nr.jobname;

-- ============================================
-- 문제 진단
-- ============================================

-- 10. 실패한 실행들의 에러 분석
SELECT 
  j.jobname,
  jr.start_time,
  jr.return_message,
  CASE 
    WHEN jr.return_message LIKE '%undefined%' THEN 'SQL 구문 오류'
    WHEN jr.return_message LIKE '%timeout%' THEN '타임아웃 오류'
    WHEN jr.return_message LIKE '%connection%' THEN '연결 오류'
    ELSE '기타 오류'
  END as error_type
FROM cron.job j
JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE j.jobname LIKE 'tiktok-metadata-crawling-%'
  AND jr.status = 'failed'
  AND jr.start_time >= NOW() - INTERVAL '24 hours'
ORDER BY jr.start_time DESC;

-- 11. 크론잡 실행 간격 분석 (같은 시간에 여러 개가 실행되는지 확인)
SELECT 
  DATE_TRUNC('minute', jr.start_time) as execution_minute,
  COUNT(*) as concurrent_jobs,
  string_agg(j.jobname, ', ') as running_jobs
FROM cron.job j
JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE j.jobname LIKE 'tiktok-metadata-crawling-%'
  AND jr.start_time >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('minute', jr.start_time)
HAVING COUNT(*) > 1  -- 동시 실행된 경우만
ORDER BY execution_minute DESC;

-- ============================================
-- 수동 테스트
-- ============================================

-- 12. 크롤링 함수 수동 실행 (테스트용)
/*
SELECT
  net.http_post(
    url := 'https://nscecbxechxejddkmtlc.supabase.co/functions/v1/tiktok-metadata-crawling',
    body := '{}',
    headers := '{"Authorization": "Bearer YOUR_KEY", "Content-Type": "application/json"}'::jsonb
  ) as manual_test_result;
*/

-- ============================================
-- 성능 최적화 정보
-- ============================================

-- 13. 시간대별 크론잡 부하 분석
SELECT 
  EXTRACT(HOUR FROM jr.start_time) as hour_utc,
  EXTRACT(HOUR FROM jr.start_time) + 9 as hour_korean, -- UTC+9
  COUNT(*) as job_executions,
  AVG(EXTRACT(EPOCH FROM (jr.end_time - jr.start_time))) as avg_duration_seconds
FROM cron.job j
JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE j.jobname LIKE 'tiktok-metadata-crawling-%'
  AND jr.start_time >= NOW() - INTERVAL '7 days'
  AND jr.end_time IS NOT NULL
GROUP BY EXTRACT(HOUR FROM jr.start_time)
ORDER BY hour_utc;

-- 14. 전체 시스템 상태 요약
SELECT 
  json_build_object(
    'active_cron_jobs', (
      SELECT COUNT(*) 
      FROM cron.job 
      WHERE jobname LIKE 'tiktok-metadata-crawling-%' AND active = true
    ),
    'videos_needing_update', (
      SELECT COUNT(*) 
      FROM campaign_application_videos cav
      JOIN campaign_applications ca ON cav.campaign_application_id = ca.id
      WHERE ca.status = 'UPLOADED'
        AND ca.created_at >= NOW() - INTERVAL '30 days'
        AND cav.video_url IS NOT NULL
        AND (cav.metadata_updated_at IS NULL OR cav.metadata_updated_at < NOW() - INTERVAL '1 day')
    ),
    'last_24h_successful_runs', (
      SELECT COUNT(*) 
      FROM cron.job j
      JOIN cron.job_run_details jr ON j.jobid = jr.jobid
      WHERE j.jobname LIKE 'tiktok-metadata-crawling-%'
        AND jr.status = 'succeeded'
        AND jr.start_time >= NOW() - INTERVAL '24 hours'
    ),
    'last_24h_failed_runs', (
      SELECT COUNT(*) 
      FROM cron.job j
      JOIN cron.job_run_details jr ON j.jobid = jr.jobid
      WHERE j.jobname LIKE 'tiktok-metadata-crawling-%'
        AND jr.status = 'failed'
        AND jr.start_time >= NOW() - INTERVAL '24 hours'
    ),
    'last_metadata_update', (
      SELECT MAX(metadata_updated_at)
      FROM campaign_application_videos
      WHERE metadata_updated_at IS NOT NULL
    )
  ) as system_status;
