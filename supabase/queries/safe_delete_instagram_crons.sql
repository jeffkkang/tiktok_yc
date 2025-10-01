-- 가장 안전한 Instagram Cron Job 삭제 방법
-- 에러 방지를 위한 TRY-CATCH 패턴 사용

-- 1. 현재 Instagram 관련 cron job 확인
SELECT 
    'Current Instagram cron jobs:' as info,
    jobname, 
    schedule, 
    active
FROM cron.job 
WHERE jobname LIKE '%instagram%' 
OR jobname LIKE '%reels%'
ORDER BY jobname;

-- 2. 안전한 삭제 (각각 개별 실행 권장)

-- 2-1. instagram-stats-daily 삭제 (개별 실행)
DO $$
BEGIN
    BEGIN
        PERFORM cron.unschedule('instagram-stats-daily');
        RAISE NOTICE 'Successfully deleted: instagram-stats-daily';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Job not found or already deleted: instagram-stats-daily';
    END;
END $$;

-- 2-2. instagram-reels-stats-daily 삭제 (개별 실행)
DO $$
BEGIN
    BEGIN
        PERFORM cron.unschedule('instagram-reels-stats-daily');
        RAISE NOTICE 'Successfully deleted: instagram-reels-stats-daily';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Job not found or already deleted: instagram-reels-stats-daily';
    END;
END $$;

-- 2-3. instagram_token_refresh_daily 삭제 (개별 실행)
DO $$
BEGIN
    BEGIN
        PERFORM cron.unschedule('instagram_token_refresh_daily');
        RAISE NOTICE 'Successfully deleted: instagram_token_refresh_daily';
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'Job not found or already deleted: instagram_token_refresh_daily';
    END;
END $$;

-- 3. 삭제 후 확인
SELECT 
    'Remaining Instagram cron jobs after deletion:' as info,
    jobname, 
    schedule, 
    active
FROM cron.job 
WHERE jobname LIKE '%instagram%' 
OR jobname LIKE '%reels%'
ORDER BY jobname;
