# ClipQuery YouTube Transcript Worker

A Cloudflare Worker that fetches YouTube transcripts using the Innertube API, bypassing AWS IP blocking.

## Setup

1. Install Wrangler CLI:
```bash
npm install -g wrangler
```

2. Install dependencies:
```bash
npm install
```

3. Login to Cloudflare:
```bash
wrangler login
```

4. Update the `name` field in `wrangler.toml` to your preferred worker name

5. Deploy the worker:
```bash
npm run deploy
```

6. After deployment, note the worker URL (e.g., `https://your-worker.your-subdomain.workers.dev`)

7. Configure your backend to use the Worker by setting the `CLOUDFLARE_WORKER_URL` environment variable:
```bash
export CLOUDFLARE_WORKER_URL=https://your-worker.your-subdomain.workers.dev
```

## Usage

The worker accepts GET requests with a `v` query parameter containing the YouTube video ID:

```
GET https://your-worker.your-subdomain.workers.dev/?v=VIDEO_ID
```

Example:
```
GET https://clipquery-youtube-transcripts.your-subdomain.workers.dev/?v=dQw4w9WgXcQ
```

## Response Format

Success response:
```json
{
  "success": true,
  "videoId": "dQw4w9WgXcQ",
  "segmentCount": 42,
  "segments": [
    {
      "text": "Never gonna give you up",
      "start": 0.0,
      "end": 3.5
    }
  ],
  "processedAt": "2024-01-01T12:00:00.000Z",
  "source": "cloudflare-worker"
}
```

Error response:
```json
{
  "error": "No caption tracks found in video",
  "success": false,
  "source": "cloudflare-worker"
}
```

## Features

- Bypasses YouTube IP blocking by running on Cloudflare's edge network
- Smart segmentation that groups transcript segments into natural speech boundaries
- CORS enabled for cross-origin requests
- 1-hour caching for improved performance
- Android client impersonation for better API access