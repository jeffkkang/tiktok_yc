// TikTok API 전용 비디오 통계 업데이트 함수 (크롤링 제외)
// supabase edge function
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.21.0';

/**
 * TikTok 액세스 토큰이 만료되었는지 확인하는 함수
 */
function isTokenExpired(expiresAt: string | null): boolean {
  if (!expiresAt) return true;
  const expiryDate = new Date(expiresAt);
  const now = new Date();
  const bufferTime = 10 * 60 * 1000; // 10분 여유시간
  console.log(`[isTokenExpired] now: ${now.toISOString()}, expiresAt: ${expiresAt}, expiryDate: ${expiryDate.toISOString()}`);
  const isExpired = now.getTime() + bufferTime > expiryDate.getTime();
  console.log(`[isTokenExpired] isExpired: ${isExpired}`);
  return isExpired;
}

/**
 * TikTok API 전용 비디오 통계 업데이트 함수 (메타데이터 제외)
 */
async function updateVideoStatsOnly(supabase: any, videoId: string, stats: any) {
  try {
    // 현재 result 데이터 가져오기
    const { data: currentVideo, error: fetchError } = await supabase
      .from('campaign_application_videos')
      .select('result, saves_count')
      .eq('tiktok_video_id', videoId)
      .single();

    if (fetchError) {
      throw new Error(`Error fetching current video data: ${fetchError.message}`);
    }

    const currentResult = currentVideo?.result || {};
    const timestamp = new Date().toISOString();

    // 새 통계 데이터 (기존 saves_count 유지)
    const newStats = {
      like_count: stats.like_count || 0,
      comment_count: stats.comment_count || 0,
      share_count: stats.share_count || 0,
      view_count: stats.view_count || 0,
      saves_count: currentVideo?.saves_count || 0,
      timestamp
    };

    // result 업데이트 (기존 구조 유지)
    const updatedResult = {
      ...currentResult,
      stats: [
        ...(currentResult.stats || []),
        newStats
      ],
      latest: newStats
    };

    // 업데이트할 데이터 준비 (메타데이터 관련 필드 제외)
    const updateData = {
      result: updatedResult,
      like_count: stats.like_count || 0,
      comment_count: stats.comment_count || 0,
      share_count: stats.share_count || 0,
      view_count: stats.view_count || 0,
      updated_at: timestamp
    };

    // 비디오 통계 업데이트
    const { error: updateError } = await supabase
      .from('campaign_application_videos')
      .update(updateData)
      .eq('tiktok_video_id', videoId);

    if (updateError) {
      throw new Error(`Error updating video: ${updateError.message}`);
    }

    return {
      success: true,
      videoId,
      stats: newStats
    };
  } catch (error) {
    console.error(`Error updating video ${videoId}:`, error);
    return {
      success: false,
      videoId,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * TikTok 토큰 리프레시 함수
 */
async function refreshTikTokToken(supabase: any, userId: string, refreshToken: string): Promise<string> {
  try {
    console.log(`Refreshing token for user ${userId}`);
    const clientKey = Deno.env.get('TIKTOK_CLIENT_KEY');
    const clientSecret = Deno.env.get('TIKTOK_CLIENT_SECRET');
    
    console.log(`Environment variables check - clientKey exists: ${!!clientKey}, clientSecret exists: ${!!clientSecret}`);
    
    if (!clientKey || !clientSecret) {
      throw new Error('Missing TikTok credentials');
    }

    // TikTok OAuth 토큰 갱신 요청
    const formData = new URLSearchParams({
      client_key: clientKey,
      client_secret: clientSecret,
      grant_type: 'refresh_token',
      refresh_token: refreshToken
    });

    console.log(`Sending token refresh request to TikTok for user ${userId}`);
    
    try {
      const response = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Cache-Control': 'no-cache'
        },
        body: formData.toString()
      });

      const data = await response.json();
      console.log(`TikTok token refresh response status: ${response.status}`);
      console.log(`TikTok token refresh response body: ${JSON.stringify(data)}`);

      // "invalid_grant" 오류는 리프레시 토큰이 만료되었음을 의미
      if (data?.error === 'invalid_grant') {
        console.error(`Refresh token has expired for user ${userId}`);
        
        // 토큰 만료 상태 업데이트
        try {
          await supabase
            .from('user_tiktok_account')
            .update({
              refresh_token: null,
              access_token: null,
              updated_at: new Date().toISOString()
            })
            .eq('user_id', userId);
          console.log(`Updated user ${userId} account to mark tokens as expired`);
        } catch (updateError) {
          console.error(`Failed to update user account status:`, updateError);
        }
        
        throw new Error(`Refresh token is invalid or expired: ${data?.error_description || 'TikTok authentication expired'}`);
      }

      if (!response.ok) {
        throw new Error(`TikTok API Error: ${data?.error_description || data?.message || JSON.stringify(data || {})}`);
      }

      if (!data?.access_token) {
        console.error('Invalid TikTok API response - missing access_token:', data);
        throw new Error('Missing access_token in TikTok response');
      }

      // 토큰 유효 기간 계산
      const now = new Date();
      const accessExpiresAt = new Date(now.getTime() + (data.expires_in || 86400) * 1000);
      const refreshExpiresAt = new Date(now.getTime() + (data.refresh_expires_in || 31536000) * 1000);
      
      console.log(`Token expiry times - accessExpiresAt: ${accessExpiresAt.toISOString()}, refreshExpiresAt: ${refreshExpiresAt.toISOString()}`);

      // 토큰 정보 업데이트
      const { error: updateError } = await supabase
        .from('user_tiktok_account')
        .update({
          access_token: data.access_token,
          refresh_token: data.refresh_token || refreshToken,
          access_expires_at: accessExpiresAt.toISOString(),
          refresh_expires_at: refreshExpiresAt.toISOString(),
          updated_at: now.toISOString()
        })
        .eq('user_id', userId);

      if (updateError) {
        console.error(`DB update error for user ${userId}:`, updateError);
        throw new Error(`Failed to update token in database: ${updateError.message}`);
      }

      console.log(`Successfully refreshed token for user ${userId}`);
      return data.access_token;
    } catch (fetchError) {
      if (fetchError instanceof Error && fetchError.message.includes('Refresh token is invalid or expired')) {
        throw fetchError;
      }
      console.error(`Network error while refreshing token for user ${userId}:`, fetchError);
      throw new Error(`Network error during token refresh: ${fetchError instanceof Error ? fetchError.message : 'Unknown error'}`);
    }
  } catch (error) {
    console.error(`Error refreshing token for user ${userId}:`, error);
    throw error;
  }
}

