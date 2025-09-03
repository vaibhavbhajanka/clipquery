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

### System Overview

ClipQuery employs a microservices-inspired architecture with clear separation between frontend presentation, backend business logic, and external service integrations. The system is designed for horizontal scalability and can handle both local deployments and cloud-scale operations.

**Frontend**: Next.js 15 with React 19, TypeScript, and Tailwind CSS
**Backend**: FastAPI with Python 3.11, PostgreSQL, and vector embeddings
**Infrastructure**: AWS ECS, CloudFront, S3, and Container Registry
**AI Services**: OpenAI Whisper for transcription, OpenAI embeddings for semantic search

### Key Components

#### Video Processing Pipeline
The video processing pipeline handles both uploaded files and YouTube URLs through a multi-stage approach:

1. **Video Ingestion**: Supports major formats (MP4, MOV, AVI, MKV, WebM) up to 500MB
2. **Audio Extraction**: Uses FFmpeg for high-quality audio extraction
3. **Transcription**: OpenAI Whisper provides industry-leading speech-to-text accuracy
4. **Segmentation**: Intelligent chunking preserves semantic meaning while optimizing for search
5. **Embedding Generation**: OpenAI's text-embedding-3-small model creates vector representations

#### Semantic Search Engine
The search implementation provides both semantic and lexical search capabilities:

- **Vector Search**: Uses Pinecone for similarity-based semantic search
- **Fallback Search**: PostgreSQL full-text search when vector database is unavailable
- **Hybrid Results**: Combines semantic understanding with exact phrase matching

#### Scalable Storage Architecture
ClipQuery implements a sophisticated storage strategy that balances performance, cost, and scalability:

- **Presigned S3 URLs**: Direct browser-to-S3 uploads bypass server payload limits
- **CloudFront Distribution**: Global CDN for optimized video delivery
- **Local Fallback**: Development-friendly local storage option
- **Database Optimization**: Efficient video metadata and segment storage

## Engineering Decisions and Trade-offs

### Storage Strategy: Presigned URLs vs Server Upload

**Decision**: Implement presigned S3 URLs for direct browser uploads
**Trade-off**: Added complexity in exchange for unlimited file size support

Traditional server-mediated uploads hit Vercel's 4.5MB serverless function limit, making video uploads impractical. Presigned URLs enable direct browser-to-S3 transfers, supporting files up to 500MB while maintaining security through time-limited, scoped permissions. This approach requires careful CORS configuration and error handling but eliminates server bandwidth constraints entirely.

### Transcription: Cloud API vs Self-hosted

**Decision**: Use OpenAI Whisper API over self-hosted solutions
**Trade-off**: API costs vs infrastructure complexity and accuracy

Self-hosting Whisper would require GPU infrastructure, model management, and significant operational overhead. OpenAI's hosted Whisper provides superior accuracy with multilingual support, automatic punctuation, and speaker identification. The cost scales linearly with usage, making it economical for MVP development while maintaining production-ready quality.

### Search Implementation: Vector + Lexical Hybrid

**Decision**: Implement both semantic (Pinecone) and lexical (PostgreSQL) search with graceful fallback
**Trade-off**: System complexity vs search quality and reliability

Pure keyword search misses semantic relationships ("AI" vs "artificial intelligence"), while pure vector search can miss exact phrases. The hybrid approach provides semantic understanding through embeddings while maintaining exact phrase matching capabilities. Graceful fallback to PostgreSQL ensures system reliability when external vector services are unavailable.

### YouTube Integration: API + Proxy Architecture

**Decision**: Implement YouTube transcript fetching with proxy support for IP restrictions
**Trade-off**: Additional infrastructure vs comprehensive content coverage

YouTube blocks most cloud provider IPs from transcript access, requiring proxy infrastructure for cloud deployments. This adds operational complexity but enables seamless integration with YouTube content, significantly expanding the platform's utility. The proxy configuration is optional, allowing local development while supporting production scalability.

## Deployment Architecture

### Cloud Infrastructure 
- **AWS ECS Fargate**: Serverless container orchestration
- **Application Load Balancer**: Traffic distribution and SSL termination
- **CloudFront**: Global CDN with edge caching
- **S3**: Object storage for video files and static assets
- **RDS/Supabase**: Managed PostgreSQL with automatic backups
- **ECR**: Private container registry

