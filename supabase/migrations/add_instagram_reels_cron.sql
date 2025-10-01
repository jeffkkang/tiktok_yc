-- Instagram 릴 통계 업데이트 크론잡 추가

-- 기존 Instagram 릴 크론잡 삭제 (있는 경우)
SELECT cron.unschedule('instagram-reels-stats-hourly') WHERE EXISTS (
  SELECT 1 FROM cron.job WHERE jobname = 'instagram-reels-stats-hourly'
);
SELECT cron.unschedule('instagram-reels-stats-daily') WHERE EXISTS (
  SELECT 1 FROM cron.job WHERE jobname = 'instagram-reels-stats-daily'
);

-- Instagram 릴 API 통계 크론잡 (매일)
SELECT cron.schedule(
  'instagram-reels-stats-daily',
  '30 0 * * *', -- 매일 UTC 00:30 (한국시간 09:30)
  $$
  SELECT
    net.http_post(
      url := 'https://nscecbxechxejddkmtlc.supabase.co/functions/v1/instagram-reels-stats-api-only',
      body := '{}',
      headers := '{"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zY2VjYnhlY2h4ZWpkZGttdGxjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MjIyMTAwOSwiZXhwIjoyMDU3Nzk3MDA5fQ.hkr_j6pAyllTChgbsyZq68LZp-CaRlWQlhgRSOeFPKs", "Content-Type": "application/json"}'::jsonb
    ) as request_id;
  $$
);

-- 모든 크론잡 확인
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
    ELSE schedule
  END as description
FROM cron.job 
WHERE jobname LIKE '%instagram%' OR jobname LIKE '%tiktok%'
ORDER BY jobname;
