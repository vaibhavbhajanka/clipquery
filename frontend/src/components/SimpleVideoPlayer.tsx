'use client'

import { useRef, useEffect, useCallback, useState } from 'react'

declare global {
  interface Window {
    YT: any;
    onYouTubeIframeAPIReady: () => void;
  }
}

interface SimpleVideoPlayerProps {
  url: string
  seekTo?: number
  onProgress?: (currentTime: number) => void
  videoType?: string
  youtubeId?: string
}

export default function SimpleVideoPlayer({ url, seekTo, onProgress, videoType, youtubeId }: SimpleVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const youtubeRef = useRef<HTMLDivElement>(null)
  const youtubePlayerRef = useRef<any>(null)
  const lastUpdateTime = useRef<number>(0)
  const [youtubeReady, setYoutubeReady] = useState(false)

  const isYouTube = videoType === 'youtube' || url.includes('youtube.com/embed/')

  // Load YouTube IFrame API
  useEffect(() => {
    if (isYouTube && !window.YT) {
      const script = document.createElement('script')
      script.src = 'https://www.youtube.com/iframe_api'
      document.body.appendChild(script)

      window.onYouTubeIframeAPIReady = () => {
        setYoutubeReady(true)
      }
    } else if (isYouTube && window.YT) {
      setYoutubeReady(true)
    }
  }, [isYouTube])

  // Initialize YouTube player
  useEffect(() => {
    if (isYouTube && youtubeReady && youtubeRef.current && youtubeId) {
      youtubePlayerRef.current = new window.YT.Player(youtubeRef.current, {
        videoId: youtubeId,
        width: '100%',
        height: 'auto',
        playerVars: {
          enablejsapi: 1,
          origin: window.location.origin,
        },
        events: {
          onReady: () => {
            console.log('YouTube player ready')
          },
          onStateChange: (event: any) => {
            // Handle YouTube player state changes
            if (event.data === window.YT.PlayerState.PLAYING) {
              // Start progress updates when playing
              startYouTubeProgressUpdates()
            }
          }
        }
      })
    }

    return () => {
      if (youtubePlayerRef.current) {
        youtubePlayerRef.current.destroy()
      }
    }
  }, [isYouTube, youtubeReady, youtubeId])

  // Handle YouTube seeking
  useEffect(() => {
    if (seekTo !== undefined) {
      if (isYouTube && youtubePlayerRef.current) {
        youtubePlayerRef.current.seekTo(seekTo, true)
      } else if (videoRef.current) {
        videoRef.current.currentTime = seekTo
      }
    }
  }, [seekTo, isYouTube])

  // YouTube progress updates
  const startYouTubeProgressUpdates = useCallback(() => {
    if (!youtubePlayerRef.current || !onProgress) return

    const updateProgress = () => {
      if (youtubePlayerRef.current && youtubePlayerRef.current.getCurrentTime) {
        const currentTime = youtubePlayerRef.current.getCurrentTime()
        const now = Date.now()
        
        // Only update every 250ms
        if (now - lastUpdateTime.current > 250) {
          onProgress(currentTime)
          lastUpdateTime.current = now
        }
      }
    }

    const interval = setInterval(() => {
      if (youtubePlayerRef.current) {
        const state = youtubePlayerRef.current.getPlayerState()
        if (state === window.YT.PlayerState.PLAYING) {
          updateProgress()
        }
      }
    }, 250)

    return () => clearInterval(interval)
  }, [onProgress])

  // Regular video progress updates
  const handleTimeUpdate = useCallback(() => {
    if (videoRef.current && onProgress) {
      const currentTime = videoRef.current.currentTime
      const now = Date.now()
      
      // Only update every 250ms or when seeking
      if (now - lastUpdateTime.current > 250) {
        onProgress(currentTime)
        lastUpdateTime.current = now
      }
    }
  }, [onProgress])

  if (isYouTube) {
    return (
      <div className="relative w-full h-full">
        <div 
          ref={youtubeRef}
          className="w-full h-full bg-black"
        />
        {!youtubeReady && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
            <div className="text-gray-600">Loading YouTube player...</div>
          </div>
        )}
      </div>
    )
  }

  return (
    <video
      ref={videoRef}
      src={url}
      controls
      className="w-full h-full object-contain bg-black"
      onTimeUpdate={handleTimeUpdate}
      onError={(e) => {
        console.error('Video error:', e)
        const video = e.target as HTMLVideoElement
        console.error('Video error details:', {
          error: video.error,
          networkState: video.networkState,
          readyState: video.readyState
        })
      }}
      onLoadedData={() => {
        console.log('Video loaded successfully')
      }}
    >
      Your browser does not support the video tag.
    </video>
  )
}