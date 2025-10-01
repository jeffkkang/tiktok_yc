-- 전체 크론잡 관리 쿼리 (Instagram 릴 + TikTok + Instagram 토큰)

-- ============================================
-- 전체 크론잡 상태 확인
-- ============================================

-- 1. 모든 크론잡 상태 한눈에 보기
SELECT 
  jobname,
  schedule,
  active,
  CASE jobname
    WHEN 'instagram-reels-stats-daily' THEN 'UTC 00:30 (한국 09:30) - Instagram 릴 통계'
    WHEN 'instagram_token_refresh_daily' THEN 'UTC 01:00 (한국 10:00) - Instagram 토큰 리프레시'
    WHEN 'tiktok-metadata-crawling-1' THEN 'UTC 02:00 (한국 11:00) - TikTok 크롤링 #1'
    WHEN 'tiktok-metadata-crawling-2' THEN 'UTC 02:30 (한국 11:30) - TikTok 크롤링 #2'
    WHEN 'tiktok-metadata-crawling-3' THEN 'UTC 03:00 (한국 12:00) - TikTok 크롤링 #3'
    ELSE schedule || ' - ' || jobname
  END as description,
  command
FROM cron.job 
WHERE jobname LIKE '%instagram%' OR jobname LIKE '%tiktok%'
ORDER BY 
  CASE 
    WHEN jobname LIKE '%instagram_token%' THEN 1
    WHEN jobname LIKE '%instagram-reels%' THEN 2
    WHEN jobname LIKE '%tiktok%' THEN 3
    ELSE 4
  END, jobname;

-- 2. 최근 24시간 실행 기록 (모든 크론잡)
SELECT 
  j.jobname,
  jr.status,
  jr.start_time,
  jr.end_time,
  EXTRACT(EPOCH FROM (jr.end_time - jr.start_time)) as duration_seconds,
  LEFT(jr.return_message, 100) as return_message_preview
FROM cron.job j
LEFT JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE (j.jobname LIKE '%instagram%' OR j.jobname LIKE '%tiktok%')
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
WHERE (j.jobname LIKE '%instagram%' OR j.jobname LIKE '%tiktok%')
  AND jr.start_time >= NOW() - INTERVAL '7 days'
GROUP BY j.jobname
ORDER BY j.jobname;

-- ============================================
-- 데이터 업데이트 현황
-- ============================================

-- 4. Instagram 릴 업데이트 현황
SELECT 
  DATE_TRUNC('hour', updated_at) as update_hour,
  COUNT(*) as reels_updated,
  AVG(view_count::numeric) as avg_views,
  AVG(like_count::numeric) as avg_likes,
  AVG(reach_count::numeric) as avg_reach
FROM campaign_application_reels 
WHERE DATE(updated_at) = CURRENT_DATE
GROUP BY DATE_TRUNC('hour', updated_at)
ORDER BY update_hour DESC;

-- 5. TikTok 비디오 업데이트 현황
SELECT 
  DATE_TRUNC('hour', updated_at) as update_hour,
  COUNT(*) as videos_updated,
  AVG(view_count::numeric) as avg_views,
  AVG(like_count::numeric) as avg_likes,
  COUNT(CASE WHEN metadata_updated_at >= NOW() - INTERVAL '1 day' THEN 1 END) as metadata_updated_today
FROM campaign_application_videos 
WHERE DATE(updated_at) = CURRENT_DATE
GROUP BY DATE_TRUNC('hour', updated_at)
ORDER BY update_hour DESC;

-- 6. Instagram 토큰 상태 요약
SELECT 
  'Instagram Tokens' as category,
  COUNT(*) as total_accounts,
  COUNT(CASE WHEN access_token IS NOT NULL THEN 1 END) as accounts_with_token,
  COUNT(CASE WHEN access_expires_at > NOW() THEN 1 END) as accounts_with_valid_token,
  COUNT(CASE WHEN access_expires_at <= NOW() + INTERVAL '10 days' THEN 1 END) as accounts_expiring_soon
FROM user_instagram_account;

-- ============================================
-- 크론잡 제어
-- ============================================

-- 7. 모든 크론잡 중지 (긴급시)
/*
SELECT cron.unschedule('instagram_token_refresh_daily');
SELECT cron.unschedule('instagram-reels-stats-daily');
SELECT cron.unschedule('tiktok-metadata-crawling-1');
SELECT cron.unschedule('tiktok-metadata-crawling-2');
SELECT cron.unschedule('tiktok-metadata-crawling-3');
*/

-- 8. 특정 크론잡만 중지
/*
-- Instagram 관련만 중지
SELECT cron.unschedule('instagram_token_refresh_daily');
SELECT cron.unschedule('instagram-reels-stats-daily');

-- TikTok 관련만 중지
SELECT cron.unschedule('tiktok-metadata-crawling-1');
SELECT cron.unschedule('tiktok-metadata-crawling-2');
SELECT cron.unschedule('tiktok-metadata-crawling-3');
*/

