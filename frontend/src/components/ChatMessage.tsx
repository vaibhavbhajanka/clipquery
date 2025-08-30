'use client'

import { useState } from 'react'

interface ChatMessageProps {
  message: string
  isUser: boolean
  timestamp?: Date
  searchSegments?: any[]
  onTimestampClick?: (timestamp: number, searchSegment?: any) => void
}

interface TimestampMatch {
  index: number
  length: number
  timestamp: number
  content: string
}

interface MessagePart {
  type: 'text' | 'timestamp'
  content: string
  timestamp?: number
}

export default function ChatMessage({ 
  message, 
  isUser, 
  timestamp,
  searchSegments,
  onTimestampClick 
}: ChatMessageProps) {
  const [clickedTimestamp, setClickedTimestamp] = useState<number | null>(null)

  const handleTimestampClick = (ts: number, searchSegment?: any) => {
    setClickedTimestamp(ts)
    if (onTimestampClick) {
      onTimestampClick(ts, searchSegment)
    }
    // Reset click feedback after a short delay
    setTimeout(() => setClickedTimestamp(null), 1000)
  }

  // Find matching search segment for a timestamp
  const findSearchSegmentForTimestamp = (timestamp: number) => {
    if (!searchSegments || searchSegments.length === 0) return null
    
    // Try to find exact match first
    const exactMatch = searchSegments.find(segment => 
      Math.abs(segment.start_time - timestamp) < 1 // Within 1 second
    )
    if (exactMatch) return exactMatch
    
    // Find closest match
    const closestMatch = searchSegments.reduce((closest, segment) => {
      const currentDiff = Math.abs(segment.start_time - timestamp)
      const closestDiff = Math.abs(closest.start_time - timestamp)
      return currentDiff < closestDiff ? segment : closest
    })
    
    return closestMatch
  }
  // Parse timestamp references from AI responses - optimized patterns
  const parseTimestampReferences = (text: string): MessagePart[] => {
    // Optimized timestamp patterns (ordered by priority)
    const patterns = [
      // PRIORITY: Match [10.0s] or [45s] format first (most reliable)
      { regex: /\[(\d+(?:\.\d+)?)s\]/g, format: 'bracket_seconds' },
      // "at 45.0 seconds" or "around 45.0 seconds"
      { regex: /(?:at|around) (\d+(?:\.\d+)?) seconds?/gi, format: 'at_seconds' },
      // "At 1:23" (minutes:seconds)
      { regex: /At (\d+):(\d+)/g, format: 'mm:ss' },
      // "At 83s" or "At 83.5s" (seconds)
      { regex: /At (\d+(?:\.\d+)?)s/gi, format: 'seconds' },
      // "1:23" (bare minutes:seconds) - more conservative
      { regex: /\b(\d{1,2}):(\d{2})\b/g, format: 'mm:ss_bare' }
    ]

    const parts: MessagePart[] = []
    const matches: TimestampMatch[] = []

    // Find all matches from all patterns
    patterns.forEach(pattern => {
      let match
      while ((match = pattern.regex.exec(text)) !== null) {
        let timestampValue = 0
        let displayText = match[0]

        switch (pattern.format) {
          case 'bracket_seconds':
            timestampValue = parseFloat(match[1])
            displayText = match[0] // Keep the [XX.Xs] format
            break;
          case 'at_seconds':
            timestampValue = parseFloat(match[1])
            displayText = `${timestampValue}s`
            break
          case 'mm:ss':
            timestampValue = parseInt(match[1]) * 60 + parseInt(match[2])
            displayText = `${match[1]}:${match[2]}`
            break
          case 'mm:ss_bare':
            timestampValue = parseInt(match[1]) * 60 + parseInt(match[2])
            displayText = `${match[1]}:${match[2]}`
            break
          case 'seconds':
            timestampValue = parseFloat(match[1])
            displayText = `${timestampValue}s`
            break
        }

        matches.push({
          index: match.index,
          length: match[0].length,
          timestamp: timestampValue,
          content: displayText
        })
      }
      // Reset regex for next iteration
      pattern.regex.lastIndex = 0
    })

    // Sort matches by position in text
    matches.sort((a, b) => a.index - b.index)

    // Remove overlapping matches (keep the first/longest match)
    const filteredMatches: TimestampMatch[] = []
    for (let i = 0; i < matches.length; i++) {
      const current = matches[i]
      let hasOverlap = false
      
      for (let j = 0; j < filteredMatches.length; j++) {
        const existing = filteredMatches[j]
        const currentEnd = current.index + current.length
        const existingEnd = existing.index + existing.length
        
        // Check if matches overlap
        if (
          (current.index >= existing.index && current.index < existingEnd) ||
          (currentEnd > existing.index && currentEnd <= existingEnd) ||
          (current.index < existing.index && currentEnd > existingEnd)
        ) {
          hasOverlap = true
          break
        }
      }
      
      if (!hasOverlap) {
        filteredMatches.push(current)
      }
    }

    // Build parts array
    let lastIndex = 0
    filteredMatches.forEach(match => {
      // Add text before timestamp
      if (match.index > lastIndex) {
        parts.push({
          type: 'text',
          content: text.slice(lastIndex, match.index)
        })
      }

      // Add clickable timestamp
      parts.push({
        type: 'timestamp',
        content: match.content,
        timestamp: match.timestamp
      })

      lastIndex = match.index + match.length
    })

    // Add remaining text
    if (lastIndex < text.length) {
      parts.push({
        type: 'text',
        content: text.slice(lastIndex)
      })
    }

    return parts.length > 0 ? parts : [{ type: 'text', content: text }]
  }

  const messageParts: MessagePart[] = !isUser ? parseTimestampReferences(message) : [{ type: 'text', content: message }]

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-1`}>
      <div className={`max-w-[85%] sm:max-w-sm lg:max-w-lg px-3 sm:px-5 py-3 sm:py-4 shadow-sm ${
        isUser 
          ? 'bg-blue-600 text-white rounded-2xl rounded-br-lg' 
          : 'bg-white text-gray-900 border border-gray-200 rounded-2xl rounded-bl-lg'
      }`}>
        <div className="break-words leading-relaxed">
          {messageParts.map((part, index) => {
            if (part.type === 'timestamp' && onTimestampClick && part.timestamp !== undefined) {
              const isClicked = clickedTimestamp === part.timestamp
              const searchSegment = findSearchSegmentForTimestamp(part.timestamp)
              
              return (
                <button
                  key={index}
                  onClick={() => handleTimestampClick(part.timestamp!, searchSegment)}
                  className={`inline-flex items-center justify-center p-1.5 sm:p-2 mx-0.5 sm:mx-1 rounded-full cursor-pointer transition-all duration-200 hover:scale-110 shadow-sm ${
                    isClicked 
                      ? 'bg-green-500 text-white shadow-md' 
                      : isUser
                        ? 'bg-blue-400 text-white hover:bg-blue-300'
                        : searchSegment
                          ? 'bg-blue-600 text-white hover:bg-blue-700'
                          : 'bg-gray-500 text-white hover:bg-gray-600'
                  }`}
                  title={searchSegment 
                    ? `Jump to: "${searchSegment.text.substring(0, 50)}..." (${Math.round(searchSegment.confidence * 100)}% match)`
                    : `Jump to ${part.content}`
                  }
                >
                  {isClicked ? (
                    <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  )}
                </button>
              )
            } else {
              return <span key={index} className="text-xs sm:text-sm">{part.content}</span>
            }
          })}
        </div>
      </div>
    </div>
  )
}