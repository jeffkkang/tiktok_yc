-- Instagram Cron Jobs 빠른 삭제 (단일 명령어)

-- 방법 1: 조건부 삭제 (권장) - 수정된 버전
DO $$
DECLARE
    job_exists boolean;
BEGIN
    -- instagram-stats-daily 삭제
    SELECT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'instagram-stats-daily') INTO job_exists;
    IF job_exists THEN
        PERFORM cron.unschedule('instagram-stats-daily');
        RAISE NOTICE 'instagram-stats-daily cron job deleted';
    ELSE
        RAISE NOTICE 'instagram-stats-daily cron job not found';
    END IF;

    -- instagram-reels-stats-daily 삭제  
    SELECT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'instagram-reels-stats-daily') INTO job_exists;
    IF job_exists THEN
        PERFORM cron.unschedule('instagram-reels-stats-daily');
        RAISE NOTICE 'instagram-reels-stats-daily cron job deleted';
    ELSE
        RAISE NOTICE 'instagram-reels-stats-daily cron job not found';
    END IF;

    -- instagram_token_refresh_daily 삭제 (필요한 경우)
    SELECT EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'instagram_token_refresh_daily') INTO job_exists;
    IF job_exists THEN
        PERFORM cron.unschedule('instagram_token_refresh_daily');
        RAISE NOTICE 'instagram_token_refresh_daily cron job deleted';
    ELSE
        RAISE NOTICE 'instagram_token_refresh_daily cron job not found';
    END IF;
END $$;

-- 방법 2: 강제 삭제 (에러 무시)
-- 주의: 존재하지 않는 cron job을 삭제하려고 하면 에러가 발생할 수 있음

-- SELECT cron.unschedule('instagram-stats-daily');
-- SELECT cron.unschedule('instagram-reels-stats-daily'); 
-- SELECT cron.unschedule('instagram_token_refresh_daily');

-- 삭제 확인
SELECT 'Remaining Instagram cron jobs:' as status;
SELECT 
    jobname,
    schedule,
    active
FROM cron.job 
WHERE jobname LIKE '%instagram%'
ORDER BY jobname;
