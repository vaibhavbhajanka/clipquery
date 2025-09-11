from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import os
import tempfile
from datetime import datetime

from app.database import get_db
from app.models import Video as VideoModel
from app.schemas import Video, ProcessRequest, ProcessingResult
from pydantic import BaseModel
from app.aws_utils import aws_manager
from app.services.video_service import process_video
from app.core.logging_config import get_logger
from app.utils.retry import retry_async

logger = get_logger("routes.video")

router = APIRouter()

# Ensure uploads directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Pydantic models for presigned uploads
class PresignedUploadRequest(BaseModel):
    filename: str
    content_type: str = "video/mp4"

class CompleteUploadRequest(BaseModel):
    filename: str
    original_name: str
    file_size: int
    duration: float = None

@router.post("/get-upload-url")
@retry_async(max_retries=3, delay=1.0, backoff=2.0)
async def get_presigned_upload_url(request: PresignedUploadRequest):
    """Generate a presigned URL for direct S3 upload"""
    if not aws_manager:
        raise HTTPException(status_code=503, detail="S3 upload not configured")
    
    # Generate unique filename with timestamp
    timestamp = int(datetime.now().timestamp())
    unique_filename = f"{timestamp}-{request.filename}"
    
    presigned_data = aws_manager.generate_presigned_upload_url(
        unique_filename, 
        request.content_type
    )
    
    if not presigned_data:
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")
    
    return {
        "upload_url": presigned_data["url"],
        "fields": presigned_data["fields"],
        "filename": unique_filename
    }

@router.post("/complete-upload", response_model=Video)
@retry_async(max_retries=3, delay=1.0, backoff=2.0)
async def complete_upload(request: CompleteUploadRequest, db: Session = Depends(get_db)):
    """Complete the upload process by creating database record"""
    try:
        # Create video record in database
        file_path = f"s3://{aws_manager.bucket_name}/videos/{request.filename}" if aws_manager else f"uploads/{request.filename}"
        
        db_video = VideoModel(
            filename=request.filename,
            original_name=request.original_name,
            file_path=file_path,
            file_size=request.file_size,
            duration=request.duration,
            status="uploaded"
        )
        
        db.add(db_video)
        db.commit()
        db.refresh(db_video)
        
        logger.info(f"Video record created with ID: {db_video.id}")
        return db_video
        
    except Exception as error:
        logger.error(f"Complete upload error: {error}")
        raise HTTPException(status_code=500, detail=f"Failed to complete upload: {str(error)}")

@router.post("/upload", response_model=Video)
async def upload_video(
    video: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload a video file"""
    temp_file_path = None
    try:
        logger.info(f"Received upload request for: {video.filename}")
        
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
            
            logger.info(f"Video duration: {duration} seconds" if duration else "Duration validation skipped")
        
        # Upload to S3 if configured, otherwise save locally
        if aws_manager:
            logger.info(f"AWS Manager available, uploading {filename} to S3 bucket: {aws_manager.bucket_name}")
            success = aws_manager.upload_video(file_content, filename)
            if not success:
                raise HTTPException(status_code=500, detail="Failed to upload video to cloud storage")
            
            file_path = f"s3://{aws_manager.bucket_name}/videos/{filename}"
            logger.info(f"Video uploaded to S3: {file_path}")
        else:
            # Fallback to local storage
            logger.warning(f"No AWS Manager - saving {filename} locally (AWS credentials missing?)")
            file_path = os.path.join(UPLOAD_DIR, filename)
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
            logger.info(f"Video saved locally: {file_path}")
        
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
        
        logger.info(f"Video saved to database with ID: {db_video.id}")
        
        return db_video
        
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as error:
        logger.error(f"Upload error: {error}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(error)}")
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Error cleaning up temp file: {e}")

@router.post("/process", response_model=ProcessingResult)
async def process_video_endpoint(
    request: ProcessRequest,
    db: Session = Depends(get_db)
):
    """Process video with Whisper or YouTube transcript"""
    return await process_video(request.video_id, db)

@router.get("/video-url/{filename}")
async def get_video_url(filename: str, db: Session = Depends(get_db)):
    """Get the actual video URL (public S3 URL, local URL, or YouTube embed URL)"""
    try:
        # Find video in database
        video = db.query(VideoModel).filter(VideoModel.filename == filename).first()
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        # Handle YouTube videos
        if video.video_type == "youtube" and video.youtube_id:
            return {
                "url": f"https://www.youtube.com/embed/{video.youtube_id}?enablejsapi=1",
                "type": "youtube",
                "youtube_id": video.youtube_id,
                "headers": {}
            }
        
        # If using S3, return direct public S3 URL for streaming
        if aws_manager and video.file_path.startswith('s3://'):
            try:
                s3_url = aws_manager.get_video_url(filename)
                logger.info(f"Resolved S3 URL for {filename}: {s3_url}")
                return {
                    "url": s3_url, 
                    "type": "s3-public",
                    "headers": {
                        "Accept-Ranges": "bytes",
                        "Content-Type": "video/mp4"
                    }
                }
            except Exception as e:
                logger.error(f"Error getting S3 URL for {filename}: {e}")
                # Fall through to local fallback
        
        # Fallback to local URL
        local_file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(local_file_path):
            raise HTTPException(status_code=404, detail="Video file not found locally")
            
        # Use environment variable for deployed backend URL
        base_url = os.getenv("API_BASE_URL")
        if not base_url:
            # If no API_BASE_URL is set, this means we're in a misconfigured deployment
            raise HTTPException(status_code=500, detail="Backend API_BASE_URL not configured for video serving")
        local_url = f"{base_url}/video/{filename}"
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
        logger.error(f"Error getting video URL: {error}")
        raise HTTPException(status_code=500, detail="Failed to get video URL")

@router.get("/video/{filename}")
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
            logger.info(f"Redirecting S3 video to direct URL: {s3_url}")
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
        logger.error(f"Video serving error: {error}")
        raise HTTPException(status_code=500, detail="Failed to serve video")

@router.get("/videos", response_model=List[Video])
async def get_videos(db: Session = Depends(get_db)):
    """Get all videos"""
    videos = db.query(VideoModel).order_by(VideoModel.created_at.desc()).all()
    return videos

@router.get("/videos/{video_id}", response_model=Video)
async def get_video(video_id: str, db: Session = Depends(get_db)):
    """Get a specific video by ID"""
    video = db.query(VideoModel).filter(VideoModel.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video