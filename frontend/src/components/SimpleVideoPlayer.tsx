'use client'

import { useRef, useEffect, useCallback } from 'react'

interface SimpleVideoPlayerProps {
  url: string
  seekTo?: number
  onProgress?: (currentTime: number) => void
}

export default function SimpleVideoPlayer({ url, seekTo, onProgress }: SimpleVideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const lastUpdateTime = useRef<number>(0)

  useEffect(() => {
    if (seekTo !== undefined && videoRef.current) {
      videoRef.current.currentTime = seekTo
    }
  }, [seekTo])

  // Throttle progress updates to avoid excessive re-renders
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

  return (
    <div className="w-full">
      <video
        ref={videoRef}
        src={url}
        controls
        width="100%"
        height="auto"
        className="w-full h-auto max-h-[60vh] sm:max-h-[450px] rounded-xl shadow-lg bg-black"
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
    </div>
  )
}