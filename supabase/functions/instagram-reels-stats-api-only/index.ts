// Instagram 릴 API 전용 통계 업데이트 함수
// supabase edge function
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.21.0';

/**
 * Instagram 액세스 토큰이 만료되었는지 확인하는 함수
 */
function isTokenExpired(expiresAt: string | null): boolean {
  if (!expiresAt) return true;
  const expiryDate = new Date(expiresAt);
  const now = new Date();
  const bufferTime = 10 * 60 * 1000; // 10분 여유시간
  return now.getTime() + bufferTime > expiryDate.getTime();
}

/**
 * Instagram API 전용 릴 통계 업데이트 함수
 */
async function updateReelStatsOnly(supabase: any, reelId: string, stats: any) {
  try {
    // 현재 result 데이터 가져오기 (기존 share_count도 포함)
    const { data: currentReel, error: fetchError } = await supabase
      .from('campaign_application_reels')
      .select('result, reach_count, share_count')
      .eq('instagram_reel_id', reelId)
      .single();

    if (fetchError) {
      throw new Error(`Error fetching current reel data: ${fetchError.message}`);
    }

    const currentResult = currentReel?.result || {};
    const timestamp = new Date().toISOString();

          // 새 통계 데이터 (모든 메트릭 포함)
          const newStats = {
            timestamp: stats.timestamp,
            like_count: stats.like_count || 0,
            view_count: stats.view_count || 0,
            saves_count: stats.saves_count || 0,
            share_count: stats.share_count || 0,
            comment_count: stats.comment_count || 0,
            reach_count: stats.reach_count || 0
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

    // 업데이트할 데이터 준비
    const updateData = {
      result: updatedResult,
      like_count: stats.like_count || 0,
      comment_count: stats.comment_count || 0,
      share_count: stats.share_count || 0,
      view_count: stats.view_count || 0,
      saves_count: stats.saves_count || 0,
      reach_count: stats.reach_count || 0,
      impression_count: stats.impression_count || 0,
      updated_at: stats.timestamp
    };

    // 릴 통계 업데이트
    const { error: updateError } = await supabase
      .from('campaign_application_reels')
      .update(updateData)
      .eq('instagram_reel_id', reelId);

    if (updateError) {
      throw new Error(`Error updating reel: ${updateError.message}`);
    }

    return {
      success: true,
      reelId,
      stats: newStats
    };
  } catch (error) {
    console.error(`Error updating reel ${reelId}:`, error);
    return {
      success: false,
      reelId,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Instagram 토큰 리프레시 함수
 */
async function refreshInstagramToken(supabase: any, userId: string, accessToken: string): Promise<string> {
  try {
    const url = `https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=${encodeURIComponent(accessToken)}`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'User-Agent': 'Collabeauty-Instagram-Refresh/1.0'
      }
    });

    const data = await response.json();

    if (!response.ok) {
      const errorType = data?.error?.type || 'Unknown';
      
      if (errorType === 'OAuthException') {
        // 토큰 만료 상태 업데이트
        await supabase
          .from('user_instagram_account')
          .update({
            access_token: null,
            access_expires_at: null,
            updated_at: new Date().toISOString()
          })
          .eq('user_id', userId);
      }
      
      throw new Error(`Instagram API Error: ${data?.error?.message || JSON.stringify(data || {})}`);
    }

    if (!data?.access_token) {
      throw new Error('Missing access_token in Instagram response');
    }

    // 토큰 유효 기간 계산 (Instagram 토큰은 60일)
    const now = new Date();
    const accessExpiresAt = new Date(now.getTime() + (data.expires_in || 5184000) * 1000);

    // 토큰 정보 업데이트
    const { error: updateError } = await supabase
      .from('user_instagram_account')
      .update({
        access_token: data.access_token,
        access_expires_at: accessExpiresAt.toISOString(),
        updated_at: now.toISOString(),
        last_refreshed_at: now.toISOString()
      })
      .eq('user_id', userId);

    if (updateError) {
      throw new Error(`Failed to update token in database: ${updateError.message}`);
    }

    return data.access_token;
  } catch (error) {
    console.error(`Error refreshing Instagram token for user ${userId}:`, error);
    throw error;
  }
}

/**
 * Instagram API를 사용하여 릴 통계 가져오기 (Media Insights 사용)
 */
async function fetchInstagramReelStats(reelIds: string[], accessToken: string) {
  try {
    const results: any = {};
    
    // 각 릴에 대해 개별적으로 insights 요청
    for (const reelId of reelIds) {
      try {
        // 기본 미디어 정보로 접근 가능한지 확인
        const basicCheckResponse = await fetch(
          `https://graph.instagram.com/${reelId}?fields=id,media_type,media_product_type&access_token=${encodeURIComponent(accessToken)}`,
          {
            method: 'GET',
            headers: {
              'User-Agent': 'Collabeauty-Instagram-API/1.0'
            }
          }
        );
        
        if (!basicCheckResponse.ok) {
          results[reelId] = null;
          continue;
        }
        
        // Insights API 시도
        const metricsResponse = await fetch(
          `https://graph.instagram.com/${reelId}/insights?metric=reach,likes,comments,shares,saved,views&access_token=${encodeURIComponent(accessToken)}`,
          {
            method: 'GET',
            headers: {
              'User-Agent': 'Collabeauty-Instagram-API/1.0'
            }
          }
        );
        
        if (metricsResponse.ok) {
          const metricsData = await metricsResponse.json();
          
          // Insights 데이터를 파싱하여 결과 형태로 변환
          const insights: any = {};
          if (metricsData.data && Array.isArray(metricsData.data)) {
            metricsData.data.forEach((metric: any) => {
              if (metric.values && metric.values.length > 0) {
                insights[metric.name] = metric.values[0].value;
              } else {
                insights[metric.name] = 0;
              }
            });
          }
          
          results[reelId] = insights;
        } else {
          const errorData = await metricsResponse.json();
          
          // 에러 로깅 (중요한 에러만)
          if (!errorData.error?.message?.includes('does not support')) {
            console.error(`Failed to get insights for reel ${reelId}:`, errorData);
          }
          
          results[reelId] = null;
          
          // 기본값으로 fallback
          if (!results[reelId]) {
            try {
              const basicResponse = await fetch(
                `https://graph.instagram.com/${reelId}?fields=id&access_token=${encodeURIComponent(accessToken)}`,
                {
                  method: 'GET',
                  headers: {
                    'User-Agent': 'Collabeauty-Instagram-API/1.0'
                  }
                }
              );
              
              if (basicResponse.ok) {
                results[reelId] = {
                  likes: 0,
                  comments: 0,
                  shares: 0,
                  reach: 0,
                  saved: 0,
                  views: 0
                };
              } else {
                results[reelId] = null;
              }
            } catch (fallbackError) {
              results[reelId] = null;
            }
          }
        }
        
        // API 요청 간 지연 (rate limiting 방지)
        await new Promise(resolve => setTimeout(resolve, 500));
        
      } catch (error) {
        results[reelId] = null;
      }
    }

    return results;
  } catch (error) {
    console.error('Error fetching Instagram reel stats:', error);
    throw error;
  }
}

/**
 * Instagram API 호출 함수 (토큰 리프레시 로직 포함)
 */
async function callInstagramApi(
  supabase: any,
  userId: string,
  accessToken: string,
  accessExpiresAt: string,
  reelIds: string[]
): Promise<any> {
  try {
    let currentAccessToken = accessToken;
    
    const accessTokenExpired = isTokenExpired(accessExpiresAt);

    if (accessTokenExpired) {
      try {
        currentAccessToken = await refreshInstagramToken(supabase, userId, accessToken);
      } catch (refreshError) {
        throw new Error(`Failed to refresh token: ${refreshError instanceof Error ? refreshError.message : 'Unknown error'}`);
      }
    }

    const apiData = await fetchInstagramReelStats(reelIds, currentAccessToken);
    
    return apiData;
  } catch (error) {
    console.error('Error calling Instagram API:', error);
    throw error;
  }
}

/**
 * 메인 함수 - Instagram API 전용 통계 업데이트
 */
serve(async (req) => {
  try {
    // Supabase 클라이언트 생성
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? '';
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
    
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
    
    const applicationIds = applications.map(app => app.id);
    const userIds = applications.map(app => app.user_id);

    // 2. 해당 애플리케이션 ID에 연결된 릴 찾기
    const { data: reels, error: reelError } = await supabase
      .from('campaign_application_reels')
      .select('id, campaign_application_id, instagram_reel_id')
      .in('campaign_application_id', applicationIds);

    if (reelError) {
      throw new Error(`Error fetching reels: ${reelError.message}`);
    }

    if (!reels || reels.length === 0) {
      return new Response(
        JSON.stringify({
          message: 'No reels found for UPLOADED applications'
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 200
        }
      );
    }

    // 릴 그룹화 (애플리케이션당)
    const reelsByApplication = reels.reduce((acc: any, reel: any) => {
      if (!acc[reel.campaign_application_id]) {
        acc[reel.campaign_application_id] = [];
      }
      acc[reel.campaign_application_id].push({
        id: reel.instagram_reel_id
      });
      return acc;
    }, {});

    // 3. Instagram 계정 정보 가져오기
    const { data: instagramAccounts, error: accountError } = await supabase
      .from('user_instagram_account')
      .select('user_id, username, access_token, access_expires_at')
      .in('user_id', userIds);

    if (accountError) {
      throw new Error(`Error fetching Instagram accounts: ${accountError.message}`);
    }

    if (!instagramAccounts || instagramAccounts.length === 0) {
      return new Response(
        JSON.stringify({
          message: 'No Instagram accounts found for users'
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 200
        }
      );
    }

    // 계정 정보를 user_id로 매핑
    const accountMap = instagramAccounts.reduce((acc: any, account: any) => {
      acc[account.user_id] = account;
      return acc;
    }, {});

    // 처리할 항목 준비
    const processingList = applications.flatMap((app: any) => {
      const account = accountMap[app.user_id];
      const appReels = reelsByApplication[app.id] || [];

      if (!account || !appReels.length) return [];

      if (!account.access_token) {
        return [];
      }

      return {
        applicationId: app.id,
        userId: app.user_id,
        username: account.username,
        accessToken: account.access_token,
        accessExpiresAt: account.access_expires_at,
        reels: appReels
      };
    }).filter((item: any) => !!item.userId);

    if (processingList.length === 0) {
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

    // 4. 각 사용자별로 Instagram API 호출하여 릴 통계 가져오기
    const results: any[] = [];

    for (const item of processingList) {
      try {
        const reelIds = item.reels.map((r: any) => r.id);

        // Instagram API로 통계 가져오기
        const apiData = await callInstagramApi(
          supabase,
          item.userId,
          item.accessToken,
          item.accessExpiresAt,
          reelIds
        );

        // 5. 각 릴별로 통계 업데이트 (Media Insights 데이터)
        for (const reelId of reelIds) {
          if (apiData[reelId] && apiData[reelId] !== null) {
            const insights = apiData[reelId];
            const timestamp = new Date().toISOString();
            const reelStats = {
              timestamp,
              like_count: insights.likes || 0,
              comment_count: insights.comments || 0,
              share_count: insights.shares || 0,
              view_count: insights.views || 0,
              saves_count: insights.saved || 0,
              reach_count: insights.reach || 0,
              impression_count: 0
            };

            const updateResult = await updateReelStatsOnly(supabase, reelId, reelStats);
            results.push(updateResult);
          } else {
            results.push({
              success: false,
              reelId,
              error: 'No insights data available - check account type and permissions'
            });
          }
        }

      } catch (error) {
        console.error(`Error processing user ${item.userId}:`, error);
        let errorMessage = error instanceof Error ? error.message : 'Unknown error';

        if (error instanceof Error && error.message.includes('Instagram authentication')) {
          errorMessage = `Instagram 인증이 만료되었습니다. Instagram 계정을 다시 연결해주세요: ${error.message}`;
          try {
            await supabase
              .from('user_instagram_account')
              .update({
                access_token: null,
                access_expires_at: null,
                updated_at: new Date().toISOString()
              })
              .eq('user_id', item.userId);
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
    console.error('Error in Instagram API-only reel stats function:', error);
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
