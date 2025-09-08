from fastapi import HTTPException
import os
import urllib.parse
import re
import httpx
from app.core.logging_config import get_logger

logger = get_logger("services.youtube")


def extract_youtube_id(url: str) -> str:
    """Extract YouTube video ID from various YouTube URL formats"""
    # Handle different YouTube URL formats
    if 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    elif 'youtube.com/watch' in url:
        parsed_url = urllib.parse.urlparse(url)
        return urllib.parse.parse_qs(parsed_url.query)['v'][0]
    elif 'youtube.com/embed/' in url:
        return url.split('youtube.com/embed/')[1].split('?')[0]
    else:
        raise ValueError("Invalid YouTube URL format")


def get_youtube_video_info(video_id: str) -> dict:
    """Get YouTube video information using YouTube Data API (optional - can work without API key)"""
    try:
        from googleapiclient.discovery import build
        
        # Check if we have YouTube API key (optional)
        youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        if youtube_api_key:
            youtube = build('youtube', 'v3', developerKey=youtube_api_key)
            
            # Get video details
            request = youtube.videos().list(
                part="snippet,contentDetails",
                id=video_id
            )
            response = request.execute()
            
            if response['items']:
                item = response['items'][0]
                snippet = item['snippet']
                content_details = item['contentDetails']
                
                # Parse duration (PT4M13S -> seconds)
                duration_str = content_details['duration']
                duration_match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
                if duration_match:
                    hours = int(duration_match.group(1) or 0)
                    minutes = int(duration_match.group(2) or 0)
                    seconds = int(duration_match.group(3) or 0)
                    total_seconds = hours * 3600 + minutes * 60 + seconds
                else:
                    total_seconds = None
                
                return {
                    'title': snippet['title'],
                    'description': snippet['description'],
                    'duration': total_seconds,
                    'channel_title': snippet['channelTitle'],
                    'thumbnail': snippet['thumbnails']['default']['url']
                }
        
        # Fallback: basic info without API
        return {
            'title': f"YouTube Video {video_id}",
            'description': '',
            'duration': None,
            'channel_title': 'Unknown',
            'thumbnail': f"https://img.youtube.com/vi/{video_id}/default.jpg"
        }
        
    except Exception as e:
        logger.warning(f"Could not fetch YouTube video info", extra={"video_id": video_id}, exc_info=True)
        return {
            'title': f"YouTube Video {video_id}",
            'description': '',
            'duration': None,
            'channel_title': 'Unknown',
            'thumbnail': f"https://img.youtube.com/vi/{video_id}/default.jpg"
        }


