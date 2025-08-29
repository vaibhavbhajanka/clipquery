# ClipQuery

Natural language video search powered by AI. Upload videos and search through them using natural language queries with precise timestamp results.

## Features

- **Smart Video Upload**: Support for MP4, MOV, AVI, MKV, WebM files up to 500MB
- **AI-Powered Transcription**: Automatic speech-to-text using OpenAI Whisper
- **Semantic Search**: Natural language search through video content using embeddings
- **Precise Timestamps**: Jump to exact moments in videos based on search results
- **Cloud Storage**: Optional AWS S3 integration for scalable video storage
- **Real-time Processing**: Live transcript viewing and search capabilities

##  Architecture

### Backend (FastAPI + Python)
- **FastAPI** web framework with async support
- **SQLAlchemy** ORM with PostgreSQL (Supabase)
- **OpenAI Whisper** for speech-to-text transcription
- **Pinecone** vector database for semantic search
- **AWS S3** for cloud video storage
- **FFmpeg** for video processing

### Frontend (Next.js + TypeScript)
- **Next.js 15** with App Router
- **React 19** with TypeScript
- **Tailwind CSS** for styling
- **React Dropzone** for file uploads
- **React Player** for video playback

##  Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- FFmpeg installed
- PostgreSQL database (Supabase recommended)
- OpenAI API key

### Backend Setup

1. **Clone and navigate to backend:**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

3. **Required environment variables:**
   ```env
   # Database (Supabase PostgreSQL)
   user=your_supabase_user
   password=your_supabase_password
   host=your_supabase_host
   port=6543
   dbname=postgres

   # OpenAI API
   OPENAI_API_KEY=your_openai_api_key
   ```

4. **Optional services (for enhanced features):**
   ```env
   # Pinecone (for semantic search)
   PINECONE_API_KEY=your_pinecone_api_key
   PINECONE_INDEX_NAME=clipquery-segments

   # AWS S3 (for cloud storage)
   AWS_ACCESS_KEY_ID=your_aws_access_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret_key
   AWS_REGION=us-west-1
   AWS_S3_BUCKET=your_s3_bucket_name
   ```

5. **Start the backend:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

### Frontend Setup

1. **Navigate to frontend:**
   ```bash
   cd frontend
   npm install
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env.local
   # Edit .env.local if needed (defaults to localhost:8000)
   ```

3. **Start the frontend:**
   ```bash
   npm run dev
   ```

4. **Open your browser:**
   Visit [http://localhost:3000](http://localhost:3000)

## 📋 API Documentation

### Core Endpoints

- `POST /upload` - Upload video files
- `POST /process` - Process uploaded videos for search
- `POST /search` - Search through video content
- `GET /videos/{id}/transcript` - Get full video transcript
- `GET /video-url/{filename}` - Get video streaming URL

### Example API Usage

```python
import requests

# Upload video
files = {'video': open('video.mp4', 'rb')}
response = requests.post('http://localhost:8000/upload', files=files)
video = response.json()

# Process video
response = requests.post('http://localhost:8000/process', 
    json={'video_id': video['id']})

# Search video
response = requests.post('http://localhost:8000/search',
    json={'query': 'machine learning', 'video_id': video['id']})
results = response.json()
```

##  Docker Deployment

### Backend Only
```bash
cd backend
docker build -t clipquery-backend .
docker run -p 8000:8000 --env-file .env clipquery-backend
```

### Full Stack (Coming Soon)
Docker Compose configuration for full-stack deployment.

## Configuration

### Database Setup
1. Create a [Supabase](https://supabase.com) project
2. Get your PostgreSQL connection details
3. Update your `.env` file with database credentials

### Cloud Services

**Pinecone (Semantic Search)**
- Creates better search results using AI embeddings
- Automatically creates required index on first use
- Falls back to basic text search if not configured

**AWS S3 (Video Storage)**
- Enables cloud storage for better scalability  
- Supports direct video streaming from S3
- Falls back to local storage if not configured

##  Development

### Backend Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn app.main:app --reload
```

### Frontend Development
```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build
```

##  Usage

1. **Upload Video**: Drag and drop or click to upload video files
2. **Wait for Processing**: AI will transcribe the audio automatically
3. **Search**: Use natural language to search through your video
4. **Navigate**: Click search results to jump to exact timestamps
5. **Browse**: View full transcript with highlighted search terms

**Built with ❤️ for efficient video content discovery**
