from sqlalchemy import Column, String, BigInteger, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

def generate_uuid():
    return str(uuid.uuid4())

class Video(Base):
    __tablename__ = "videos"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    duration = Column(Float, nullable=True)
    status = Column(String, nullable=False, default="uploaded")  # uploaded, processing, ready, failed
    video_type = Column(String, nullable=False, default="uploaded")  # uploaded, youtube
    youtube_id = Column(String, nullable=True)  # YouTube video ID for embedded videos
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationship with segments
    segments = relationship("VideoSegment", back_populates="video", cascade="all, delete-orphan")

class VideoSegment(Base):
    __tablename__ = "video_segments"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    video_id = Column(String, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship with video
    video = relationship("Video", back_populates="segments")