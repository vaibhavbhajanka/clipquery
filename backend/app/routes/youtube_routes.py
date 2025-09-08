from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Video as VideoModel
from app.schemas import Video, YouTubeUploadRequest
from app.services.youtube_service import extract_youtube_id, get_youtube_video_info
from app.services.video_service import process_video
from app.core.logging_config import get_logger

logger = get_logger("routes.youtube")

router = APIRouter()

@router.post("/upload-youtube", response_model=Video)
async def upload_youtube_video(
    request: YouTubeUploadRequest,
    db: Session = Depends(get_db)
):
    """Process a YouTube video URL and fetch its transcript"""
    try:
        logger.info(f"Received YouTube URL", extra={"url": request.url})
        
        # Extract YouTube video ID
        youtube_id = extract_youtube_id(request.url)
        logger.info(f"Extracted YouTube video ID", extra={"youtube_id": youtube_id, "url": request.url})
        
        # Check if this video already exists
        existing_video = db.query(VideoModel).filter(
            VideoModel.youtube_id == youtube_id,
            VideoModel.video_type == "youtube"
        ).first()
        
        if existing_video:
            logger.info(f"YouTube video already exists", extra={"video_id": existing_video.id, "youtube_id": youtube_id})
            return existing_video
        
        # Get video information
        video_info = get_youtube_video_info(youtube_id)
        
        # Check duration limit (3 minutes = 180 seconds)
        if video_info.get('duration') and video_info['duration'] > 180:
            minutes = int(video_info['duration'] // 60)
            seconds = int(video_info['duration'] % 60)
            raise HTTPException(
                status_code=400, 
                detail=f"YouTube video is {minutes}:{seconds:02d} long. Please use videos under 3 minutes."
            )
        
        # Create video record in database
        db_video = VideoModel(
            filename=f"youtube-{youtube_id}",
            original_name=video_info['title'][:100],  # Limit length
            file_path=f"youtube://{youtube_id}",  # Use special scheme for YouTube
            file_size=0,  # No file size for YouTube videos
            duration=video_info.get('duration'),
            status="uploaded",
            video_type="youtube",
            youtube_id=youtube_id
        )
        
        db.add(db_video)
        db.commit()
        db.refresh(db_video)
        
        logger.info(f"YouTube video saved to database", extra={"video_id": db_video.id, "youtube_id": youtube_id})
        
        # Process the video immediately (fetch transcript and create segments)
        await process_video(db_video.id, db)
        
        # Refresh to get updated status and segments
        db.refresh(db_video)
        
        return db_video
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as error:
        logger.error(f"YouTube upload failed", extra={"url": request.url}, exc_info=True)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process YouTube video: {str(error)}")