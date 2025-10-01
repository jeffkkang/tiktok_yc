// TikTok 크롤링 전용 메타데이터 업데이트 함수 (3회 배치 처리)
// supabase edge function
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.21.0';

/**
 * 메타데이터 업데이트가 필요한지 확인 (1일마다 또는 최초)
 */
function shouldUpdateMetadata(metadataUpdatedAt: string | null): boolean {
  if (!metadataUpdatedAt) return true; // 최초 업데이트
  const lastUpdate = new Date(metadataUpdatedAt);
  const now = new Date();
  const daysSince = (now.getTime() - lastUpdate.getTime()) / (1000 * 60 * 60 * 24);
  return daysSince >= 1; // 1일마다 메타데이터 업데이트
}

/**
 * Collabeauty Brand API를 통해 TikTok 비디오 메타데이터 가져오기
 */
async function fetchVideoMetadata(videoUrl: string): Promise<any> {
  try {
    console.log(`Fetching metadata for video: ${videoUrl}`);
    
    // Vercel에 배포된 collabeauty-brand API 호출
    const COLLABEAUTY_DOMAIN = Deno.env.get('COLLABEAUTY_BRAND_DOMAIN') || 'YOUR_VERCEL_DOMAIN.vercel.app';
    
    // 🚀 메타데이터 전용 API 호출 (80% 성능 향상!)
    const analyzeResponse = await fetch(`https://${COLLABEAUTY_DOMAIN}/api/tiktok/metadata-only`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        url: videoUrl
      })
    });

    if (!analyzeResponse.ok) {
      console.error(`Failed to analyze video: ${analyzeResponse.status} ${analyzeResponse.statusText}`);
      return null;
    }

    const analyzeResult = await analyzeResponse.json();
    console.log(`Metadata-only result:`, analyzeResult);

    // 다양한 오류 응답 형태 처리
    if (analyzeResult.status === 'error' || analyzeResult.error || analyzeResult.detail) {
      const errorMsg = analyzeResult.error || analyzeResult.details || analyzeResult.detail || 'Unknown error';
      console.log('Metadata API error:', errorMsg);
      return null;
    }

    if (analyzeResult.status !== 'success' || !analyzeResult.metadata_file) {
      console.log('No metadata file generated:', analyzeResult);
      return null;
    }

    // 메타데이터 파일 경로 직접 사용
    const metadataFile = analyzeResult.metadata_file;
    console.log(`Found metadata file: ${metadataFile}`);

    // 메타데이터 다운로드
    const downloadUrl = `https://${COLLABEAUTY_DOMAIN}/api/tiktok/download?gcs=${encodeURIComponent(metadataFile)}`;
    const metadataResponse = await fetch(downloadUrl);

    if (!metadataResponse.ok) {
      console.error(`Failed to download metadata: ${metadataResponse.status} ${metadataResponse.statusText}`);
      return null;
    }

    const metadata = await metadataResponse.json().catch((parseError) => {
      console.error('Failed to parse metadata JSON:', parseError);
      return null;
    });

    if (!metadata) {
      console.log('Metadata parsing failed');
      return null;
    }

    console.log(`Metadata fetched successfully:`, metadata);

    // 안전한 메타데이터 파싱
    const safeMetadata = {
      platform_labels: Array.isArray(metadata?.platform_labels) ? metadata.platform_labels : [],
      location_created: metadata?.location_created || null,
      music_title: metadata?.music_title || null,
      saves_count: typeof metadata?.saves_count === 'number' ? metadata.saves_count : 0,
      video_url: metadata?.video_url || videoUrl
    };

    console.log(`Safe metadata processed:`, safeMetadata);
    return safeMetadata;

  } catch (error) {
    console.error('Error fetching video metadata:', error);
    return null;
  }
}

/**
 * 메타데이터만 업데이트하는 함수
 */
