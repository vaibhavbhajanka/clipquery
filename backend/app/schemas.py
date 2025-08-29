from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class VideoSegmentBase(BaseModel):
    text: str
    start_time: float
    end_time: float

class VideoSegmentCreate(VideoSegmentBase):
    video_id: str

class VideoSegment(VideoSegmentBase):
    id: str
    video_id: str
    created_at: datetime
    
    class Config:
        from_attributes = True
        alias_generator = lambda string: ''.join(
            word.capitalize() if i else word for i, word in enumerate(string.split('_'))
        )
        populate_by_name = True

class VideoBase(BaseModel):
    filename: str
    original_name: str
    file_path: str
    file_size: int
    duration: Optional[float] = None
    status: str = "uploaded"
    
    class Config:
        alias_generator = lambda string: ''.join(
            word.capitalize() if i else word for i, word in enumerate(string.split('_'))
        )
        populate_by_name = True

class VideoCreate(VideoBase):
    pass

class Video(VideoBase):
    id: str
    created_at: datetime
    updated_at: datetime
    segments: List[VideoSegment] = []
    
    class Config:
        from_attributes = True
        alias_generator = lambda string: ''.join(
            word.capitalize() if i else word for i, word in enumerate(string.split('_'))
        )
        populate_by_name = True

class ProcessRequest(BaseModel):
    video_id: str

class SearchRequest(BaseModel):
    query: str
    video_id: str

class SearchResult(BaseModel):
    text: str
    start_time: float
    end_time: float
    confidence: float
    
    class Config:
        # This will allow the API to return camelCase while using snake_case internally
        alias_generator = lambda string: ''.join(
            word.capitalize() if i else word for i, word in enumerate(string.split('_'))
        )
        populate_by_name = True

class ProcessingResult(BaseModel):
    success: bool
    segment_count: Optional[int] = None
    window_count: Optional[int] = None
    error: Optional[str] = None