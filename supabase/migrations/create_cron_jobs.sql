-- TikTok 메타데이터 크롤링 크론잡 설정 (3회 분할 실행)
-- 각각 다른 시간에 실행하여 런타임 에러 최소화

-- pg_cron 확장 활성화 (필요한 경우)
-- 기존 크론잡 삭제 (있는 경우)
SELECT cron.unschedule('tiktok-metadata-crawling-1') WHERE EXISTS (
  SELECT 1 FROM cron.job WHERE jobname = 'tiktok-metadata-crawling-1'
);
SELECT cron.unschedule('tiktok-metadata-crawling-2') WHERE EXISTS (
  SELECT 1 FROM cron.job WHERE jobname = 'tiktok-metadata-crawling-2'
);
SELECT cron.unschedule('tiktok-metadata-crawling-3') WHERE EXISTS (
  SELECT 1 FROM cron.job WHERE jobname = 'tiktok-metadata-crawling-3'
);

-- 1. TikTok 메타데이터 크롤링 크론잡 #1 (매일 오전 2시)
SELECT cron.schedule(
  'tiktok-metadata-crawling-1',
  '0 2 * * *', -- 매일 UTC 02:00 (한국시간 11:00)
  $$
  SELECT
    net.http_post(
      url := 'https://nscecbxechxejddkmtlc.supabase.co/functions/v1/tiktok-metadata-crawling',
      body := '{}',
      headers := '{"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zY2VjYnhlY2h4ZWpkZGttdGxjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MjIyMTAwOSwiZXhwIjoyMDU3Nzk3MDA5fQ.hkr_j6pAyllTChgbsyZq68LZp-CaRlWQlhgRSOeFPKs", "Content-Type": "application/json"}'::jsonb
    ) as request_id;
  $$
);

-- 2. TikTok 메타데이터 크롤링 크론잡 #2 (매일 오전 2시 30분)
SELECT cron.schedule(
  'tiktok-metadata-crawling-2',
  '30 2 * * *', -- 매일 UTC 02:30 (한국시간 11:30)
  $$
  SELECT
    net.http_post(
      url := 'https://nscecbxechxejddkmtlc.supabase.co/functions/v1/tiktok-metadata-crawling',
      body := '{}',
      headers := '{"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zY2VjYnhlY2h4ZWpkZGttdGxjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MjIyMTAwOSwiZXhwIjoyMDU3Nzk3MDA5fQ.hkr_j6pAyllTChgbsyZq68LZp-CaRlWQlhgRSOeFPKs", "Content-Type": "application/json"}'::jsonb
    ) as request_id;
  $$
);

-- 3. TikTok 메타데이터 크롤링 크론잡 #3 (매일 오전 3시)
SELECT cron.schedule(
  'tiktok-metadata-crawling-3',
  '0 3 * * *', -- 매일 UTC 03:00 (한국시간 12:00)
  $$
  SELECT
    net.http_post(
      url := 'https://nscecbxechxejddkmtlc.supabase.co/functions/v1/tiktok-metadata-crawling',
      body := '{}',
      headers := '{"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5zY2VjYnhlY2h4ZWpkZGttdGxjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0MjIyMTAwOSwiZXhwIjoyMDU3Nzk3MDA5fQ.hkr_j6pAyllTChgbsyZq68LZp-CaRlWQlhgRSOeFPKs", "Content-Type": "application/json"}'::jsonb
    ) as request_id;
  $$
);

-- 크론잡 목록 확인
SELECT 
  jobname,
  schedule,
  active
FROM cron.job 
WHERE jobname LIKE 'tiktok-metadata-crawling-%'
ORDER BY jobname;
