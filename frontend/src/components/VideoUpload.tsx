'use client'

import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Video } from '@/lib/types'

// API base URL - configurable for different environments
const API_BASE_URL = process.env.API_URL || 'http://localhost:8000'

interface VideoUploadProps {
  onVideoUploaded: (video: Video) => void
}

export default function VideoUpload({ onVideoUploaded }: VideoUploadProps) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string>('')
  const [uploadMode, setUploadMode] = useState<'file' | 'youtube'>('file')
  const [youtubeUrl, setYoutubeUrl] = useState('')

  const MAX_SIZE = 500 * 1024 * 1024 // 500MB
  const MAX_DURATION = 3 * 60 // 3 minutes

  const isValidYouTubeUrl = (url: string): boolean => {
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)/
    return youtubeRegex.test(url)
  }

  const handleYouTubeSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!youtubeUrl.trim()) {
      setError('Please enter a YouTube URL')
      return
    }

    if (!isValidYouTubeUrl(youtubeUrl)) {
      setError('Please enter a valid YouTube URL')
      return
    }

    setError(null)
    setUploading(true)
    setStatus('Fetching YouTube video information...')

    try {
      const response = await fetch(`${API_BASE_URL}/upload-youtube`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: youtubeUrl })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Failed to process YouTube video')
      }

      const video = await response.json()
      onVideoUploaded(video)
      setStatus('YouTube video added successfully!')
      setYoutubeUrl('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to process YouTube video')
    } finally {
      setUploading(false)
      setTimeout(() => setStatus(''), 3000)
    }
  }

  
  const validateVideoDuration = (file: File): Promise<number> => {
    return new Promise((resolve, reject) => {
      const video = document.createElement('video')
      video.preload = 'metadata'
      
      video.onloadedmetadata = () => {
        window.URL.revokeObjectURL(video.src)
        resolve(video.duration)
      }
      
      video.onerror = () => {
        window.URL.revokeObjectURL(video.src)
        reject(new Error('Failed to load video metadata'))
      }
      
      video.src = window.URL.createObjectURL(file)
    })
  }

  const onDrop = useCallback(async (acceptedFiles: File[], rejectedFiles: any[]) => {
    if (rejectedFiles.length > 0) {
      setError('Please select a valid video file')
      return
    }

    const file = acceptedFiles[0]
    if (!file) return

    if (file.size > MAX_SIZE) {
      setError('Video must be under 500MB')
      return
    }

    setError(null)
    setUploading(true)
    setStatus('Validating video duration...')

    try {
      // Check video duration
      const duration = await validateVideoDuration(file)
      
      if (duration > MAX_DURATION) {
        const minutes = Math.floor(duration / 60)
        const seconds = Math.floor(duration % 60)
        setError(`Video is ${minutes}:${seconds.toString().padStart(2, '0')} long. Please upload videos under 3 minutes.`)
        setUploading(false)
        setStatus('')
        return
      }

      console.log(`Video duration: ${duration} seconds (${Math.floor(duration / 60)}:${Math.floor(duration % 60).toString().padStart(2, '0')})`)
    } catch (durationError) {
      console.warn('Could not validate video duration:', durationError)
      // Continue with upload if duration check fails (server will validate as backup)
    }
    
    const sizeMB = (file.size / (1024 * 1024)).toFixed(1)
    if (file.size > 25 * 1024 * 1024) {
      setStatus(`Large file (${sizeMB}MB) - will extract audio for processing...`)
    } else {
      setStatus(`Processing ${sizeMB}MB video directly...`)
    }

    try {
      const formData = new FormData()
      formData.append('video', file)

      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.error || 'Upload failed')
      }

      const video = await response.json()
      onVideoUploaded(video)
      setStatus('Upload completed successfully!')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
      setTimeout(() => setStatus(''), 3000)
    }
  }, [onVideoUploaded])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'video/*': ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    },
    maxSize: MAX_SIZE,
    multiple: false
  })

  return (
    <div className="w-full max-w-4xl mx-auto">
      {/* Upload Mode Tabs */}
      <div className="flex mb-6 bg-gray-100 rounded-lg p-1">
        <button
          onClick={() => setUploadMode('file')}
          className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            uploadMode === 'file'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Upload File
        </button>
        <button
          onClick={() => setUploadMode('youtube')}
          className={`flex-1 py-2 px-4 rounded-md text-sm font-medium transition-colors ${
            uploadMode === 'youtube'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          YouTube URL
        </button>
      </div>

      {uploadMode === 'youtube' ? (
        /* YouTube URL Input */
        <div className="border-2 border-gray-300 rounded-xl p-6 sm:p-8 lg:p-12">
          <div className="space-y-6">
            <div className="mx-auto w-16 h-16 sm:w-20 sm:h-20 lg:w-24 lg:h-24 rounded-full bg-gradient-to-br from-red-100 to-red-200 flex items-center justify-center">
              <svg className="w-8 h-8 sm:w-10 sm:h-10 lg:w-12 lg:h-12 text-red-600" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
              </svg>
            </div>
            <div>
              <p className="text-lg sm:text-xl lg:text-2xl font-semibold text-gray-900">Add YouTube Video</p>
              <p className="text-sm sm:text-base text-gray-600 mt-2">
                Paste a YouTube URL to analyze its content
              </p>
            </div>
            
            <form onSubmit={handleYouTubeSubmit} className="space-y-4">
              <div>
                <input
                  type="url"
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="w-full px-3 sm:px-4 py-2 sm:py-3 text-sm sm:text-base text-gray-900 placeholder-gray-400 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
                  disabled={uploading}
                />
              </div>
              <button
                type="submit"
                disabled={uploading || !youtubeUrl.trim()}
                className="w-full py-3 px-4 bg-red-600 hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
              >
                {uploading ? 'Processing...' : 'Add YouTube Video'}
              </button>
            </form>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4 text-xs sm:text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" clipRule="evenodd" />
                </svg>
                Under 3 minutes
              </span>
              <span className="hidden sm:inline text-gray-400">•</span>
              <span className="flex items-center gap-1">
                <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                </svg>
                Must have captions/subtitles
              </span>
            </div>
          </div>
        </div>
      ) : (
        /* File Upload */
        <div
          {...getRootProps()}
          className={`
            border-2 border-dashed rounded-xl p-6 sm:p-8 lg:p-12 text-center cursor-pointer transition-all duration-200
            ${isDragActive ? 'border-blue-500 bg-blue-50 scale-105' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'}
            ${uploading ? 'pointer-events-none opacity-50' : ''}
          `}
        >
          <input {...getInputProps()} />
          
          {uploading ? (
            <div className="space-y-4">
              <div className="animate-spin rounded-full h-12 w-12 sm:h-16 sm:w-16 border-b-2 border-blue-600 mx-auto"></div>
              <p className="text-sm sm:text-base font-medium text-gray-700">
                Uploading your video...
              </p>
              <p className="text-xs sm:text-sm text-gray-500">This may take a moment</p>
            </div>
          ) : (
            <div className="space-y-4 sm:space-y-6">
              <div className="mx-auto w-16 h-16 sm:w-20 sm:h-20 lg:w-24 lg:h-24 rounded-full bg-gradient-to-br from-blue-100 to-purple-100 flex items-center justify-center">
                <svg className="w-8 h-8 sm:w-10 sm:h-10 lg:w-12 lg:h-12 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <p className="text-lg sm:text-xl lg:text-2xl font-semibold text-gray-900">
                  {isDragActive ? 'Drop your video here' : 'Upload your video'}
                </p>
                <p className="text-sm sm:text-base text-gray-600 mt-2">
                  Drag & drop or click to browse
                </p>
              </div>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4 text-xs sm:text-sm text-gray-500">
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  MP4, MOV, AVI, MKV
                </span>
                <span className="hidden sm:inline text-gray-400">•</span>
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" clipRule="evenodd" />
                  </svg>
                  Under 3 minutes
                </span>
                <span className="hidden sm:inline text-gray-400">•</span>
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                  </svg>
                  Up to 500MB
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {status && (
        <div className="mt-4 p-3 sm:p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <p className="text-sm sm:text-base text-blue-700 font-medium">{status}</p>
        </div>
      )}

      {error && (
        <div className="mt-4 p-3 sm:p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2">
          <svg className="w-4 h-4 text-red-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
          <p className="text-sm sm:text-base text-red-700 font-medium">{error}</p>
        </div>
      )}
    </div>
  )
}