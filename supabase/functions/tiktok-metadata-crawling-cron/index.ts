// TikTok 메타데이터 크롤링 크론잡
// supabase edge function with cron scheduling
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts';
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.21.0';

serve(async (req) => {
  try {
    console.log('Starting TikTok metadata crawling cron job');
    
    // Supabase 클라이언트 생성
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? '';
    const supabaseKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? '';
    
    if (!supabaseUrl || !supabaseKey) {
      throw new Error('Missing Supabase configuration');
    }

    // 메타데이터 크롤링 함수 호출
    const crawlingResponse = await fetch(`${supabaseUrl}/functions/v1/tiktok-metadata-crawling`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${supabaseKey}`,
        'Content-Type': 'application/json'
      }
    });

    const result = await crawlingResponse.json();
    
    console.log('Metadata crawling cron job completed:', result);

    return new Response(
      JSON.stringify({
        message: 'TikTok metadata crawling cron job executed successfully',
        timestamp: new Date().toISOString(),
        result
      }),
      {
        headers: { 'Content-Type': 'application/json' },
        status: 200
      }
    );

  } catch (error) {
    console.error('Error in TikTok metadata crawling cron job:', error);
    return new Response(
      JSON.stringify({
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      }),
      {
        headers: { 'Content-Type': 'application/json' },
        status: 500
      }
    );
  }
});
