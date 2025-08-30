'use client'

import { useState } from 'react'
import VideoUpload from '@/components/VideoUpload'
import VideoPlayer from '@/components/SimpleVideoPlayer'
import SearchBar from '@/components/SearchBar'
import SearchResults from '@/components/SearchResults'
import TranscriptViewer from '@/components/TranscriptViewer'
import TabSwitcher from '@/components/TabSwitcher'
import ChatPanel from '@/components/ChatPanel'
import { Video, SearchResult, VideoSegment } from '@/lib/types'

// API base URL - configurable for different environments
const API_BASE_URL = process.env.API_URL || 'http://localhost:8000'

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

export default function Home() {
  const [currentVideo, setCurrentVideo] = useState<Video | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [isSearching, setIsSearching] = useState(false)
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [transcript, setTranscript] = useState<VideoSegment[]>([])
  const [currentSearchQuery, setCurrentSearchQuery] = useState<string>('')
  const [seekTo, setSeekTo] = useState<number | undefined>()
  const [processingError, setProcessingError] = useState<string | null>(null)
  const [currentVideoTime, setCurrentVideoTime] = useState<number>(0)
  const [autoScrollEnabled, setAutoScrollEnabled] = useState<boolean>(false)
  const [activeResultIndex, setActiveResultIndex] = useState<number>(-1)
  const [videoUrl, setVideoUrl] = useState<string>('')
  const [activeTab, setActiveTab] = useState<'search' | 'chat'>('search')

  const fetchTranscript = async (videoId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/videos/${videoId}/transcript`)
      if (response.ok) {
        const transcriptData = await response.json()
        setTranscript(transcriptData)
      } else {
        console.error('Failed to fetch transcript')
        setTranscript([])
      }
    } catch (error) {
      console.error('Error fetching transcript:', error)
      setTranscript([])
    }
  }

  const [videoData, setVideoData] = useState<{url: string, type: string, youtubeId?: string} | null>(null)

  const resolveVideoUrl = async (video: Video) => {
    try {
      const response = await fetch(`${API_BASE_URL}/video-url/${video.filename}`)
      const data = await response.json()
      
      if (response.ok && data.url) {
        setVideoData({
          url: data.url,
          type: data.type || 'local',
          youtubeId: data.youtube_id
        })
        setVideoUrl(data.url)
      } else {
        throw new Error('Failed to get video URL')
      }
    } catch (error) {
      console.error('Error resolving video URL:', error)
      // Fallback to localhost URL
      const fallbackUrl = `${API_BASE_URL}/video/${video.filename}`
      setVideoData({
        url: fallbackUrl,
        type: 'local'
      })
      setVideoUrl(fallbackUrl)
    }
  }

  const handleVideoUploaded = async (video: Video) => {
    setCurrentVideo(video)
    setProcessingError(null)
    setIsProcessing(true)
    
    // Resolve the video URL for playback
    await resolveVideoUrl(video)

    try {
      const response = await fetch(`${API_BASE_URL}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          video_id: video.id
        })
      })

      const result = await response.json()

      if (!response.ok) {
        throw new Error(result.error || 'Processing failed')
      }

      setCurrentVideo(prev => prev ? { ...prev, status: 'ready' } : null)
      
      // Fetch the transcript once processing is complete
      if (video.id) {
        await fetchTranscript(video.id)
      }
    } catch (error) {
      setProcessingError(error instanceof Error ? error.message : 'Processing failed')
      setCurrentVideo(prev => prev ? { ...prev, status: 'failed' } : null)
    } finally {
      setIsProcessing(false)
    }
  }

  const handleSearch = async (query: string) => {
    if (!currentVideo) return

    setCurrentSearchQuery(query)
    setIsSearching(true)
    try {
      const response = await fetch(`${API_BASE_URL}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          video_id: currentVideo.id 
        })
      })

      const results = await response.json()
      setSearchResults(results || [])
      
      // Auto-seek to the best result (first result with highest confidence)
      if (results && results.length > 0) {
        const bestResult = results[0]
        setActiveResultIndex(0)
        handleSeek(bestResult.startTime || bestResult.start_time)
      } else {
        setActiveResultIndex(-1)
      }
    } catch (error) {
      console.error('Search failed:', error)
      setSearchResults([])
      setActiveResultIndex(-1)
    } finally {
      setIsSearching(false)
    }
  }

  const handleSeek = (timestamp: number, resultIndex?: number) => {
    setSeekTo(timestamp)
    if (resultIndex !== undefined) {
      setActiveResultIndex(resultIndex)
    }
    // Reset seekTo after a short delay to allow multiple seeks to the same timestamp
    setTimeout(() => setSeekTo(undefined), 100)
  }


  const canSearch = currentVideo && currentVideo.status === 'ready' && !isProcessing

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 py-4 sm:py-6">
      <div className="max-w-4xl md:max-w-6xl lg:max-w-7xl xl:max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-4 sm:mb-6">
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-2">
            ClipQuery
          </h1>
          <p className="text-base sm:text-lg text-gray-700 max-w-2xl mx-auto">
            Natural language video search powered by AI
          </p>
        </div>

        {!currentVideo ? (
          // Centered upload layout when no video is present
          <div className="flex items-center justify-center min-h-[50vh] sm:min-h-[60vh]">
            <div className="w-full max-w-3xl lg:max-w-4xl xl:max-w-5xl">
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6 sm:p-8 lg:p-12">
                <h2 className="text-xl sm:text-2xl lg:text-3xl font-bold text-gray-900 mb-6 text-center">Upload Video</h2>
                <VideoUpload onVideoUploaded={handleVideoUploaded} />
              </div>
            </div>
          </div>
        ) : (
          // Regular layout when video is present
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-12 gap-4 sm:gap-6">
            {/* Left Column - Upload & Search */}
            <div className="md:col-span-1 lg:col-span-4 xl:col-span-4 space-y-4">
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-4 sm:p-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between mb-4 gap-3">
                  <h2 className="text-lg sm:text-xl font-bold text-gray-900">Video Details</h2>
                  <button
                    onClick={() => {
                      setCurrentVideo(null)
                      setSearchResults([])
                      setTranscript([])
                      setCurrentSearchQuery('')
                      setProcessingError(null)
                      setCurrentVideoTime(0)
                      setAutoScrollEnabled(false)
                      setActiveResultIndex(-1)
                      setVideoUrl('')
                      setActiveTab('search')
                    }}
                    className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                  >
                    Change video
                  </button>
                </div>
                
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">{currentVideo.originalName}</p>
                      <p className="text-xs text-gray-500">{(Number(currentVideo.fileSize) / (1024 * 1024)).toFixed(1)} MB</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-700">Status:</span>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${
                      currentVideo.status === 'ready' ? 'bg-green-100 text-green-800' :
                      currentVideo.status === 'processing' || isProcessing ? 'bg-yellow-100 text-yellow-800' :
                      currentVideo.status === 'failed' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`}>
                      {isProcessing ? 'Processing...' : currentVideo.status === 'ready' ? 'Ready' : currentVideo.status}
                    </span>
                  </div>
                  
                  {processingError && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                      <p className="text-sm text-red-700">{processingError}</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-4 sm:p-6">
                <h2 className="text-lg sm:text-xl font-bold text-gray-900 mb-4">
                  {activeTab === 'search' ? 'Search Video' : 'Chat with Video'}
                </h2>
                
                <TabSwitcher 
                  activeTab={activeTab}
                  onTabChange={setActiveTab}
                  disabled={!canSearch}
                />
                
                <div className={activeTab === 'search' ? 'block' : 'hidden'}>
                  <SearchBar 
                    onSearch={handleSearch}
                    isSearching={isSearching}
                    disabled={!canSearch}
                  />
                  
                  {!canSearch && currentVideo.status !== 'ready' && (
                    <p className="text-sm text-gray-500 mt-2 text-center">
                      {isProcessing ? 'Processing video...' : 'Video processing required for search'}
                    </p>
                  )}
                </div>
                
                <div className={`min-h-[400px] max-h-[500px] sm:min-h-[450px] sm:max-h-[550px] flex flex-col ${activeTab === 'chat' ? 'block' : 'hidden'}`}>
                  <ChatPanel 
                    videoId={currentVideo.id}
                    disabled={!canSearch}
                    onSeek={handleSeek}
                  />
                </div>
              </div>

              {activeTab === 'search' && searchResults.length > 0 && (
                <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-4 sm:p-6">
                  <h3 className="text-lg font-bold text-gray-900 mb-4">
                    Search Results
                    {activeResultIndex >= 0 && (
                      <span className="block sm:inline text-sm font-normal text-blue-600 sm:ml-2">
                        (jumped to best match)
                      </span>
                    )}
                  </h3>
                  <SearchResults 
                    results={searchResults}
                    onSeek={handleSeek}
                    activeResultIndex={activeResultIndex}
                  />
                </div>
              )}
            </div>

            {/* Middle and Right Columns - Video Player and Transcript */}
            <div className="md:col-span-2 lg:col-span-8 xl:col-span-8 space-y-4">
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-4 sm:p-6">
                <h2 className="text-lg sm:text-xl font-bold text-gray-900 mb-4">Video Player</h2>
                <div className="aspect-video bg-gray-100 rounded-xl overflow-hidden">
                  {videoData ? (
                    <VideoPlayer 
                      url={videoData.url}
                      seekTo={seekTo}
                      onProgress={setCurrentVideoTime}
                      videoType={videoData.type}
                      youtubeId={videoData.youtubeId}
                    />
                  ) : (
                    <div className="flex items-center justify-center w-full h-full">
                      <div className="text-center">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
                        <div className="text-gray-600 font-medium">Loading video...</div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              
              {transcript.length > 0 && (
                <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-4 sm:p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 gap-3">
                    <h3 className="text-lg font-bold text-gray-900">
                      Full Transcript
                      {currentSearchQuery && (
                        <span className="block sm:inline text-sm font-normal text-gray-600 sm:ml-2">
                          (highlighting: "{currentSearchQuery}")
                        </span>
                      )}
                    </h3>
                    
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => setAutoScrollEnabled(!autoScrollEnabled)}
                        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                          autoScrollEnabled 
                            ? 'bg-blue-100 text-blue-700 hover:bg-blue-200' 
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        <span className="hidden sm:inline">Auto-scroll</span>
                        <span className="sm:hidden">Auto</span>
                        {autoScrollEnabled ? ' ON' : ' OFF'}
                      </button>
                      
                      {autoScrollEnabled && (
                        <div className="hidden lg:flex items-center gap-2 text-xs text-gray-500">
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                          </svg>
                          Smart follow
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div className="max-h-80 sm:max-h-96 lg:max-h-[500px] overflow-y-auto">
                    <TranscriptViewer 
                      segments={transcript}
                      searchQuery={currentSearchQuery}
                      onSeek={handleSeek}
                      currentTime={currentVideoTime}
                      autoScroll={autoScrollEnabled}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}