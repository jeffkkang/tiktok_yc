-- user_instagram_account 테이블에 error_message 컬럼 추가 (선택사항)

-- error_message 컬럼 추가
ALTER TABLE user_instagram_account 
ADD COLUMN IF NOT EXISTS error_message TEXT;

-- 컬럼 추가 확인
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'user_instagram_account' 
  AND column_name = 'error_message';