async function updateVideoMetadataOnly(supabase: any, videoId: string, metadata: any) {
  try {
    // 현재 result 데이터 가져오기
    const { data: currentVideo, error: fetchError } = await supabase
      .from('campaign_application_videos')
      .select('result')
      .eq('tiktok_video_id', videoId)
      .single();

    if (fetchError) {
      throw new Error(`Error fetching current video data: ${fetchError.message}`);
    }

    const currentResult = currentVideo?.result || {};
    const timestamp = new Date().toISOString();

    // result에 메타데이터 추가/업데이트
    const updatedResult = {
      ...currentResult,
      metadata: {
        ...currentResult.metadata,
        platform_labels: Array.isArray(metadata.platform_labels) ? metadata.platform_labels : [],
        location_created: metadata.location_created || null,
        music_title: metadata.music_title || null,
        video_url: metadata.video_url || null,
        fetched_at: timestamp
      }
    };

    // saves_count가 있으면 latest 통계에도 업데이트
    if (typeof metadata.saves_count === 'number' && currentResult.latest) {
      updatedResult.latest = {
        ...currentResult.latest,
        saves_count: metadata.saves_count
      };
    }

    // 업데이트할 데이터 준비 (메타데이터 관련 필드만)
    const updateData = {
      result: updatedResult,
      platform_labels: Array.isArray(metadata.platform_labels) ? metadata.platform_labels : [],
      location_created: metadata.location_created || null,
      metadata_updated_at: timestamp
    };

    // saves_count가 있으면 해당 컬럼도 업데이트
    if (typeof metadata.saves_count === 'number') {
      updateData.saves_count = metadata.saves_count;
    }

    // 비디오 메타데이터 업데이트
    const { error: updateError } = await supabase
      .from('campaign_application_videos')
      .update(updateData)
      .eq('tiktok_video_id', videoId);

    if (updateError) {
      throw new Error(`Error updating video metadata: ${updateError.message}`);
    }

    return {
      success: true,
      videoId,
      metadata: 'updated'
    };
  } catch (error) {
    console.error(`Error updating video metadata ${videoId}:`, error);
    return {
      success: false,
      videoId,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * 배치 처리를 위한 지연 함수
 */
function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * 메인 함수 - 크롤링 전용 메타데이터 업데이트 (3회 배치 처리)
 */
serve(async (req) => {
  try {
    console.log('Starting TikTok metadata crawling function with batch processing');
    console.log(`Processing videos created within the last 30 days, metadata not updated within 1 day`);

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

    // 2. 해당 애플리케이션 ID에 연결된 비디오 찾기 (메타데이터 업데이트가 필요한 것만)
    const { data: videos, error: videoError } = await supabase
      .from('campaign_application_videos')
      .select('id, campaign_application_id, tiktok_video_id, video_url, metadata_updated_at')
      .in('campaign_application_id', applicationIds)
      .not('video_url', 'is', null); // video_url이 있는 것만

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

    // 메타데이터 업데이트가 필요한 비디오만 필터링
    const videosNeedingUpdate = videos.filter(video => 
      video.video_url && shouldUpdateMetadata(video.metadata_updated_at)
    );

    if (videosNeedingUpdate.length === 0) {
      console.log('No videos need metadata update');
      return new Response(
        JSON.stringify({
          message: 'No videos need metadata update (all updated within 1 day)'
        }),
        {
          headers: { 'Content-Type': 'application/json' },
          status: 200
        }
      );
    }

    console.log(`Found ${videosNeedingUpdate.length} videos needing metadata update`);

    // 3회 배치로 나누기 (런타임 에러 최소화)
    const batchSize = Math.ceil(videosNeedingUpdate.length / 3);
    const batches = [];
    
    for (let i = 0; i < videosNeedingUpdate.length; i += batchSize) {
      batches.push(videosNeedingUpdate.slice(i, i + batchSize));
    }

    console.log(`Split into ${batches.length} batches with sizes: ${batches.map(b => b.length).join(', ')}`);

    const results: any[] = [];
    let totalMetadataFetched = 0;

    // 각 배치 처리
    for (let batchIndex = 0; batchIndex < batches.length; batchIndex++) {
      const batch = batches[batchIndex];
      console.log(`Processing batch ${batchIndex + 1}/${batches.length} with ${batch.length} videos`);

      // 배치 간 지연 시간 (첫 번째 배치는 지연 없음)
      if (batchIndex > 0) {
        console.log('Waiting 5 seconds before next batch...');
        await delay(5000);
      }

      // 각 비디오 처리
      for (const video of batch) {
        try {
          console.log(`Fetching metadata for video ${video.tiktok_video_id} from URL: ${video.video_url}`);
          
          // 메타데이터 가져오기
          const metadata = await fetchVideoMetadata(video.video_url);
          
          if (metadata) {
            console.log(`Metadata fetched for video ${video.tiktok_video_id}:`, metadata);
            totalMetadataFetched++;
            
            // 메타데이터 업데이트
            const updateResult = await updateVideoMetadataOnly(supabase, video.tiktok_video_id, metadata);
            results.push(updateResult);
          } else {
            console.log(`Failed to fetch metadata for video ${video.tiktok_video_id}`);
            results.push({
              success: false,
              videoId: video.tiktok_video_id,
              error: 'Failed to fetch metadata from crawling API'
            });
          }

          // 각 비디오 간 작은 지연 (API 과부하 방지)
          if (batch.indexOf(video) < batch.length - 1) {
            await delay(2000); // 2초 지연
          }

        } catch (error) {
          console.error(`Error processing video ${video.tiktok_video_id}:`, error);
          results.push({
            success: false,
            videoId: video.tiktok_video_id,
            error: error instanceof Error ? error.message : 'Unknown error'
          });
        }
      }

      console.log(`Completed batch ${batchIndex + 1}/${batches.length}`);
    }

    // 4. 응답 반환
    const successCount = results.filter((r: any) => r.success).length;
    const failedCount = results.filter((r: any) => !r.success).length;
    const metadataUpdatedCount = results.filter((r: any) => r.metadata === 'updated').length;

    console.log(`Processing complete - total: ${results.length}, successful: ${successCount}, failed: ${failedCount}, metadata updated: ${metadataUpdatedCount}`);

    return new Response(
      JSON.stringify({
        processed: results.length,
        successful: successCount,
        failed: failedCount,
        metadata_fetched: totalMetadataFetched,
        metadata_updated: metadataUpdatedCount,
        batches_processed: batches.length,
        results
      }),
      {
        headers: { 'Content-Type': 'application/json' },
        status: 200
      }
    );

  } catch (error) {
    console.error('Error in TikTok metadata crawling function:', error);
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