/**
 * TikTok API 호출 함수 (토큰 리프레시 로직 포함)
 */
async function callTikTokApi(
  supabase: any,
  userId: string,
  accessToken: string,
  refreshToken: string,
  accessExpiresAt: string,
  refreshExpiresAt: string,
  endpoint: string,
  options: any = {}
): Promise<Response> {
  try {
    console.log(`TikTok API 호출: ${endpoint}, userId: ${userId}`);
    let currentAccessToken = accessToken;
    
    const accessTokenExpired = isTokenExpired(accessExpiresAt);
    const refreshTokenExpired = isTokenExpired(refreshExpiresAt);
    
    console.log(`[callTikTokApi] 토큰 상태 - accessTokenExpired: ${accessTokenExpired}, refreshTokenExpired: ${refreshTokenExpired}`);

    if (accessTokenExpired) {
      console.log('토큰 만료 감지, 리프레시 진행');
      
      if (refreshTokenExpired) {
        console.error('리프레시 토큰도 만료됨');
        try {
          await supabase
            .from('user_tiktok_account')
            .update({
              refresh_token: null,
              access_token: null,
              updated_at: new Date().toISOString()
            })
            .eq('user_id', userId);
          console.log(`Updated user ${userId} account to mark tokens as expired due to refresh token expiry`);
        } catch (updateError) {
          console.error(`Failed to update user account status:`, updateError);
        }
        throw new Error('TikTok refresh token has expired. Please reconnect your TikTok account.');
      }

      try {
        currentAccessToken = await refreshTikTokToken(supabase, userId, refreshToken);
        console.log('새 액세스 토큰 발급 완료');
      } catch (refreshError) {
        console.error('토큰 리프레시 실패:', refreshError);
        if (refreshError instanceof Error && refreshError.message.includes('Refresh token is invalid or expired')) {
          throw new Error(`TikTok authentication has expired. Please reconnect your TikTok account: ${refreshError.message}`);
        }
        throw new Error(`Failed to refresh token: ${refreshError instanceof Error ? refreshError.message : 'Unknown error'}`);
      }
    }

    const apiOptions = {
      ...options,
      headers: {
        'Authorization': `Bearer ${currentAccessToken}`,
        'Content-Type': 'application/json',
        ...(options.headers || {})
      }
    };

    const apiUrl = endpoint.startsWith('http') ? endpoint : `https://open.tiktokapis.com/v2/${endpoint}`;
    console.log(`TikTok API 요청: ${apiUrl}`);
    
    const response = await fetch(apiUrl, apiOptions);
    console.log(`TikTok API 응답 상태: ${response.status}`);

    if (response.status === 401 && !accessTokenExpired) {
      console.log('401 응답 받음, 강제 리프레시 후 재시도');
      try {
        currentAccessToken = await refreshTikTokToken(supabase, userId, refreshToken);
        const retryOptions = {
          ...options,
          headers: {
            'Authorization': `Bearer ${currentAccessToken}`,
            'Content-Type': 'application/json',
            ...(options.headers || {})
          }
        };
        console.log(`TikTok API 재요청: ${apiUrl}`);
        return await fetch(apiUrl, retryOptions);
      } catch (retryError) {
        console.error('재시도 중 토큰 리프레시 실패:', retryError);
        throw new Error(`Failed to refresh token during retry: ${retryError instanceof Error ? retryError.message : 'Unknown error'}`);
      }
    }

    return response;
  } catch (error) {
    console.error('Error calling TikTok API:', error);
    throw error;
  }
}

