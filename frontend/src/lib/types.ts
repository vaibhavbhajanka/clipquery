export interface Video {
  id: string
  filename: string
  originalName: string
  filePath: string
  fileSize: number
  duration?: number
  status: 'uploaded' | 'processing' | 'ready' | 'failed'
  createdAt: string
  updatedAt: string
  segments?: VideoSegment[]
}

export interface VideoSegment {
  id: string
  videoId: string
  text: string
  startTime: number
  endTime: number
  createdAt: string
}

export interface SearchResult {
  text: string
  startTime: number
  endTime: number
  confidence: number
}

export interface ProcessingResult {
  success: boolean
  segmentCount?: number
  windowCount?: number
  error?: string
}