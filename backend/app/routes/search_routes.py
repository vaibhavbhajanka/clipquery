from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List
import json

from app.database import get_db
from app.models import Video as VideoModel, VideoSegment as VideoSegmentModel
from app.schemas import SearchRequest, SearchResult, VideoSegment
from app.services.search_service import unified_video_search, handle_chat_websocket

router = APIRouter()

@router.post("/search", response_model=List[SearchResult])
async def search_video(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """Search within video content using natural language"""
    try:
        # Use the unified search function
        search_results = await unified_video_search(db, request.video_id, request.query, top_k=3)
        
        # Convert to SearchResult objects
        results = [
            SearchResult(
                text=result["text"],
                start_time=result["start_time"],
                end_time=result["end_time"],
                confidence=result["confidence"]
            )
            for result in search_results
        ]
        
        return results
        
    except Exception as error:
        print(f"Search error: {error}")
        raise HTTPException(status_code=500, detail="Search failed")

@router.get("/videos/{video_id}/transcript", response_model=List[VideoSegment])
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

@router.websocket("/ws/chat/{video_id}")
async def chat_websocket(websocket: WebSocket, video_id: str):
    """WebSocket endpoint for real-time chat with video context"""
    print(f"WebSocket connection attempt for video {video_id}")
    
    # Accept the connection first
    await websocket.accept()
    print(f"WebSocket connected for video {video_id}")
    
    # Get database session
    db = next(get_db())
    
    try:
        await handle_chat_websocket(websocket, video_id, db)
    except WebSocketDisconnect:
        print(f"Client disconnected from chat for video {video_id}")
    except Exception as e:
        print(f"Chat WebSocket error: {e}")
        await websocket.close()