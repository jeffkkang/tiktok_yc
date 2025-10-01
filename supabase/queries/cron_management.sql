-- TikTok 크론잡 관리 쿼리들

-- ================================
-- 크론잡 확인 및 관리
-- ================================

-- 1. 현재 등록된 모든 크론잡 확인
SELECT 
  jobid,
  schedule,
  command,
  nodename,
  nodeport,
  database,
  username,
  active,
  jobname
FROM cron.job 
WHERE jobname LIKE '%tiktok%'
ORDER BY jobname;

-- 2. 크론잡 실행 기록 확인 (최근 10개)
SELECT 
  runid,
  job_pid,
  database,
  username,
  command,
  status,
  return_message,
  start_time,
  end_time
FROM cron.job_run_details 
WHERE command LIKE '%tiktok%'
ORDER BY start_time DESC 
LIMIT 10;

-- 3. 특정 크론잡의 최근 실행 상태
SELECT 
  j.jobname,
  j.schedule,
  j.active,
  jr.status,
  jr.return_message,
  jr.start_time,
  jr.end_time,
  EXTRACT(EPOCH FROM (jr.end_time - jr.start_time)) as duration_seconds
FROM cron.job j
LEFT JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE j.jobname IN ('tiktok-metadata-crawling-daily', 'tiktok-stats-api-hourly')
ORDER BY jr.start_time DESC;

-- ================================
-- 크론잡 제어
-- ================================

-- 4. 메타데이터 크롤링 크론잡 중지
-- SELECT cron.unschedule('tiktok-metadata-crawling-daily');

-- 5. API 통계 크론잡 중지
-- SELECT cron.unschedule('tiktok-stats-api-hourly');

-- 6. 크론잡 다시 시작 (스케줄 재설정)
/*
SELECT cron.schedule(
  'tiktok-metadata-crawling-daily',
  '0 2 * * *',
  $$
  SELECT
    net.http_post(
      url := 'https://YOUR_PROJECT_ID.supabase.co/functions/v1/tiktok-metadata-crawling',
      headers := '{"Content-Type": "application/json", "Authorization": "Bearer YOUR_SERVICE_ROLE_KEY"}'::jsonb,
      body := '{}'::jsonb
    ) as request_id;
  $$
);
*/

-- ================================
-- 메타데이터 업데이트 통계 확인
-- ================================

-- 7. 최근 메타데이터 업데이트 현황
SELECT 
  DATE(metadata_updated_at) as update_date,
  COUNT(*) as videos_updated,
  COUNT(DISTINCT campaign_application_id) as applications_affected
FROM campaign_application_videos 
WHERE metadata_updated_at >= NOW() - INTERVAL '7 days'
  AND metadata_updated_at IS NOT NULL
GROUP BY DATE(metadata_updated_at)
ORDER BY update_date DESC;

-- 8. 메타데이터 업데이트가 필요한 비디오 수
SELECT 
  CASE 
    WHEN metadata_updated_at IS NULL THEN 'Never updated'
    WHEN metadata_updated_at < NOW() - INTERVAL '1 day' THEN 'Needs update (>1 day)'
    ELSE 'Recently updated (<1 day)'
  END as update_status,
  COUNT(*) as video_count
FROM campaign_application_videos cav
JOIN campaign_applications ca ON cav.campaign_application_id = ca.id
WHERE ca.status = 'UPLOADED'
  AND ca.created_at >= NOW() - INTERVAL '30 days'
  AND cav.video_url IS NOT NULL
GROUP BY update_status;

-- 9. 사용자별 TikTok 토큰 상태
SELECT 
  u.id as user_id,
  u.email,
  uta.username as tiktok_username,
  CASE 
    WHEN uta.access_token IS NULL THEN 'No token'
    WHEN uta.access_expires_at < NOW() THEN 'Access token expired'
    WHEN uta.refresh_expires_at < NOW() THEN 'Refresh token expired'
    ELSE 'Valid'
  END as token_status,
  uta.access_expires_at,
  uta.refresh_expires_at
FROM users u
JOIN user_tiktok_account uta ON u.id = uta.user_id
WHERE EXISTS (
  SELECT 1 FROM campaign_applications ca 
  WHERE ca.user_id = u.id 
    AND ca.status = 'UPLOADED'
    AND ca.created_at >= NOW() - INTERVAL '30 days'
);

-- ================================
-- 성능 모니터링
-- ================================

-- 10. 크론잡 실행 시간 분석
SELECT 
  j.jobname,
  COUNT(jr.runid) as total_runs,
  AVG(EXTRACT(EPOCH FROM (jr.end_time - jr.start_time))) as avg_duration_seconds,
  MIN(EXTRACT(EPOCH FROM (jr.end_time - jr.start_time))) as min_duration_seconds,
  MAX(EXTRACT(EPOCH FROM (jr.end_time - jr.start_time))) as max_duration_seconds,
  COUNT(CASE WHEN jr.status = 'succeeded' THEN 1 END) as successful_runs,
  COUNT(CASE WHEN jr.status = 'failed' THEN 1 END) as failed_runs
FROM cron.job j
LEFT JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE j.jobname LIKE '%tiktok%'
  AND jr.start_time >= NOW() - INTERVAL '7 days'
GROUP BY j.jobname;

-- ================================
-- 문제 해결 도구
-- ================================

-- 11. 실패한 크론잡 실행 분석
SELECT 
  j.jobname,
  jr.status,
  jr.return_message,
  jr.start_time,
  jr.end_time,
  jr.command
FROM cron.job j
JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE j.jobname LIKE '%tiktok%'
  AND jr.status = 'failed'
  AND jr.start_time >= NOW() - INTERVAL '24 hours'
ORDER BY jr.start_time DESC;

-- 12. 비디오 업데이트 실패 패턴 분석
SELECT 
  DATE(updated_at) as update_date,
  COUNT(*) as total_attempts,
  COUNT(CASE WHEN like_count > 0 OR comment_count > 0 THEN 1 END) as successful_updates,
  COUNT(CASE WHEN metadata_updated_at IS NOT NULL THEN 1 END) as metadata_updates
FROM campaign_application_videos
WHERE updated_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(updated_at)
ORDER BY update_date DESC;