def split_large_segments(segments: list) -> list:
    """Split large segments (blobs) into smaller, searchable chunks"""
    result = []
    target_duration = 8  # Target 8 seconds per segment
    
    for segment in segments:
        text = segment["text"]
        duration = segment["end"] - segment["start"]
        
        if duration <= 15:  # If already reasonable size, keep it
            result.append(segment)
            continue
        
        # Split by sentences first
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # If no sentence boundaries, split by word count
        if len(sentences) <= 1:
            words = text.split()
            words_per_segment = max(20, len(words) * target_duration // duration)
            sentences = [' '.join(words[i:i+words_per_segment]) 
                        for i in range(0, len(words), words_per_segment)]
        
        # Create new segments from sentences
        current_text = ""
        current_start = segment["start"]
        time_per_char = duration / len(text) if text else 1
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            if current_text and (
                len(current_text) > 200 or  # Enough text
                len(current_text + " " + sentence) > 400  # Would be too long
            ):
                # Finalize current segment
                result.append({
                    "text": current_text.strip(),
                    "start": current_start,
                    "end": current_start + len(current_text) * time_per_char
                })
                current_start = current_start + len(current_text) * time_per_char
                current_text = sentence
            else:
                current_text = (current_text + " " + sentence).strip()
        
        # Add remaining text
        if current_text:
            result.append({
                "text": current_text.strip(),
                "start": current_start,
                "end": segment["end"]
            })
    
    return result


def group_small_segments(segments: list) -> list:
    """Group small segments into larger, more meaningful chunks"""
    result = []
    current_group = {
        "text_parts": [],
        "start": None,
        "end": None
    }
    
    for i, segment in enumerate(segments):
        text = segment["text"].strip()
        if not text:
            continue
        
        # Initialize first group
        if current_group["start"] is None:
            current_group["start"] = segment["start"]
        
        current_group["text_parts"].append(text)
        current_group["end"] = segment["end"]
        
        # Calculate current group duration
        current_duration = current_group["end"] - current_group["start"]
        
        # Check if we should finalize this group
        should_finalize = False
        
        # Check for natural breaks
        if current_duration >= 5:  # Minimum 5 seconds
            if text.endswith(('.', '!', '?')):  # Sentence ending
                should_finalize = True
            elif current_duration >= 10:  # Force at 10 seconds
                should_finalize = True
            elif i + 1 < len(segments):
                # Check for pause between segments
                next_segment = segments[i + 1]
                gap = next_segment["start"] - segment["end"]
                if gap > 0.5:  # Natural pause
                    should_finalize = True
        
        # Force split at 15 seconds
        if current_duration >= 15:
            should_finalize = True
        
        # Last segment
        if i == len(segments) - 1:
            should_finalize = True
        
        if should_finalize and current_group["text_parts"]:
            result.append({
                "text": " ".join(current_group["text_parts"]),
                "start": current_group["start"],
                "end": current_group["end"]
            })
            current_group = {
                "text_parts": [],
                "start": None,
                "end": None
            }
    
    return result


def smart_segment_youtube_transcript(raw_segments: list) -> list:
    """
    Adaptive segmentation for YouTube transcripts that handles both:
    - Many small segments (1-2 seconds each) → Group them
    - Few large segments (entire transcript as blob) → Split them
    
    Target: 5-15 second segments for optimal searchability
    """
    print(f"\n========== SMART SEGMENTATION ==========")
    print(f"Input: {len(raw_segments)} raw segments")
    
    if not raw_segments:
        return []
    
    # Analyze segment characteristics
    avg_duration = sum(s["end"] - s["start"] for s in raw_segments) / len(raw_segments)
    total_duration = raw_segments[-1]["end"] - raw_segments[0]["start"]
    
    print(f"Average segment duration: {avg_duration:.1f}s")
    print(f"Total duration: {total_duration:.1f}s")
    
    # Determine strategy based on segment characteristics
    if len(raw_segments) == 1 or avg_duration > 30:
        # Single blob or very large segments - need splitting
        print("Strategy: SPLITTING large segments")
        result = split_large_segments(raw_segments)
    elif avg_duration < 5:
        # Many small segments - need grouping
        print("Strategy: GROUPING small segments")
        result = group_small_segments(raw_segments)
    else:
        # Segments are already reasonable size
        print("Strategy: KEEPING segments as-is (already good size)")
        result = raw_segments
    
    print(f"Output: {len(result)} smart segments")
    if len(result) > 0:
        print(f"First segment: {result[0].get('text', '')[:80]}...")
        print(f"Average duration: {total_duration / len(result):.1f}s per segment")
    print(f"========== END SMART SEGMENTATION ==========\n")
    
    return result


async def fetch_youtube_transcript_via_third_party(video_id: str) -> list:
    """Fetch YouTube transcript using third-party youtube-transcript.io API"""
    api_token = os.getenv("YOUTUBE_TRANSCRIPT_API_TOKEN")
    if not api_token:
        raise Exception("YOUTUBE_TRANSCRIPT_API_TOKEN not configured")
    
    api_url = "https://www.youtube-transcript.io/api/transcripts"
    
    try:
        print(f"\n========== [DEBUG] Fetching YouTube transcript via third-party API ==========\nVideo ID: {video_id}\n")
        # logger.info(f"Fetching YouTube transcript via third-party API", extra={"video_id": video_id})
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Basic {api_token}",
                    "Content-Type": "application/json"
                },
                json={"ids": [video_id]}
            )
            
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "10")
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Please retry after {retry_after} seconds."
            )
            
        if response.status_code != 200:
            raise Exception(f"API returned HTTP {response.status_code}: {response.text[:200]}")
            
        data = response.json()
        print(f"\n[API RESPONSE] Type: {type(data)}")
        
        # Response can be either a list or a direct object
        if isinstance(data, list) and len(data) > 0:
            video_data = data[0]
            print(f"[API RESPONSE] Using first item from list")
        elif isinstance(data, dict):
            video_data = data
            print(f"[API RESPONSE] Using direct dict response")
        else:
            raise Exception("Invalid response format from transcript API")
        
        # Check if this is the right video (only if id field exists)
        if 'id' in video_data and video_data.get('id') != video_id:
            raise Exception(f"Received data for wrong video ID: {video_data.get('id')}")
        
        print(f"[API RESPONSE] Keys in response: {list(video_data.keys())[:5]}...")
        
        # Get tracks
        tracks = video_data.get('tracks', [])
        
        # Find English track (prefer non-auto-generated)
        en_track = None
        for track in tracks:
            if track.get('language') == 'en':
                en_track = track
                break
        
        # Fallback to any English track
        if not en_track:
            for track in tracks:
                lang = track.get('language', '')
                if 'English' in lang or lang == 'en' or lang.startswith('en'):
                    en_track = track
                    break
        
        if not en_track:
            raise Exception("No English transcript available for this video")
        
        # Extract transcript segments
        transcript = en_track.get('transcript', [])
        if not transcript:
            raise Exception("English track has no transcript data")
        
        print(f"[TRANSCRIPT] Found {len(transcript)} raw segments from API")
        
        # Decode HTML entities
        import html
        
        segments = []
        for item in transcript:
            if isinstance(item, dict) and "text" in item:
                start = float(item.get("start", 0))
                duration = float(item.get("dur", 0))
                # Decode HTML entities like &#39; to '
                decoded_text = html.unescape(item.get("text", ""))
                segments.append({
                    "text": decoded_text,
                    "start": start,
                    "end": start + duration
                })
        
        # Apply smart segmentation
        smart_segments = smart_segment_youtube_transcript(segments)
        print(f"\n========== [SUCCESS] Third-party API transcript fetched ==========\nVideo ID: {video_id}\nRaw segments: {len(segments)}\nSmart segments: {len(smart_segments)}\n")
        # logger.info(f"Successfully fetched transcript via third-party API", extra={
        #     "video_id": video_id, 
        #     "raw_segments": len(segments),
        #     "smart_segments": len(smart_segments)
        # })
        
        return smart_segments
        
        raise Exception("Invalid response format from transcript API")
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n========== [ERROR] Third-party transcript API failed ==========\nVideo ID: {video_id}\nError: {str(e)}\n")
        # logger.error(f"Third-party transcript API failed", extra={"video_id": video_id}, exc_info=True)
        raise Exception(f"Third-party transcript API failed: {str(e)}")


