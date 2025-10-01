import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.21.0';

// 유틸리티 함수들
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const isValidToken = (token: string) => {
  return token && token.trim().length > 0 && !token.includes('undefined');
};

const calculateExpirationDate = (expiresIn: number) => {
  const expirationTime = Date.now() + expiresIn * 1000;
  return new Date(expirationTime).toISOString();
};

const classifyError = (error: any) => {
  const errorType = error?.error?.type || error?.error?.error_type || 'Unknown';
  const errorMessage = error?.error?.message || JSON.stringify(error);
  
  switch(errorType) {
    case 'OAuthException':
      return {
        type: 'OAUTH_ERROR',
        message: 'Token has been revoked or is invalid',
        shouldRetry: false
      };
    case 'IGApiException':
      return {
        type: 'API_ERROR',
        message: 'Instagram API temporary error',
        shouldRetry: true
      };
    case 'RateLimitExceeded':
      return {
        type: 'RATE_LIMIT',
        message: 'Rate limit exceeded',
        shouldRetry: true
      };
    default:
      return {
        type: 'UNKNOWN_ERROR',
        message: errorMessage,
        shouldRetry: true
      };
  }
};

// 재시도 로직이 포함된 토큰 갱신 함수
const refreshTokenWithRetry = async (account: any, maxRetries = 3) => {
  let lastError;
  
  for(let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`[IG Refresh] Attempt ${attempt}/${maxRetries} for user ${account.user_id}`);
      
      const url = `https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=${encodeURIComponent(account.access_token)}`;
      
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'User-Agent': 'Collabeauty-Instagram-Refresh/1.0'
        }
      });
      
      const responseData = await response.json().catch(() => ({}));
      
      if (!response.ok) {
        const errorInfo = classifyError(responseData);
        lastError = {
          ...errorInfo,
          httpStatus: response.status
        };
        
        if (!errorInfo.shouldRetry) {
          console.warn(`[IG Refresh] Non-retryable error for ${account.user_id}: ${errorInfo.type}`);
          return { success: false, error: lastError };
        }
        
        if (attempt < maxRetries) {
          const waitTime = Math.pow(2, attempt) * 1000;
          console.log(`[IG Refresh] Waiting ${waitTime}ms before retry...`);
          await delay(waitTime);
          continue;
        }
      } else {
        if (!responseData?.access_token) {
          return {
            success: false,
            error: {
              type: 'MISSING_TOKEN',
              message: 'No access_token in response'
            }
          };
        }
        
        return { success: true, data: responseData };
      }
    } catch (networkError) {
      lastError = {
        type: 'NETWORK_ERROR',
        message: networkError.message
      };
      console.error(`[IG Refresh] Network error on attempt ${attempt}:`, networkError);
      
      if (attempt < maxRetries) {
        await delay(2000 * attempt);
      }
    }
  }
  
  return { success: false, error: lastError };
};

