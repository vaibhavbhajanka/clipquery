from fastapi import HTTPException
from sqlalchemy.orm import Session
import os
import subprocess
import tempfile
import boto3
from openai import OpenAI

from app.models import Video as VideoModel, VideoSegment as VideoSegmentModel
from app.schemas import ProcessingResult
from app.aws_utils import aws_manager
from app.services.youtube_service import fetch_youtube_transcript_smart

try:
    from pinecone import Pinecone
except ImportError:
    import pinecone
    Pinecone = pinecone

def extract_audio_for_whisper(video_path: str) -> str:
    """
    Extract audio from video for large files
    Reduces 75MB video to ~1.5MB audio while preserving timestamps
    """
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_audio:
        cmd = [
            'ffmpeg', '-i', video_path,
            '-vn',  # No video
            '-acodec', 'libmp3lame',
            '-ab', '64k',  # Low bitrate for speech
            '-ac', '1',    # Mono
            '-ar', '16000',  # Whisper's preferred sample rate
            '-y',  # Overwrite
            temp_audio.name
        ]
        
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            return temp_audio.name
        except subprocess.CalledProcessError as e:
            print(f"FFmpeg error: {e.stderr}")
            raise HTTPException(status_code=500, detail=f"Audio extraction failed: {e.stderr}")

def create_overlapping_windows(segments: list, window_size: int = 10, overlap: int = 5) -> list:
    """Create 10-second overlapping windows for precise timestamp matching"""
    if not segments:
        return []
    
    windows = []
    current_time = 0
    last_end = max(segment['end'] for segment in segments)
    
    while current_time < last_end:
        window_end = current_time + window_size
        
        window_segments = []
        for segment in segments:
            # Check if segment overlaps with current window
            if (segment['start'] >= current_time and segment['start'] < window_end) or \
               (segment['end'] > current_time and segment['end'] <= window_end) or \
               (segment['start'] < current_time and segment['end'] > window_end):
                window_segments.append(segment)
        
        if window_segments:
            combined_text = " ".join([s['text'].strip() for s in window_segments])
            if combined_text.strip():  # Only add non-empty windows
                windows.append({
                    "text": combined_text.strip(),
                    "start_time": current_time,
                    "end_time": min(window_end, last_end)
                })
        
        current_time += overlap
    
    return windows

