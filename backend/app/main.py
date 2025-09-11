from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import os
import json

from app.core.logging_config import setup_logging, get_logger
from app.database import create_tables, get_db
from app.routes.video_routes import router as video_router
from app.routes.youtube_routes import router as youtube_router
from app.routes.search_routes import router as search_router
from app.aws_utils import aws_manager

load_dotenv()
setup_logging()

logger = get_logger("main")

# Create tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting ClipQuery Backend API")
    try:
        # Create database tables
        create_tables()
        logger.info("Database tables created successfully")
        
        # Warm up database connection pool
        await warm_up_database()
        
        # Warm up AWS S3 connection if configured
        await warm_up_aws_services()
        
        logger.info("All services warmed up successfully - ready to accept requests")
        
    except Exception as e:
        logger.error("Failed to initialize services", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down ClipQuery Backend API")

async def warm_up_database():
    """Warm up database connection pool"""
    try:
        from sqlalchemy import text
        db = next(get_db())
        # Execute a simple query to establish connections
        result = db.execute(text("SELECT 1"))
        db.close()
        logger.info("Database connection pool warmed up successfully")
    except Exception as e:
        logger.warning("Database warm-up failed", exc_info=True)
        # Don't fail startup, just log the issue

async def warm_up_aws_services():
    """Warm up AWS S3 connection if configured"""
    if aws_manager:
        try:
            # AWS manager already validates connection on init
            logger.info("AWS S3 services warmed up successfully")
        except Exception as e:
            logger.warning("AWS S3 warm-up failed", exc_info=True)
            # Don't fail startup, just log the issue
    else:
        logger.info("AWS S3 not configured - skipping S3 warm-up")

app = FastAPI(title="ClipQuery Backend", version="1.0.0", lifespan=lifespan)

# Enable CORS for Next.js frontend
# Get CORS origins from environment variable
cors_origins = os.getenv("CORS_ORIGINS", '["http://localhost:3000", "http://localhost:3001"]')
try:
    allowed_origins = json.loads(cors_origins)
    logger.info(f"CORS configured for origins: {allowed_origins}")
except json.JSONDecodeError:
    # Fallback to default origins if parsing fails
    allowed_origins = ["http://localhost:3000", "http://localhost:3001"]
    logger.warning(f"Invalid CORS_ORIGINS format, using defaults: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - keep original paths for compatibility
app.include_router(video_router, tags=["videos"])
app.include_router(youtube_router, tags=["youtube"])
app.include_router(search_router, tags=["search"])

@app.get("/")
async def root():
    return {"message": "ClipQuery Backend API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)