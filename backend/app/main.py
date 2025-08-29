from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
import subprocess
import tempfile
import shutil
from datetime import datetime
from openai import OpenAI
try:
    from pinecone import Pinecone
except ImportError:
    # Fallback for older pinecone versions
    import pinecone
    Pinecone = pinecone
from dotenv import load_dotenv

from app.database import get_db, create_tables
from app.models import Video as VideoModel, VideoSegment as VideoSegmentModel
from app.schemas import (
    Video, VideoCreate, VideoSegment, ProcessRequest, 
    SearchRequest, SearchResult, ProcessingResult
)
from app.aws_utils import aws_manager

load_dotenv()

# Create tables on startup
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    yield
    # Shutdown (nothing to do for now)

app = FastAPI(title="ClipQuery Backend", version="1.0.0", lifespan=lifespan)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure uploads directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

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

@app.get("/")
async def root():
    return {"message": "ClipQuery Backend API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/upload", response_model=Video)
async def upload_video(
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a video file"""
    temp_file_path = None
    try:
        print(f"Received upload request for: {video.filename}")
        
        # Validate file type
        if not video.content_type or not video.content_type.startswith('video/'):
            raise HTTPException(status_code=400, detail="File must be a video")
        
        # Validate file size (500MB limit)
        max_size = 500 * 1024 * 1024
        if video.size and video.size > max_size:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 500MB")
        
        # Generate unique filename
        timestamp = int(datetime.now().timestamp())
        filename = f"{timestamp}-{video.filename}"
        
        # Read file content
        file_content = await video.read()
        file_size = len(file_content)
        
        # Server-side duration validation (as backup to client-side)
        if aws_manager:
            # Save to temp file for duration check (keep original extension)
            ext = os.path.splitext(video.filename)[1] if video.filename else '.mp4'
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            duration = aws_manager.validate_video_duration_server(temp_file_path)
            if duration and duration > 180:  # 3 minutes = 180 seconds
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                raise HTTPException(
                    status_code=400, 
                    detail=f"Video is {minutes}:{seconds:02d} long. Please upload videos under 3 minutes."
                )
            
            print(f"Video duration: {duration} seconds" if duration else "Duration validation skipped")
        
        # Upload to S3 if configured, otherwise save locally
        if aws_manager:
            success = aws_manager.upload_video(file_content, filename)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to upload video to cloud storage")
            
            file_path = f"s3://{aws_manager.bucket_name}/videos/{filename}"
            print(f"Video uploaded to S3: {file_path}")
        else:
            # Fallback to local storage
            file_path = os.path.join(UPLOAD_DIR, filename)
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
            print(f"Video saved locally: {file_path}")
        
        # Create video record in database
        db_video = VideoModel(
            filename=filename,
            original_name=video.filename or "unknown",
            file_path=file_path,
            file_size=file_size,
            duration=duration if 'duration' in locals() else None,
            status="uploaded"
        )
        
        db.add(db_video)
        db.commit()
        db.refresh(db_video)
        
        print(f"Video saved to database with ID: {db_video.id}")
        
        return db_video
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as error:
        print(f"Upload error: {error}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(error)}")
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                print(f"Error cleaning up temp file: {e}")
    
    

@app.post("/process", response_model=ProcessingResult)
async def process_video_endpoint(
    request: ProcessRequest,
    db: Session = Depends(get_db)
):
    """
    FastAPI endpoint: handles any file size with perfect timestamp accuracy
    """
    video_id = request.video_id
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
        
        # Handle S3 videos - download to temp file for processing
        if video_path.startswith('s3://') and aws_manager:
            print(f"Downloading video from S3 for processing: {video_path}")
            
            # Download from S3 to temp file
            import boto3
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
        
        # Create overlapping windows for precise search
        windows = create_overlapping_windows(processed_segments)
        print(f"Created {len(windows)} windows")
        
        # Generate embeddings and store in Pinecone (if configured)
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

@app.post("/search", response_model=List[SearchResult])
async def search_video(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """Search within video content using natural language"""
    try:
        query = request.query
        video_id = request.video_id
        
        # Check if Pinecone is configured
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if pinecone_api_key and pinecone_api_key != "your_pinecone_key_here":
            try:
                # Use Pinecone for semantic search
                openai_client = OpenAI()
                pc = Pinecone(api_key=pinecone_api_key)
                
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
                
                # Generate query embedding
                embedding = openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=query,
                )
                
                # Search Pinecone
                index = pc.Index(index_name)
                search_results = index.query(
                    vector=embedding.data[0].embedding,
                    filter={"video_id": video_id},
                    top_k=3,
                    include_metadata=True
                )
                
                results = [
                    SearchResult(
                        text=match.metadata.get("text", ""),
                        start_time=match.metadata.get("start_time", 0),
                        end_time=match.metadata.get("end_time", 0),
                        confidence=match.score or 0
                    )
                    for match in search_results.matches
                ]
                
                return results
                
            except Exception as pinecone_error:
                print(f"Pinecone search error: {pinecone_error}")
                # Fall through to database search
        
        # Fallback to database search
        segments = db.query(VideoSegmentModel).filter(
            VideoSegmentModel.video_id == video_id,
            VideoSegmentModel.text.ilike(f"%{query}%")
        ).order_by(VideoSegmentModel.start_time).limit(5).all()
        
        results = [
            SearchResult(
                text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                confidence=0.8  # Mock confidence for simple text search
            )
            for segment in segments
        ]
        
        return results
        
    except Exception as error:
        print(f"Search error: {error}")
        raise HTTPException(status_code=500, detail="Search failed")

@app.get("/video-url/{filename}")
async def get_video_url(filename: str, db: Session = Depends(get_db)):
    """Get the actual video URL (public S3 URL or local URL)"""
    try:
        # Find video in database
        video = db.query(VideoModel).filter(VideoModel.filename == filename).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # If using S3, return direct public S3 URL for streaming
        if aws_manager and video.file_path.startswith('s3://'):
            s3_url = aws_manager.get_video_url(filename)
            return {
                "url": s3_url, 
                "type": "s3-public",
                "headers": {
                    "Accept-Ranges": "bytes",
                    "Content-Type": "video/mp4"
                }
            }
        
        # Fallback to local URL
        local_file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(local_file_path):
            raise HTTPException(status_code=404, detail="Video file not found locally")
            
        local_url = f"http://localhost:8000/video/{filename}"
        return {
            "url": local_url, 
            "type": "local",
            "headers": {
                "Accept-Ranges": "bytes",
                "Content-Type": "video/mp4"
            }
        }
        
    except HTTPException:
        raise
    except Exception as error:
        print(f"Error getting video URL: {error}")
        raise HTTPException(status_code=500, detail="Failed to get video URL")

@app.get("/video/{filename}")
async def serve_video(filename: str, db: Session = Depends(get_db)):
    """Serve video file directly (for local storage only - S3 videos should use direct URLs)"""
    try:
        # Find video in database
        video = db.query(VideoModel).filter(VideoModel.filename == filename).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # For S3 videos, redirect to the public S3 URL instead of serving through backend
        if aws_manager and video.file_path.startswith('s3://'):
            s3_url = aws_manager.get_video_url(filename)
            print(f"Redirecting S3 video to direct URL: {s3_url}")
            return {"error": "S3 videos should be accessed directly", "redirect_url": s3_url}
        
        # Serve local file only
        local_file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(local_file_path):
            raise HTTPException(status_code=404, detail="Video file not found")
        
        # Use FileResponse which handles range requests automatically
        return FileResponse(
            local_file_path,
            media_type="video/mp4",
            headers={
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "Range, Content-Range",
                "Cache-Control": "max-age=3600",
            }
        )
        
    except HTTPException:
        raise
    except Exception as error:
        print(f"Video serving error: {error}")
        raise HTTPException(status_code=500, detail="Failed to serve video")

@app.get("/videos", response_model=List[Video])
async def get_videos(db: Session = Depends(get_db)):
    """Get all videos"""
    videos = db.query(VideoModel).order_by(VideoModel.created_at.desc()).all()
    return videos

@app.get("/videos/{video_id}", response_model=Video)
async def get_video(video_id: str, db: Session = Depends(get_db)):
    """Get a specific video by ID"""
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video

@app.get("/videos/{video_id}/transcript", response_model=List[VideoSegment])
async def get_video_transcript(video_id: str, db: Session = Depends(get_db)):
    """Get the complete transcript for a video"""
    try:
        # Check if video exists
        video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Get all segments ordered by start time
        segments = db.query(VideoSegmentModel).filter(
            VideoSegmentModel.video_id == video_id
        ).order_by(VideoSegmentModel.start_time).all()
        
        return segments
        
    except Exception as error:
        print(f"Transcript fetch error: {error}")
        raise HTTPException(status_code=500, detail="Failed to fetch transcript")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)