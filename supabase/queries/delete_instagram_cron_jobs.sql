-- Instagram 관련 Cron Job 삭제 쿼리
-- 실행 전에 현재 등록된 cron job 목록을 확인하세요

-- 1. 현재 등록된 모든 cron job 조회
SELECT 
    jobname,
    schedule,
    active,
    command,
    created_at
FROM cron.job 
WHERE jobname LIKE '%instagram%'
ORDER BY jobname;

-- 2. Instagram Stats Daily Cron Job 삭제
SELECT cron.unschedule('instagram-stats-daily') 
WHERE EXISTS (
    SELECT 1 FROM cron.job 
    WHERE jobname = 'instagram-stats-daily'
);

-- 3. Instagram Reels Stats Daily Cron Job 삭제
SELECT cron.unschedule('instagram-reels-stats-daily') 
WHERE EXISTS (
    SELECT 1 FROM cron.job 
    WHERE jobname = 'instagram-reels-stats-daily'
);

-- 4. Instagram Token Refresh Daily Cron Job 삭제 (필요한 경우)
SELECT cron.unschedule('instagram_token_refresh_daily') 
WHERE EXISTS (
    SELECT 1 FROM cron.job 
    WHERE jobname = 'instagram_token_refresh_daily'
);

-- 5. 삭제 후 확인 - Instagram 관련 cron job이 모두 삭제되었는지 확인
SELECT 
    jobname,
    schedule,
    active,
    command
FROM cron.job 
WHERE jobname LIKE '%instagram%'
ORDER BY jobname;

-- 6. 모든 cron job 목록 조회 (전체 확인용)
SELECT 
    jobname,
    schedule,
    active,
    command
FROM cron.job 
ORDER BY jobname;
