-- Instagram 토큰 리프레시 크론잡 업데이트
-- 실제 프로젝트 정보로 수정

-- 기존 크론잡 삭제
SELECT cron.unschedule('instagram_token_refresh_daily') WHERE EXISTS (
  SELECT 1 FROM cron.job WHERE jobname = 'instagram_token_refresh_daily'
);

-- Instagram 토큰 리프레시 크론잡 (매일 실행)
SELECT cron.schedule(
  'instagram_token_refresh_daily',
  '0 1 * * *', -- 매일 UTC 01:00 (한국시간 10:00)
  $$
  SELECT
    net.http_post(
      url := 'https://nscecbxechxejddkmtlc.supabase.co/functions/v1/instagram-token-refresh',
      body := '{}',
      headers := '{"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zY2VjYnhlY2h4ZWpkZGttdGxjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MjIyMTAwOSwiZXhwIjoyMDU3Nzk3MDA5fQ.hkr_j6pAyllTChgbsyZq68LZp-CaRlWQlhgRSOeFPKs", "Content-Type": "application/json"}'::jsonb
    ) as request_id;
  $$
);

-- 크론잡 등록 확인
SELECT 
  jobname,
  schedule,
  active,
  command
FROM cron.job 
WHERE jobname = 'instagram_token_refresh_daily';