async def fetch_youtube_transcript_via_worker(video_id: str) -> list:
    """Fetch YouTube transcript using Cloudflare Worker (fallback method)"""
    worker_url = os.getenv("CLOUDFLARE_WORKER_URL")
    if not worker_url:
        raise Exception("No Cloudflare Worker URL configured")
    
    try:
        print(f"\n========== [DEBUG] Fetching YouTube transcript via Cloudflare Worker ==========\nVideo ID: {video_id}\nWorker URL: {worker_url}\n")
        # logger.info(f"Fetching YouTube transcript via Cloudflare Worker", extra={"video_id": video_id, "worker_url": worker_url})
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(f"{worker_url}/?v={video_id}")
            
        if response.status_code != 200:
            raise Exception(f"Worker returned HTTP {response.status_code}: {response.text[:200]}")
            
        data = response.json()
        
        if not data.get("success"):
            raise Exception(data.get("error", "Unknown worker error"))
            
        segments = data.get("segments", [])
        
        print(f"\n========== [SUCCESS] Cloudflare Worker transcript fetched ==========\nVideo ID: {video_id}\nSegment count: {len(segments)}\n")
        # logger.info(f"Successfully fetched transcript via Cloudflare Worker", extra={
        #     "video_id": video_id, 
        #     "segment_count": len(segments)
        # })
        
        return segments
        
    except Exception as e:
        print(f"\n========== [ERROR] Cloudflare Worker failed ==========\nVideo ID: {video_id}\nError: {str(e)}\n")
        # logger.warning(f"Cloudflare Worker failed", extra={"video_id": video_id}, exc_info=True)
        raise Exception(f"Cloudflare Worker failed: {str(e)}")