-- ============================================
-- 실행 스케줄 분석
-- ============================================

-- 9. 시간대별 크론잡 실행 현황
SELECT 
  EXTRACT(HOUR FROM jr.start_time) as hour_utc,
  EXTRACT(HOUR FROM jr.start_time) + 9 as hour_korean, -- UTC+9
  j.jobname,
  COUNT(*) as executions,
  AVG(EXTRACT(EPOCH FROM (jr.end_time - jr.start_time))) as avg_duration_seconds
FROM cron.job j
JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE (j.jobname LIKE '%instagram%' OR j.jobname LIKE '%tiktok%')
  AND jr.start_time >= NOW() - INTERVAL '7 days'
  AND jr.end_time IS NOT NULL
GROUP BY EXTRACT(HOUR FROM jr.start_time), j.jobname
ORDER BY hour_utc, j.jobname;

-- 10. 동시 실행 충돌 확인
SELECT 
  DATE_TRUNC('minute', jr.start_time) as execution_minute,
  COUNT(*) as concurrent_jobs,
  string_agg(j.jobname, ', ') as running_jobs
FROM cron.job j
JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE (j.jobname LIKE '%instagram%' OR j.jobname LIKE '%tiktok%')
  AND jr.start_time >= NOW() - INTERVAL '24 hours'
GROUP BY DATE_TRUNC('minute', jr.start_time)
HAVING COUNT(*) > 1  -- 동시 실행된 경우만
ORDER BY execution_minute DESC;

-- ============================================
-- 에러 분석
-- ============================================

-- 11. 최근 실패한 크론잡들
SELECT 
  j.jobname,
  jr.start_time,
  jr.return_message,
  CASE 
    WHEN jr.return_message LIKE '%undefined%' THEN 'SQL 구문 오류'
    WHEN jr.return_message LIKE '%timeout%' THEN '타임아웃 오류'
    WHEN jr.return_message LIKE '%connection%' THEN '연결 오류'
    WHEN jr.return_message LIKE '%token%' THEN '토큰 오류'
    WHEN jr.return_message LIKE '%rate%' THEN '요청 제한 오류'
    ELSE '기타 오류'
  END as error_category
FROM cron.job j
JOIN cron.job_run_details jr ON j.jobid = jr.jobid
WHERE (j.jobname LIKE '%instagram%' OR j.jobname LIKE '%tiktok%')
  AND jr.status = 'failed'
  AND jr.start_time >= NOW() - INTERVAL '24 hours'
ORDER BY jr.start_time DESC;

-- ============================================
-- 시스템 전체 상태 대시보드
-- ============================================

-- 12. 전체 시스템 상태 요약
SELECT 
  json_build_object(
    'cron_jobs', json_build_object(
      'total_active', (
        SELECT COUNT(*) 
        FROM cron.job 
        WHERE (jobname LIKE '%instagram%' OR jobname LIKE '%tiktok%') AND active = true
      ),
      'last_24h_successful', (
        SELECT COUNT(*) 
        FROM cron.job j
        JOIN cron.job_run_details jr ON j.jobid = jr.jobid
        WHERE (j.jobname LIKE '%instagram%' OR j.jobname LIKE '%tiktok%')
          AND jr.status = 'succeeded'
          AND jr.start_time >= NOW() - INTERVAL '24 hours'
      ),
      'last_24h_failed', (
        SELECT COUNT(*) 
        FROM cron.job j
        JOIN cron.job_run_details jr ON j.jobid = jr.jobid
        WHERE (j.jobname LIKE '%instagram%' OR j.jobname LIKE '%tiktok%')
          AND jr.status = 'failed'
          AND jr.start_time >= NOW() - INTERVAL '24 hours'
      )
    ),
    'instagram', json_build_object(
      'accounts_with_valid_tokens', (
        SELECT COUNT(*) 
        FROM user_instagram_account 
        WHERE access_token IS NOT NULL AND access_expires_at > NOW()
      ),
      'reels_updated_today', (
        SELECT COUNT(*) 
        FROM campaign_application_reels 
        WHERE DATE(updated_at) = CURRENT_DATE
      )
    ),
    'tiktok', json_build_object(
      'accounts_with_valid_tokens', (
        SELECT COUNT(*) 
        FROM user_tiktok_account 
        WHERE access_token IS NOT NULL AND access_expires_at > NOW()
      ),
      'videos_updated_today', (
        SELECT COUNT(*) 
        FROM campaign_application_videos 
        WHERE DATE(updated_at) = CURRENT_DATE
      ),
      'metadata_updated_today', (
        SELECT COUNT(*) 
        FROM campaign_application_videos 
        WHERE DATE(metadata_updated_at) = CURRENT_DATE
      )
    )
  ) as system_status;