/**
 * 메인 함수 - TikTok API 전용 통계 업데이트
 */
serve(async (req) => {
  try {
    console.log('Starting TikTok API-only video stats update function');
    console.log(`Processing applications created within the last 30 days only`);

    // Supabase 클라이언트 생성
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? '';
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
    console.log(`Supabase configuration check - URL exists: ${!!supabaseUrl}, Key exists: ${!!supabaseKey}`);
    
    const supabase = createClient(supabaseUrl, supabaseKey);

    // 1. UPLOADED 상태의 캠페인 애플리케이션 찾기 (30일 이내만)
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

    const { data: applications, error: appError } = await supabase
      .from('campaign_applications')
      .select(`
        id,
        user_id,
        campaign_id,
        created_at
      `)
      .eq('status', 'UPLOADED')
      .gte('created_at', thirtyDaysAgo.toISOString());

    if (appError) {
      throw new Error(`Error fetching applications: ${appError.message}`);
    }

    if (!applications || applications.length === 0) {
      console.log('No UPLOADED applications found within 30 days');
      return new Response(
        JSON.stringify({
          message: 'No UPLOADED applications found within 30 days'
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 200
        }
      );
    }

    console.log(`Found ${applications.length} UPLOADED applications within 30 days`);
    
    const applicationIds = applications.map(app => app.id);
    const userIds = applications.map(app => app.user_id);

    // 2. 해당 애플리케이션 ID에 연결된 비디오 찾기
    const { data: videos, error: videoError } = await supabase
      .from('campaign_application_videos')
      .select('id, campaign_application_id, tiktok_video_id')
      .in('campaign_application_id', applicationIds);

    if (videoError) {
      throw new Error(`Error fetching videos: ${videoError.message}`);
    }

    if (!videos || videos.length === 0) {
      console.log('No videos found for UPLOADED applications');
      return new Response(
        JSON.stringify({
          message: 'No videos found for UPLOADED applications'
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 200
        }
      );
    }

    console.log(`Found ${videos.length} videos for processing`);

    // 비디오 그룹화 (애플리케이션당)
    const videosByApplication = videos.reduce((acc: any, video: any) => {
      if (!acc[video.campaign_application_id]) {
        acc[video.campaign_application_id] = [];
      }
      acc[video.campaign_application_id].push({
        id: video.tiktok_video_id
      });
      return acc;
    }, {});

    // 3. TikTok 계정 정보 가져오기
    const { data: tiktokAccounts, error: accountError } = await supabase
      .from('user_tiktok_account')
      .select('user_id, username, access_token, refresh_token, access_expires_at, refresh_expires_at')
      .in('user_id', userIds);

    if (accountError) {
      throw new Error(`Error fetching TikTok accounts: ${accountError.message}`);
    }

    if (!tiktokAccounts || tiktokAccounts.length === 0) {
      console.log('No TikTok accounts found for users');
      return new Response(
        JSON.stringify({
          message: 'No TikTok accounts found for users'
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 200
        }
      );
    }

    console.log(`Found ${tiktokAccounts.length} TikTok accounts`);

    // 계정 정보를 user_id로 매핑
    const accountMap = tiktokAccounts.reduce((acc: any, account: any) => {
      acc[account.user_id] = account;
      return acc;
    }, {});

    // 처리할 항목 준비
    const processingList = applications.flatMap((app: any) => {
      const account = accountMap[app.user_id];
      const appVideos = videosByApplication[app.id] || [];

      if (!account || !appVideos.length) return [];

      if (!account.refresh_token) {
        console.log(`Skipping user ${app.user_id} as they have no refresh token - needs to reconnect TikTok`);
        return [];
      }

      console.log(`User ${app.user_id} account info - username: ${account.username}, access token exists: ${!!account.access_token}, refresh token exists: ${!!account.refresh_token}`);
      console.log(`Access token expires: ${account.access_expires_at}, Refresh token expires: ${account.refresh_expires_at}`);

      return {
        applicationId: app.id,
        userId: app.user_id,
        username: account.username,
        accessToken: account.access_token,
        refreshToken: account.refresh_token,
        accessExpiresAt: account.access_expires_at,
        refreshExpiresAt: account.refresh_expires_at,
        videos: appVideos
      };
    }).filter((item: any) => !!item.userId);

    if (processingList.length === 0) {
      console.log('No valid processing items found');
      return new Response(
        JSON.stringify({
          message: 'No valid processing items found'
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 200
        }
      );
    }

    console.log(`Processing ${processingList.length} items`);

    // 4. 각 사용자별로 TikTok API 호출하여 비디오 통계 가져오기
    const results: any[] = [];

    for (const item of processingList) {
      try {
        console.log(`Processing user ${item.userId} with ${item.videos.length} videos`);
        const videoIds = item.videos.map((v: any) => v.id);

        // TikTok API로 통계 가져오기
        const response = await callTikTokApi(
          supabase,
          item.userId,
          item.accessToken,
          item.refreshToken,
          item.accessExpiresAt,
          item.refreshExpiresAt,
          'video/query/?fields=id,like_count,comment_count,share_count,view_count',
          {
            method: 'POST',
            body: JSON.stringify({
              filters: {
                video_ids: videoIds
              }
            })
          }
        );

        if (!response.ok) {
          const errorData = await response.json().catch(() => ({}));
          console.error('TikTok API error:', {
            status: response.status,
            statusText: response.statusText,
            error: errorData
          });

          const errorMessage = errorData?.error?.description || errorData?.error_description || JSON.stringify(errorData || {});

          if (response.status === 401 || errorMessage.includes('token')) {
            try {
              await supabase
                .from('user_tiktok_account')
                .update({
                  access_token: null,
                  updated_at: new Date().toISOString()
                })
                .eq('user_id', item.userId);
            } catch (updateError) {
              console.error(`Failed to update user account status after API error:`, updateError);
            }
          }

          results.push({
            success: false,
            userId: item.userId,
            error: `TikTok API error: ${response.status} ${response.statusText} - ${JSON.stringify(errorData)}`
          });
          continue;
        }

        const videoStats = await response.json();
        console.log(`Received stats for user ${item.userId}: ${JSON.stringify(videoStats)}`);

        if (!videoStats.data || !videoStats.data.videos || !Array.isArray(videoStats.data.videos)) {
          console.error(`Invalid response structure from TikTok API for user ${item.userId}:`, videoStats);
          results.push({
            success: false,
            userId: item.userId,
            error: `Invalid response structure from TikTok API: ${JSON.stringify(videoStats)}`
          });
          continue;
        }

        // 5. 각 비디오별로 통계 업데이트 (메타데이터 제외)
        for (const video of videoStats.data.videos || []) {
          const updateResult = await updateVideoStatsOnly(supabase, video.id, video);
          results.push(updateResult);
        }

      } catch (error) {
        console.error(`Error processing user ${item.userId}:`, error);
        let errorMessage = error instanceof Error ? error.message : 'Unknown error';

        if (error instanceof Error && (error.message.includes('Refresh token is invalid or expired') || error.message.includes('TikTok authentication has expired'))) {
          errorMessage = `TikTok 인증이 만료되었습니다. TikTok 계정을 다시 연결해주세요: ${error.message}`;
          try {
            await supabase
              .from('user_tiktok_account')
              .update({
                refresh_token: null,
                access_token: null,
                updated_at: new Date().toISOString()
              })
              .eq('user_id', item.userId);
            console.log(`Updated user ${item.userId} account to mark tokens as expired due to authentication failure`);
          } catch (updateError) {
            console.error(`Failed to update user account status:`, updateError);
          }
        }

        results.push({
          success: false,
          userId: item.userId,
          error: errorMessage
        });
      }
    }

    // 6. 응답 반환
    const successCount = results.filter((r: any) => r.success).length;
    const failedCount = results.filter((r: any) => !r.success).length;

    console.log(`Processing complete - total: ${results.length}, successful: ${successCount}, failed: ${failedCount}`);

    return new Response(
      JSON.stringify({
        processed: results.length,
        successful: successCount,
        failed: failedCount,
        results
      }),
      {
        headers: { 'Content-Type': 'application/json' },
        status: 200
      }
    );

  } catch (error) {
    console.error('Error in TikTok API-only video stats function:', error);
    return new Response(
      JSON.stringify({
        error: error instanceof Error ? error.message : 'Unknown error'
      }),
      {
        headers: { 'Content-Type': 'application/json' },
        status: 500
      }
    );
  }
});