def fetch_youtube_transcript_smart(video_id: str) -> list:
    """Fetch YouTube transcript using Innertube API and apply smart segmentation (fallback method)"""
    try:
        import requests
        import re
        import xml.etree.ElementTree as ET
        
        print(f"\n========== [DEBUG] Fetching YouTube transcript using Innertube API ==========\nVideo ID: {video_id}\n")
        # logger.info(f"Fetching YouTube transcript using Innertube API", extra={"video_id": video_id})
        
        # Step 1: Get INNERTUBE_API_KEY from video page
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"[DEBUG] Fetching video page for API key - video_url: {video_url}")
        # logger.debug(f"Fetching video page for API key", extra={"video_url": video_url})
        
        response = requests.get(video_url, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch video page: HTTP {response.status_code}")
            
        # Extract API key using regex
        api_key_match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', response.text)
        if not api_key_match:
            raise Exception("Could not extract INNERTUBE_API_KEY from video page")
            
        api_key = api_key_match.group(1)
        print(f"[DEBUG] Extracted Innertube API key for video_id: {video_id}")
        # logger.debug(f"Extracted Innertube API key", extra={"video_id": video_id})
        
        # Step 2: Call player API impersonating Android client
        player_url = f"https://www.youtube.com/youtubei/v1/player?key={api_key}"
        player_body = {
            "context": {
                "client": {
                    "clientName": "ANDROID",
                    "clientVersion": "20.10.38"
                }
            },
            "videoId": video_id
        }
        
        print(f"[DEBUG] Calling Innertube player API as Android client for video_id: {video_id}")
        # logger.debug(f"Calling Innertube player API as Android client", extra={"video_id": video_id})
        player_response = requests.post(
            player_url,
            headers={"Content-Type": "application/json"},
            json=player_body,
            timeout=30
        )
        
        if player_response.status_code != 200:
            raise Exception(f"Player API failed: HTTP {player_response.status_code}")
            
        player_data = player_response.json()
        
        # Step 3: Extract caption track URL
        captions = player_data.get("captions", {})
        caption_tracks = captions.get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])
        
        if not caption_tracks:
            raise Exception("No caption tracks found in video")
            
        print(f"[DEBUG] Found caption tracks - tracks_count: {len(caption_tracks)}, video_id: {video_id}")
        # logger.debug(f"Found caption tracks", extra={"tracks_count": len(caption_tracks), "video_id": video_id})
        
        # Find English track
        en_track = None
        for track in caption_tracks:
            if track.get("languageCode") == "en":
                en_track = track
                break
                
        if not en_track:
            raise Exception("No English captions found for this video")
            
        caption_url = en_track["baseUrl"]
        # Remove format parameter to get raw XML
        caption_url = re.sub(r'&fmt=\w+', '', caption_url)

        # Step 4: Fetch and parse XML captions
        print(f"[DEBUG] Fetching captions XML for video_id: {video_id}")
        # logger.debug(f"Fetching captions XML", extra={"video_id": video_id})
        caption_response = requests.get(caption_url, timeout=30)
        
        if caption_response.status_code != 200:
            raise Exception(f"Failed to fetch captions: HTTP {caption_response.status_code}")
            
        xml_content = caption_response.text
        root = ET.fromstring(xml_content)
        
        # Convert XML to our segment format
        raw_segments = []
        for text_elem in root.findall("text"):
            start_time = float(text_elem.get("start", 0))
            duration = float(text_elem.get("dur", 0))
            text_content = text_elem.text or ""
            
            if text_content.strip():  # Only add non-empty segments
                raw_segments.append({
                    "text": text_content.strip(),
                    "start": start_time,
                    "end": start_time + duration
                })
        
        # Apply smart segmentation to group into Whisper-like segments
        smart_segments = smart_segment_youtube_transcript(raw_segments)

        print(f"\n========== [SUCCESS] Innertube API transcript processed ==========\nVideo ID: {video_id}\nRaw segments: {len(raw_segments)}\nSmart segments: {len(smart_segments)}\n")
        # logger.info(f"YouTube transcript processed", extra={
        #     "video_id": video_id,
        #     "raw_segments": len(raw_segments), 
        #     "smart_segments": len(smart_segments)
        # })
        return smart_segments
        
    except Exception as e:
        print(f"\n========== [ERROR] Failed to fetch YouTube transcript via Innertube API ==========\nVideo ID: {video_id}\nError: {str(e)}\n")
        # logger.error(f"Failed to fetch YouTube transcript via Innertube API", extra={"video_id": video_id}, exc_info=True)
        
        # Provide more specific error messages based on the error
        error_msg = str(e).lower()
        if "no caption tracks found" in error_msg or "no english captions" in error_msg:
            detail = "This YouTube video does not have English captions available."
        elif "failed to fetch video page" in error_msg:
            detail = "Could not access YouTube video. Video may be private or deleted."
        elif "innertube_api_key" in error_msg:
            detail = "YouTube API access failed. Please try again later."
        else:
            detail = "Could not fetch transcript from YouTube video. Please try again or ensure the video has captions available."
            
        raise HTTPException(status_code=500, detail=detail)


