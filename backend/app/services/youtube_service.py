from fastapi import HTTPException
import os
import urllib.parse
import re


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
        print(f"Warning: Could not fetch YouTube video info: {e}")
        return {
            'title': f"YouTube Video {video_id}",
            'description': '',
            'duration': None,
            'channel_title': 'Unknown',
            'thumbnail': f"https://img.youtube.com/vi/{video_id}/default.jpg"
        }


def smart_segment_youtube_transcript(raw_segments: list) -> list:
    """
    Group YouTube's 1-2 second segments into natural speech boundaries like Whisper
    
    Strategy:
    - Group segments by natural speech pauses (silence gaps > 0.5s)
    - Respect sentence boundaries (., !, ?)  
    - Keep segments between 3-15 seconds (typical Whisper range)
    - Merge very short segments, split very long ones
    """
    if not raw_segments:
        return []
    
    smart_segments = []
    current_group = {
        "text_parts": [],
        "start": None,
        "last_end": None
    }
    
    def finalize_group():
        if current_group["text_parts"]:
            combined_text = " ".join(current_group["text_parts"]).strip()
            if combined_text:
                smart_segments.append({
                    "text": combined_text,
                    "start": current_group["start"],
                    "end": current_group["last_end"]
                })
        
        current_group["text_parts"] = []
        current_group["start"] = None
        current_group["last_end"] = None
    
    for i, segment in enumerate(raw_segments):
        text = segment["text"].strip()
        if not text:
            continue
            
        # Initialize first group
        if current_group["start"] is None:
            current_group["start"] = segment["start"]
        
        current_group["text_parts"].append(text)
        current_group["last_end"] = segment["end"]
        
        # Calculate current group duration
        current_duration = current_group["last_end"] - current_group["start"]
        
        # Decision logic for when to finalize current group
        should_finalize = False
        
        # 1. Natural sentence endings
        if text.endswith(('.', '!', '?')):
            should_finalize = True
        
        # 2. Current group is long enough (>= 3 seconds) and...
        elif current_duration >= 3:
            # Check for speech pause to next segment
            if i + 1 < len(raw_segments):
                next_segment = raw_segments[i + 1]
                gap = next_segment["start"] - segment["end"]
                # Gap > 0.5 seconds indicates natural pause
                if gap > 0.5:
                    should_finalize = True
            else:
                # Last segment - finalize
                should_finalize = True
        
        # 3. Force split if segment gets too long (>= 15 seconds)
        elif current_duration >= 15:
            should_finalize = True
        
        if should_finalize:
            finalize_group()
    
    # Finalize any remaining group
    finalize_group()
    
    return smart_segments


def fetch_youtube_transcript_smart(video_id: str) -> list:
    """Fetch YouTube transcript and apply smart segmentation to mimic Whisper's natural boundaries"""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        
        print(f"Fetching YouTube transcript for smart segmentation: {video_id}")
        
        # Get transcript using the correct API method  
        api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id, languages=['en'])
        
        # Convert to our segment format
        raw_segments = []
        for entry in transcript:
            raw_segments.append({
                "text": entry.text.strip(),
                "start": entry.start,
                "end": entry.start + entry.duration
            })
        
        # Apply smart segmentation to group into Whisper-like segments
        smart_segments = smart_segment_youtube_transcript(raw_segments)
        
        print(f"✅ YouTube transcript processed: {len(raw_segments)} raw → {len(smart_segments)} smart segments")
        return smart_segments
        
    except Exception as e:
        print(f"❌ Failed to fetch YouTube transcript: {e}")
        raise HTTPException(
            status_code=400, 
            detail=f"Could not fetch transcript from YouTube video. Make sure the video has captions available. Error: {str(e)}"
        )