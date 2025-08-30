from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import os
import json

from app.database import create_tables
from app.routes.video_routes import router as video_router
from app.routes.youtube_routes import router as youtube_router
from app.routes.search_routes import router as search_router

load_dotenv()

# Create tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    create_tables()
    yield
    # Shutdown (nothing to do for now)

app = FastAPI(title="ClipQuery Backend", version="1.0.0", lifespan=lifespan)

# Enable CORS for Next.js frontend
# Get CORS origins from environment variable
cors_origins = os.getenv("CORS_ORIGINS", '["http://localhost:3000", "http://localhost:3001"]')
try:
    allowed_origins = json.loads(cors_origins)
except json.JSONDecodeError:
    # Fallback to default origins if parsing fails
    allowed_origins = ["http://localhost:3000", "http://localhost:3001"]

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