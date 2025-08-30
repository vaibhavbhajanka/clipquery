'use client'

import React from 'react'
import { VideoSegment } from '../lib/types'
import { useRef, useEffect } from 'react'

interface TranscriptViewerProps {
  segments: VideoSegment[]
  searchQuery?: string
  onSeek: (timestamp: number) => void
  currentTime?: number
  autoScroll?: boolean
}

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

function highlightText(text: string, query?: string): JSX.Element {
  if (!query || query.trim() === '') {
    return <span>{text}</span>
  }

  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  const parts = text.split(regex)

  return (
    <span>
      {parts.map((part, i) => 
        regex.test(part) ? (
          <mark key={i} className="bg-yellow-200 px-1 rounded font-medium">
            {part}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        )
      )}
    </span>
  )
}

export default function TranscriptViewer({ 
  segments, 
  searchQuery, 
  onSeek, 
  currentTime = 0,
  autoScroll = false 
}: TranscriptViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const segmentRefs = useRef<{ [key: string]: HTMLDivElement | null }>({})


  // Find the current active segment based on video time
  const getCurrentSegmentIndex = () => {
    return segments.findIndex(segment => 
      currentTime >= segment.startTime && currentTime <= segment.endTime
    )
  }

  const currentSegmentIndex = getCurrentSegmentIndex()

  // Simple auto-scroll with viewport tracking
  useEffect(() => {
    if (autoScroll && currentSegmentIndex >= 0) {
      const currentSegmentElement = segmentRefs.current[segments[currentSegmentIndex].id]
      const container = containerRef.current?.parentElement
      
      if (currentSegmentElement && container) {
        // Check if transcript section is visible in viewport
        const transcriptSection = containerRef.current?.closest('.bg-white.rounded-xl')
        if (transcriptSection) {
          const rect = transcriptSection.getBoundingClientRect()
          const windowHeight = window.innerHeight
          
          // Calculate visibility ratio
          const visibleTop = Math.max(0, rect.top)
          const visibleBottom = Math.min(windowHeight, rect.bottom)
          const visibleHeight = Math.max(0, visibleBottom - visibleTop)
          const visibilityRatio = rect.height > 0 ? visibleHeight / rect.height : 0
          
          // If transcript is less than 50% visible, bring it into view first
          if (visibilityRatio < 0.5) {
            transcriptSection.scrollIntoView({ 
              behavior: 'smooth', 
              block: 'center',
              inline: 'nearest'
            })
            
            // Then scroll within the container after page scroll
            setTimeout(() => {
              const elementOffsetTop = currentSegmentElement.offsetTop - containerRef.current!.offsetTop
              const containerHeight = container.clientHeight
              const targetScrollTop = elementOffsetTop - (containerHeight / 2)
              
              container.scrollTo({
                top: Math.max(0, targetScrollTop),
                behavior: 'smooth'
              })
            }, 600)
          } else {
            // Transcript is visible enough, just scroll within container
            const elementOffsetTop = currentSegmentElement.offsetTop - containerRef.current!.offsetTop
            const containerHeight = container.clientHeight
            const targetScrollTop = elementOffsetTop - (containerHeight / 2)
            
            container.scrollTo({
              top: Math.max(0, targetScrollTop),
              behavior: 'smooth'
            })
          }
        }
      }
    }
  }, [currentSegmentIndex, autoScroll, segments])
  if (segments.length === 0) {
    return (
      <div className="text-center py-12">
        <svg className="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-gray-600 font-medium">No transcript available</p>
        <p className="text-gray-500 text-sm mt-1">Process the video to generate transcript</p>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="space-y-1">
      {segments.map((segment, i) => {
        const isActive = i === currentSegmentIndex
        
        return (
          <div
            key={segment.id || i}
            ref={el => { segmentRefs.current[segment.id] = el!; }}
            className={`group flex flex-col sm:flex-row gap-2 sm:gap-4 p-2 sm:p-3 rounded-lg cursor-pointer transition-all duration-200 ${
              isActive 
                ? 'bg-blue-100 border-l-4 border-blue-500 shadow-sm' 
                : 'hover:bg-gray-50'
            }`}
            onClick={() => onSeek(segment.startTime)}
          >
            <div className="flex-shrink-0 w-full sm:w-16 text-left sm:text-right">
              <button className={`text-xs font-mono transition-all ${
                isActive 
                  ? 'text-blue-700 font-bold' 
                  : 'text-gray-500 hover:text-blue-600 group-hover:font-semibold'
              }`}>
                {formatTime(segment.startTime)}
              </button>
            </div>
            
            <div className="flex-1 min-w-0">
              <p className={`text-sm leading-relaxed ${
                isActive ? 'text-blue-900 font-medium' : 'text-gray-800'
              }`}>
                {highlightText(segment.text.trim(), searchQuery)}
              </p>
            </div>
            
            <div className={`flex-shrink-0 transition-opacity self-end sm:self-center ${
              isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
            }`}>
              <svg className={`w-3 h-3 sm:w-4 sm:h-4 ${
                isActive ? 'text-blue-600' : 'text-gray-400'
              }`} fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
        )
      })}
    </div>
  )
}