async def fetch_youtube_transcript(video_id: str) -> list:
    """Main function to fetch YouTube transcript - tries third-party API first, then Cloudflare Worker, then fallback to direct API"""
    
    # Try third-party API first if configured
    api_token = os.getenv("YOUTUBE_TRANSCRIPT_API_TOKEN")
    if api_token:
        try:
            print(f"\n========== ATTEMPTING THIRD-PARTY API ==========\nVideo ID: {video_id}\nAPI Token: {api_token[:10]}...\n", flush=True)
            # logger.info(f"Attempting YouTube transcript fetch via third-party API", extra={"video_id": video_id})
            return await fetch_youtube_transcript_via_third_party(video_id)
        except Exception as e:
            print(f"\n========== WARNING: Third-party API failed, trying other methods ==========\nVideo ID: {video_id}\nError: {str(e)}\n")
            # logger.warning(f"Third-party API failed, trying other methods", extra={"video_id": video_id}, exc_info=True)
    else:
        print(f"\n========== NO YOUTUBE_TRANSCRIPT_API_TOKEN configured ==========\nSkipping third-party API for video_id: {video_id}\n")
        # logger.info(f"No YOUTUBE_TRANSCRIPT_API_TOKEN configured, skipping third-party API", extra={"video_id": video_id})
    
    # Try Cloudflare Worker as second option
    worker_url = os.getenv("CLOUDFLARE_WORKER_URL")
    if worker_url:
        try:
            print(f"\n========== ATTEMPTING CLOUDFLARE WORKER ==========\nVideo ID: {video_id}\n")
            # logger.info(f"Attempting YouTube transcript fetch via Cloudflare Worker", extra={"video_id": video_id})
            return await fetch_youtube_transcript_via_worker(video_id)
        except Exception as e:
            print(f"\n========== WARNING: Cloudflare Worker failed ==========\nFalling back to direct API for video_id: {video_id}\nError: {str(e)}\n")
            # logger.warning(f"Cloudflare Worker failed, falling back to direct API", extra={"video_id": video_id}, exc_info=True)
    else:
        print(f"\n========== NO CLOUDFLARE WORKER configured ==========\nUsing direct API for video_id: {video_id}\n")
        # logger.info(f"No Cloudflare Worker configured, using direct API", extra={"video_id": video_id})
    
    # Fallback to direct Innertube API
    try:
        print(f"\n========== ATTEMPTING DIRECT INNERTUBE API ==========\nVideo ID: {video_id}\n")
        # logger.info(f"Attempting YouTube transcript fetch via direct Innertube API", extra={"video_id": video_id})
        return fetch_youtube_transcript_smart(video_id)
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except Exception as e:
        print(f"\n========== ERROR: ALL YOUTUBE TRANSCRIPT METHODS FAILED ==========\nVideo ID: {video_id}\nError: {str(e)}\n")
        # logger.error(f"All YouTube transcript methods failed", extra={"video_id": video_id}, exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="Could not fetch transcript from YouTube video. Please try again later."
        )