async def process_video(video_id: str, db: Session) -> ProcessingResult:
    """
    Process video with Whisper or YouTube transcript
    """
    temp_video_path = None
    
    try:
        # Get video from database
        db_video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if not db_video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get video path from database record
        video_path = db_video.file_path
        
        # Update status to processing
        db_video.status = "processing"
        db.commit()
        
        # Handle YouTube videos - process transcript directly
        if db_video.video_type == "youtube" and db_video.youtube_id:
            print(f"Processing YouTube video: {db_video.youtube_id}")
            
            # Check if transcript segments already exist
            existing_segments = db.query(VideoSegmentModel).filter(
                VideoSegmentModel.video_id == video_id
            ).count()
            
            if existing_segments > 0:
                print(f"Transcript segments already exist ({existing_segments} segments), skipping fetch")
                # Get existing segments for window creation
                db_segments = db.query(VideoSegmentModel).filter(
                    VideoSegmentModel.video_id == video_id
                ).order_by(VideoSegmentModel.start_time).all()
                processed_segments = [{
                    "text": seg.text,
                    "start": seg.start_time,
                    "end": seg.end_time
                } for seg in db_segments]
            else:
                # Fetch YouTube transcript with smart segmentation (Whisper-like)
                processed_segments = fetch_youtube_transcript_smart(db_video.youtube_id)
                
                # Store segments in database
                for segment in processed_segments:
                    db_segment = VideoSegmentModel(
                        video_id=video_id,
                        text=segment["text"],
                        start_time=segment["start"],
                        end_time=segment["end"]
                    )
                    db.add(db_segment)
            
            print(f"Processed {len(processed_segments)} YouTube transcript segments")
            
        else:
            # Handle uploaded videos - process with Whisper
            processed_segments = await process_uploaded_video(db_video, video_id, video_path, db)
        
        # Create overlapping windows for precise search
        windows = create_overlapping_windows(processed_segments)
        print(f"Created {len(windows)} search windows")
        
        # Generate embeddings and store in Pinecone (if configured)
        await store_embeddings_in_pinecone(video_id, windows)
        
        # Update video status to ready
        db_video.status = "ready"
        db.commit()
        
        return ProcessingResult(
            success=True,
            segment_count=len(processed_segments),
            window_count=len(windows)
        )
        
    except HTTPException:
        # Update video status to failed
        db_video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if db_video:
            db_video.status = "failed"
            db.commit()
        raise
    except Exception as e:
        # Update video status to failed
        db_video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if db_video:
            db_video.status = "failed"
            db.commit()
        
        print(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        # Clean up temp file if it was created for S3 video
        if temp_video_path and os.path.exists(temp_video_path):
            try:
                os.unlink(temp_video_path)
                print(f"Cleaned up temp file: {temp_video_path}")
            except Exception as e:
                print(f"Error cleaning up temp file: {e}")

async def process_uploaded_video(db_video, video_id: str, video_path: str, db: Session) -> list:
    """Process uploaded video with Whisper"""
    temp_video_path = None
    
    # Handle S3 videos - download to temp file for processing
    if video_path.startswith('s3://') and aws_manager:
        print(f"Downloading video from S3 for processing: {video_path}")
        
        # Download from S3 to temp file
        s3_client = boto3.client('s3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION')
        )
        
        # Extract bucket and key from path
        s3_parts = video_path.replace('s3://', '').split('/', 1)
        bucket = s3_parts[0]
        key = s3_parts[1] if len(s3_parts) > 1 else ''
        
        # Download to temp file (keep original extension)
        ext = os.path.splitext(db_video.filename)[1] if db_video.filename else '.mp4'
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
            s3_client.download_fileobj(bucket, key, temp_file)
            temp_video_path = temp_file.name
            video_path = temp_video_path
        
        print(f"Downloaded to temp file: {video_path}")
    
    # Check if local file exists
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")
    
    # Check file size
    file_size = os.path.getsize(video_path)
    size_mb = file_size / (1024 * 1024)
    
    print(f"Processing video: {video_id}, size: {size_mb:.1f}MB")
    
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Always extract audio for optimal performance (10x faster uploads, same accuracy)
    print(f"Extracting audio from {size_mb:.1f}MB video for faster processing")
    audio_path = extract_audio_for_whisper(video_path)
    
    try:
        with open(audio_path, 'rb') as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                file=audio_file,
                model="whisper-1",
                response_format="verbose_json"
            )
        segments = transcript.segments
    finally:
        # Cleanup temp audio file
        try:
            os.unlink(audio_path)
        except Exception as e:
            print(f"Warning: Could not cleanup temp audio file {audio_path}: {e}")
    
    # Convert to our format
    processed_segments = []
    for segment in segments:
        processed_segments.append({
            "text": segment.text,
            "start": segment.start,
            "end": segment.end
        })
    
    print(f"Processed {len(processed_segments)} segments")
    
    # Store segments in database
    for segment in processed_segments:
        db_segment = VideoSegmentModel(
            video_id=video_id,
            text=segment["text"],
            start_time=segment["start"],
            end_time=segment["end"]
        )
        db.add(db_segment)
    
    return processed_segments

async def store_embeddings_in_pinecone(video_id: str, windows: list):
    """Store embeddings in Pinecone if configured"""
    if os.getenv("PINECONE_API_KEY") and os.getenv("PINECONE_API_KEY") != "your_pinecone_key_here":
        try:
            pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
            
            # Create index if it doesn't exist
            index_name = os.getenv("PINECONE_INDEX_NAME", "clipquery-segments")
            if index_name not in [index.name for index in pc.list_indexes()]:
                print(f"Creating Pinecone index: {index_name}")
                pc.create_index(
                    name=index_name,
                    dimension=1536,  # text-embedding-3-small dimension
                    metric="cosine"
                )
                print(f"Created Pinecone index: {index_name}")
            
            index = pc.Index(index_name)
            openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            vectors_to_upsert = []
            for i, window in enumerate(windows):
                if not window["text"].strip():
                    continue
                    
                embedding_response = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=window["text"]
                )
                embedding = embedding_response.data[0].embedding
                
                vectors_to_upsert.append({
                    "id": f"{video_id}-{i}",
                    "values": embedding,
                    "metadata": {
                        "video_id": video_id,
                        "text": window["text"],
                        "start_time": window["start_time"],
                        "end_time": window["end_time"]
                    }
                })
            
            # Batch upsert to Pinecone
            if vectors_to_upsert:
                index.upsert(vectors=vectors_to_upsert)
                print(f"Stored {len(vectors_to_upsert)} vectors in Pinecone")
        except Exception as e:
            print(f"Pinecone storage failed: {e}")
            # Continue without failing the entire process