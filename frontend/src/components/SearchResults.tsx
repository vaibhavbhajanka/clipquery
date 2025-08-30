'use client'

import { SearchResult } from '@/lib/types'

interface SearchResultsProps {
  results: SearchResult[]
  onSeek: (timestamp: number, resultIndex?: number) => void
  activeResultIndex?: number
}

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = Math.floor(seconds % 60)
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
}

export default function SearchResults({ results, onSeek, activeResultIndex = -1 }: SearchResultsProps) {
  if (results.length === 0) {
    return (
      <div className="text-center py-8">
        <svg className="w-12 h-12 mx-auto text-gray-300 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <p className="text-gray-600 font-medium">No matches found</p>
        <p className="text-gray-500 text-sm mt-1">Try different keywords or phrases</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {results.map((result, i) => {
        const isActive = i === activeResultIndex
        const isPrimary = i === 0
        
        return (
          <div
            key={i}
            className={`group p-3 sm:p-4 rounded-xl cursor-pointer transition-all duration-200 shadow-sm hover:shadow-md ${
              isActive 
                ? 'bg-gradient-to-r from-blue-100 to-blue-200 border-2 border-blue-400' 
                : isPrimary 
                  ? 'bg-gradient-to-r from-green-50 to-green-100 border border-green-300 hover:from-green-100 hover:to-green-200 hover:border-green-400'
                  : 'bg-gradient-to-r from-gray-50 to-gray-100 border border-gray-200 hover:from-blue-50 hover:to-blue-100 hover:border-blue-300'
            }`}
            onClick={() => onSeek(result.startTime, i)}
          >
            <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-3 sm:gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  {isPrimary && (
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
                      isActive 
                        ? 'bg-blue-600 text-white' 
                        : 'bg-green-600 text-white'
                    }`}>
                      {isActive ? 'NOW PLAYING' : 'BEST MATCH'}
                    </span>
                  )}
                  {!isPrimary && (
                    <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-500 text-white">
                      ALSO FOUND
                    </span>
                  )}
                </div>
                <p className="text-sm sm:text-base text-gray-800 leading-relaxed font-medium">
                  {result.text}
                </p>
                <div className="mt-2 flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-xs sm:text-sm">
                  <span className="flex items-center gap-1 text-gray-600">
                    <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {formatTime(result.startTime)} - {formatTime(result.endTime)}
                  </span>
                  <span className="hidden sm:inline text-gray-500">•</span>
                  <span className="text-gray-600">
                    {Math.round(result.confidence * 100)}% confidence
                  </span>
                </div>
              </div>
              
              <div className="flex-shrink-0 self-start sm:self-center">
                <button className={`p-2 rounded-lg transition-colors group-hover:scale-110 transform duration-200 ${
                  isActive 
                    ? 'bg-blue-700 text-white' 
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}>
                  <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}