// 메인 서비스 함수
serve(async (req) => {
  const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? '';
  const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
  const thresholdDays = Number(Deno.env.get('IG_REFRESH_THRESHOLD_DAYS') || '10');
  const batchSize = Number(Deno.env.get('IG_REFRESH_BATCH_SIZE') || '50');
  const rateLimitDelay = Number(Deno.env.get('IG_RATE_LIMIT_DELAY') || '1000');
  
  const authHeader = req.headers.get('Authorization');
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return new Response(JSON.stringify({
      success: false,
      error: 'Missing or invalid Authorization header'
    }), {
      status: 401,
      headers: { 'Content-Type': 'application/json' }
    });
  }
  
  const supabase = createClient(supabaseUrl, supabaseKey);
  
  try {
    console.log(`[IG Cron] Starting token refresh process at ${new Date().toISOString()}`);
    
    const now = new Date();
    const thresholdISO = new Date(now.getTime() + thresholdDays * 86400000).toISOString();
    console.log(`[IG Cron] Threshold: ${thresholdDays} days (${thresholdISO})`);
    
    const { data: accounts, error } = await supabase
      .from('user_instagram_account')
      .select('user_id, access_token, access_expires_at, instagram_user_id')
      .not('access_token', 'is', null)
      .or(`access_expires_at.is.null,access_expires_at.lt.${thresholdISO}`)
      .limit(batchSize);
    
    if (error) {
      console.error('[IG Cron] Database query failed:', error);
      return new Response(JSON.stringify({
        success: false,
        error: 'Database query failed',
        details: error.message
      }), {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    if (!accounts || accounts.length === 0) {
      console.log('[IG Cron] No accounts need token refresh');
      return new Response(JSON.stringify({
        success: true,
        refreshed: 0,
        failed: 0,
        total: 0,
        successRate: '100%',
        message: 'No accounts need refresh'
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      });
    }
    
    console.log(`[IG Cron] Found ${accounts.length} accounts to refresh`);
    
    let refreshed = 0;
    let failed = 0;
    const errors = [];
    
    for(let i = 0; i < accounts.length; i++) {
      const account = accounts[i];
      
      try {
        if (!isValidToken(account.access_token)) {
          console.warn(`[IG Cron] Invalid token for user ${account.user_id}`);
          failed++;
          errors.push({
            user_id: account.user_id,
            error_type: 'INVALID_TOKEN',
            message: 'Token is empty or invalid'
          });
          continue;
        }
        
        const refreshResult = await refreshTokenWithRetry(account);
        
        if (!refreshResult.success) {
          failed++;
          errors.push({
            user_id: account.user_id,
            error_type: refreshResult.error?.type || 'UNKNOWN',
            message: refreshResult.error?.message || 'Unknown error'
          });
          
          // OAuth 에러인 경우 토큰 무효화 (error_message 필드 제거)
          if (refreshResult.error?.type === 'OAUTH_ERROR') {
            console.log(`[IG Cron] Invalidating token for user ${account.user_id}`);
            await supabase
              .from('user_instagram_account')
              .update({
                access_token: null,
                access_expires_at: null,
                updated_at: new Date().toISOString()
                // error_message 필드 제거
              })
              .eq('user_id', account.user_id);
          }
          continue;
        }
        
        const tokenData = refreshResult.data;
        const updates: any = {
          access_token: tokenData.access_token,
          updated_at: new Date().toISOString(),
          last_refreshed_at: new Date().toISOString()
          // error_message 필드 제거
        };
        
        if (typeof tokenData.expires_in === 'number' && Number.isFinite(tokenData.expires_in)) {
          updates.access_expires_at = calculateExpirationDate(tokenData.expires_in);
          console.log(`[IG Cron] Token for user ${account.user_id} will expire at ${updates.access_expires_at}`);
        }
        
        const { error: updateError } = await supabase
          .from('user_instagram_account')
          .update(updates)
          .eq('user_id', account.user_id);
        
        if (updateError) {
          console.error(`[IG Cron] Database update failed for ${account.user_id}:`, updateError);
          failed++;
          errors.push({
            user_id: account.user_id,
            error_type: 'DATABASE_ERROR',
            message: updateError.message
          });
          continue;
        }
        
        refreshed++;
        console.log(`[IG Cron] Successfully refreshed token for user ${account.user_id}`);
        
      } catch (unexpectedError) {
        console.error(`[IG Cron] Unexpected error for user ${account.user_id}:`, unexpectedError);
        failed++;
        errors.push({
          user_id: account.user_id,
          error_type: 'UNEXPECTED_ERROR',
          message: unexpectedError.message || 'Unexpected error occurred'
        });
      }
      
      // 요청 간 지연
      if (i < accounts.length - 1) {
        await delay(rateLimitDelay);
      }
    }
    
    const total = accounts.length;
    const successRate = total > 0 ? (refreshed / total * 100).toFixed(2) + '%' : '100%';
    
    const result = {
      success: true,
      refreshed,
      failed,
      total,
      successRate,
      errors: errors.slice(0, 10), // 최대 10개 에러만 포함
      timestamp: new Date().toISOString()
    };
    
    const successRateNum = parseFloat(successRate);
    if (successRateNum < 80 && total > 0) {
      console.warn(`[IG Cron] Low success rate: ${successRate} (${refreshed}/${total})`);
    }
    
    console.log(`[IG Cron] Process completed: ${refreshed} refreshed, ${failed} failed, ${total} total (${successRate} success rate)`);
    
    if (errors.length > 0) {
      const errorSummary = errors.reduce((acc: any, err: any) => {
        acc[err.error_type] = (acc[err.error_type] || 0) + 1;
        return acc;
      }, {});
      console.log('[IG Cron] Error summary:', errorSummary);
    }
    
    return new Response(JSON.stringify(result), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    });
    
  } catch (fatalError) {
    console.error('[IG Cron] Fatal error:', fatalError);
    return new Response(JSON.stringify({
      success: false,
      error: 'Fatal error occurred',
      details: fatalError.message,
      timestamp: new Date().toISOString()
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
});
