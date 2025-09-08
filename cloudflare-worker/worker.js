// Cloudflare Worker for YouTube Transcript Fetching
// This runs on Cloudflare's edge, avoiding AWS IP blocking

export default {
  async fetch(request, env, ctx) {
    // Enable CORS for your backend
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      const url = new URL(request.url);
      const videoId = url.searchParams.get('v');
      
      if (!videoId) {
        return new Response(JSON.stringify({ 
          error: 'Missing video ID parameter "v"' 
        }), {
          status: 400,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      console.log(`Fetching transcript for video: ${videoId}`);

      // Step 1: Get INNERTUBE_API_KEY from video page
      const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
      console.log(`Fetching video page: ${videoUrl}`);
      
      const videoPageResponse = await fetch(videoUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Linux; Android 11; SM-A205U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Mobile Safari/537.36',
          'Accept-Language': 'en-US,en;q=0.9'
        }
      });

      if (!videoPageResponse.ok) {
        throw new Error(`Failed to fetch video page: ${videoPageResponse.status}`);
      }

      const videoPageHtml = await videoPageResponse.text();
      
      // Extract API key using regex
      const apiKeyMatch = videoPageHtml.match(/"INNERTUBE_API_KEY":"([^"]+)"/);
      if (!apiKeyMatch) {
        throw new Error('Could not extract INNERTUBE_API_KEY from video page');
      }

      const apiKey = apiKeyMatch[1];
      console.log(`Extracted API key: ${apiKey.substring(0, 10)}...`);

      // Step 2: Call player API impersonating Android client
      const playerUrl = `https://www.youtube.com/youtubei/v1/player?key=${apiKey}`;
      const playerBody = {
        context: {
          client: {
            clientName: 'ANDROID',
            clientVersion: '20.10.38'
          }
        },
        videoId: videoId
      };

      console.log(`Calling Innertube player API as Android client`);
      const playerResponse = await fetch(playerUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': 'com.google.android.youtube/20.10.38 (Linux; U; Android 11) gzip'
        },
        body: JSON.stringify(playerBody)
      });

      if (!playerResponse.ok) {
        throw new Error(`Player API failed: ${playerResponse.status}`);
      }

      const playerData = await playerResponse.json();

      // Step 3: Extract caption track URL
      const captions = playerData.captions || {};
      const captionTracks = captions.playerCaptionsTracklistRenderer?.captionTracks || [];

      if (captionTracks.length === 0) {
        return new Response(JSON.stringify({
          error: 'No caption tracks found in video',
          videoId: videoId,
          available: false
        }), {
          status: 404,
          headers: { ...corsHeaders, 'Content-Type': 'application/json' }
        });
      }

      console.log(`Found ${captionTracks.length} caption tracks`);

      // Find English track
      let enTrack = captionTracks.find(track => track.languageCode === 'en');
      if (!enTrack) {
        // If no English track, try the first available track
        enTrack = captionTracks[0];
        console.log(`No English track found, using: ${enTrack.languageCode || 'unknown'}`);
      }

      let captionUrl = enTrack.baseUrl;
      // Remove format parameter to get raw XML
      captionUrl = captionUrl.replace(/&fmt=\w+/, '');

      console.log(`Fetching captions from: ${captionUrl.substring(0, 50)}...`);

      // Step 4: Fetch and parse XML captions
      const captionResponse = await fetch(captionUrl);
      if (!captionResponse.ok) {
        throw new Error(`Failed to fetch captions: ${captionResponse.status}`);
      }

      const xmlContent = await captionResponse.text();
      console.log(`XML content length: ${xmlContent.length} chars`);

      // Parse XML manually (no XML parser in Workers)
      const segments = [];
      const textMatches = xmlContent.matchAll(/<text start="([^"]*)" dur="([^"]*)">([^<]*)<\/text>/g);
      
      for (const match of textMatches) {
        const startTime = parseFloat(match[1]);
        const duration = parseFloat(match[2]);
        const text = match[3]
          .replace(/&amp;/g, '&')
          .replace(/&lt;/g, '<')
          .replace(/&gt;/g, '>')
          .replace(/&quot;/g, '"')
          .replace(/&#39;/g, "'")
          .replace(/&nbsp;/g, ' ')
          .trim();

        if (text) {
          segments.push({
            text: text,
            start: startTime,
            end: startTime + duration
          });
        }
      }

      console.log(`Successfully parsed ${segments.length} segments`);

      // Apply smart segmentation (group into natural boundaries)
      const smartSegments = applySmartSegmentation(segments);

      const result = {
        success: true,
        videoId: videoId,
        segmentCount: smartSegments.length,
        segments: smartSegments,
        processedAt: new Date().toISOString(),
        source: 'cloudflare-worker'
      };

      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { 
          ...corsHeaders, 
          'Content-Type': 'application/json',
          'Cache-Control': 'public, max-age=3600' // Cache for 1 hour
        }
      });

    } catch (error) {
      console.error('Worker error:', error);
      
      return new Response(JSON.stringify({
        error: error.message,
        success: false,
        source: 'cloudflare-worker'
      }), {
        status: 500,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' }
      });
    }
  }
};

// Smart segmentation function (same logic as backend)
function applySmartSegmentation(rawSegments) {
  if (!rawSegments || rawSegments.length === 0) {
    return [];
  }

  const smartSegments = [];
  let currentGroup = {
    textParts: [],
    start: null,
    lastEnd: null
  };

  function finalizeGroup() {
    if (currentGroup.textParts.length > 0) {
      const combinedText = currentGroup.textParts.join(' ').trim();
      if (combinedText) {
        smartSegments.push({
          text: combinedText,
          start: currentGroup.start,
          end: currentGroup.lastEnd
        });
      }
    }
    currentGroup.textParts = [];
    currentGroup.start = null;
    currentGroup.lastEnd = null;
  }

  for (let i = 0; i < rawSegments.length; i++) {
    const segment = rawSegments[i];
    const text = segment.text.trim();
    
    if (!text) continue;

    // Initialize first group
    if (currentGroup.start === null) {
      currentGroup.start = segment.start;
    }

    currentGroup.textParts.push(text);
    currentGroup.lastEnd = segment.end;

    // Calculate current group duration
    const currentDuration = currentGroup.lastEnd - currentGroup.start;

    // Decision logic for when to finalize current group
    let shouldFinalize = false;

    // 1. Natural sentence endings
    if (text.endsWith('.') || text.endsWith('!') || text.endsWith('?')) {
      shouldFinalize = true;
    }
    // 2. Current group is long enough (>= 3 seconds) and...
    else if (currentDuration >= 3) {
      // Check for speech pause to next segment
      if (i + 1 < rawSegments.length) {
        const nextSegment = rawSegments[i + 1];
        const gap = nextSegment.start - segment.end;
        // Gap > 0.5 seconds indicates natural pause
        if (gap > 0.5) {
          shouldFinalize = true;
        }
      } else {
        // Last segment - finalize
        shouldFinalize = true;
      }
    }
    // 3. Force split if segment gets too long (>= 15 seconds)
    else if (currentDuration >= 15) {
      shouldFinalize = true;
    }

    if (shouldFinalize) {
      finalizeGroup();
    }
  }

  // Finalize any remaining group
  finalizeGroup();

  return smartSegments;
}