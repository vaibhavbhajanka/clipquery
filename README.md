# ClipQuery

ClipQuery is a full-stack web application that enables users to search and navigate through video content using natural language queries. Built with modern web technologies, it transforms spoken words into searchable text with precise timestamp matching.

The application accepts video uploads up to 3 minutes in length, providing a natural language search interface where users can ask questions like "When does the presenter mention new product features?" and receive precise timestamp results. Additionally, it includes an interactive chatbot feature with real-time WebSocket messaging for engaging with video content.

## Live Demo

**[ Watch Demo Video →](https://youtu.be/_ZMthpKYgIM)** | **[ Try Live Platform →](https://clipquery-sandy.vercel.app/)**

*See ClipQuery in action with video upload, search, and chat capabilities*

## Platform Demo

### Uploaded Video Features

<div align="center">

| **1. Video Upload Area** | **2. Video Player Interface** |
|:---:|:---:|
| ![Upload Area](images/1-upload-area.png) | ![Video Player](images/2-video-player.png) |
| *Drag & drop interface supporting MP4, MOV, AVI, MKV, and WebM formats up to 500MB* | *Interactive video player with timestamp controls and search result navigation* |

| **3. Transcript View** | **4. Search Results & Navigation** |
|:---:|:---:|
| ![Transcript](images/3-transcript.png) | ![Search Results](images/4-search-results.png) |
| *Full transcript display with segment timestamps and text content* | *Natural language search results with confidence scores and precise timestamps* |

| **5. Chat with Uploaded Video** |
|:---:|
| ![Chat Interface](images/5-chat-uploaded.png) |
| *Real-time WebSocket-powered chat interface for interactive video conversations* |

</div>

### YouTube Integration Features

<div align="center">

| **6. YouTube URL Upload** | **7. YouTube Transcript Display** |
|:---:|:---:|
| ![YouTube Upload](images/6-youtube-upload.png) | ![YouTube Transcript](images/7-youtube-transcript.png) |
| *YouTube video processing with automatic transcript extraction* | *YouTube video transcript with timestamp synchronization* |

| **8. YouTube Video Search** | **9. Chat with YouTube Video** |
|:---:|:---:|
| ![YouTube Search](images/8-youtube-chat.png) | ![YouTube Chat](images/9-youtube-search.png) |
| *Semantic search across YouTube video content with result highlighting* | *Interactive chat interface for YouTube videos with context-aware responses* |

</div>

## Technical Architecture

### System Architecture

```mermaid
graph TB
    User[User Browser] --> Frontend[Next.js 15 Frontend<br/>Vercel]
    User --> CDN[CloudFront CDN<br/>Video Delivery]

    Frontend --> Backend[FastAPI Backend<br/>AWS ECS Fargate]

    Backend --> DB[(PostgreSQL<br/>Supabase)]
    Backend --> S3[S3 Bucket<br/>Video Storage]
    Backend --> Pinecone[Pinecone<br/>Vector Database]
    Backend --> OpenAI[OpenAI API<br/>Whisper + Embeddings + GPT-4]

    S3 --> CDN

    style Frontend fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#000
    style Backend fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#000
    style DB fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#000
    style S3 fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#000
    style Pinecone fill:#fce4ec,stroke:#e91e63,stroke-width:2px,color:#000
    style OpenAI fill:#f1f8e9,stroke:#689f38,stroke-width:2px,color:#000
    style CDN fill:#fff8e1,stroke:#ff9800,stroke-width:2px,color:#000
```


ClipQuery employs an architecture with clear separation between frontend presentation, backend business logic, and external service integrations. The system is designed for horizontal scalability and can handle cloud-scale operations.

**Frontend**: Next.js 15 with React 19, TypeScript, and Tailwind CSS<br>
**Backend**: FastAPI with Python 3.11, PostgreSQL, and vector embeddings<br>
**Infrastructure**: AWS ECS, CloudFront, S3, and Container Registry<br>
**AI Services**: OpenAI Whisper for transcription, OpenAI embeddings for semantic search<br>


#### Video Processing Pipeline

```mermaid
flowchart LR
    Upload[Video Upload<br/>MP4/MOV/AVI/MKV/WebM<br/>≤500MB] --> Extract[Audio Extraction<br/>FFmpeg<br/>75MB → 1.5MB]
    YouTube[YouTube URL] --> YTTranscript[YouTube Transcript<br/>API/Proxy Fetch]

    Extract --> Transcribe[Whisper Transcription<br/>OpenAI API<br/>Verbose JSON]
    YTTranscript --> Segment

    Transcribe --> Segment[Intelligent Segmentation<br/>8-second chunks<br/>Sentence boundaries]
    Segment --> Embed[Generate Embeddings<br/>text-embedding-3-small<br/>1536 dimensions]
    Embed --> StoreText[(Store Text & Metadata<br/>PostgreSQL<br/>Segments + Timestamps)]
    Embed --> StoreVectors[(Store Embeddings<br/>Pinecone<br/>1536-dim Vectors)]
    StoreText --> Search[Semantic Search<br/>Ready for Queries]
    StoreVectors --> Search

    style Upload fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#000
    style YouTube fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#000
    style Extract fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px,color:#000
    style Transcribe fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#000
    style Segment fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#000
    style Embed fill:#fce4ec,stroke:#e91e63,stroke-width:2px,color:#000
    style StoreText fill:#e8f5e8,stroke:#388e3c,stroke-width:2px,color:#000
    style StoreVectors fill:#fce4ec,stroke:#e91e63,stroke-width:2px,color:#000
    style Search fill:#e0f2f1,stroke:#689f38,stroke-width:2px,color:#000
```

The video processing pipeline handles both uploaded files and YouTube URLs through a multi-stage approach:

1. **Video Ingestion**: Supports major formats (MP4, MOV, AVI, MKV, WebM) up to 500MB
2. **Audio Extraction**: Uses FFmpeg for high-quality audio extraction
3. **Transcription**: OpenAI Whisper provides industry-leading speech-to-text accuracy
4. **Segmentation**: Intelligent chunking preserves semantic meaning while optimizing for search
5. **Embedding Generation**: OpenAI's text-embedding-3-small model creates vector representations



## Architectural Decisions

**Video Upload**
- **Presigned S3 URLs**: Direct browser-to-S3 uploads bypass Vercel's 4.5MB serverless limit, supporting 500MB video files. Requires CORS configuration but eliminates server bandwidth constraints and enables scalable parallel uploads.
- **FFmpeg Audio Extraction**: Converts 75MB videos to 1.5MB MP3 audio since Whisper API has a 25MB file limit. 2-3 second processing overhead reduces API costs by 98% while ensuring all videos fit within constraints.

**Processing** 
- **OpenAI Whisper API**: Cloud transcription service chosen over self-hosting to avoid GPU infrastructure, model management, and scaling complexities. Higher per-request costs but provides superior accuracy with automatic language detection and multilingual support.

**Search & Storage**
- **Vector-First Search with Relational Persistence**: Pinecone handles semantic search and returns timestamps from metadata, while PostgreSQL manages video lifecycle, provides complete transcript access, and serves as fallback when vector search is unavailable.

**User Experience**
- **WebSocket Chat Streaming**: Real-time bidirectional communication delivers AI responses chunk-by-chunk as they generate. Connection management overhead justified by 60-70% improvement in perceived performance compared to waiting for complete responses.
- **YouTube Proxy Integration**: Proxy infrastructure handles cloud provider IP blocks for YouTube transcript access. Adds deployment complexity but enables seamless integration with YouTube's vast content library.

**Infrastructure**
- **ECS Fargate Containers**: Serverless container orchestration eliminates infrastructure management compared to self-managed Kubernetes. AWS vendor lock-in accepted for operational simplicity, auto-scaling, and zero-downtime deployments.
- **Retry with Exponential Backoff**: Automatic retry for transient failures with 3 attempts and exponential delays (1s→2s→4s). Prevents cascade failures during service disruptions while avoiding aggressive retry storms.

## User Flow

### User Interaction Flow

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant B as Backend
    participant S3 as AWS S3
    participant W as Whisper API
    participant P as Pinecone
    participant G as GPT-4

    Note over U,G: Video Upload & Processing Flow

    U->>F: Uploads video file (≤500MB)
    F->>B: Requests presigned S3 URL
    B->>S3: Generates presigned upload URL
    S3->>B: Returns upload URL & fields
    B->>F: Sends presigned URL
    F->>S3: Uploads video directly to S3
    S3->>F: Confirms upload success
    F->>B: Notifies upload completion

    B->>B: Extracts audio with FFmpeg (75MB→1.5MB)
    B->>W: Sends audio for transcription
    W->>B: Returns timestamped segments
    B->>B: Intelligent segmentation (8-second chunks)
    B->>B: Generates embeddings (text-embedding-3-small)
    B->>P: Stores vectors with metadata
    P->>B: Confirms storage
    B->>F: Status: Ready for search

    Note over U,G: Search & Chat Interaction

    U->>F: Enters search query "When does speaker mention AI?"
    F->>B: Sends search request
    B->>B: Generates query embedding
    B->>P: Vector similarity search
    P->>B: Returns matching segments with scores
    B->>F: Sends ranked results with timestamps
    F->>U: Displays search results

    U->>F: Clicks timestamp to jump to moment
    F->>F: Seeks video to timestamp

    U->>F: Opens chat panel
    F->>B: Establishes WebSocket connection
    B->>F: Confirms WebSocket ready

    U->>F: Sends chat message "Summarize main points"
    F->>B: Forwards message via WebSocket
    B->>P: Retrieves relevant video context
    P->>B: Returns context segments
    B->>G: Sends context + user query
    G->>B: Streams response chunks
    B->>F: Forwards chunks via WebSocket
    F->>U: Displays streaming response in real-time
```
## Deployment Architecture

### Cloud Infrastructure 
- **AWS ECS Fargate**: Serverless container orchestration
- **Application Load Balancer**: Traffic distribution and SSL termination
- **CloudFront**: Global CDN with edge caching
- **S3**: Object storage for video files and static assets
- **Supabase**: Managed PostgreSQL with automatic backups
- **ECR**: Private container registry
