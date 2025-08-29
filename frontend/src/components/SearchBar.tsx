'use client'

import { useState } from 'react'

interface SearchBarProps {
  onSearch: (query: string) => void
  isSearching?: boolean
  disabled?: boolean
}

export default function SearchBar({ onSearch, isSearching = false, disabled = false }: SearchBarProps) {
  const [query, setQuery] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim() && !isSearching && !disabled) {
      onSearch(query.trim())
    }
  }

  return (
    <form onSubmit={handleSubmit} className="w-full max-w-2xl mx-auto">
      <div className="relative flex items-center">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search within your video... (e.g., 'when does the speaker mention pricing?')"
          className="w-full px-4 py-3 pr-12 text-gray-900 placeholder-gray-400 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
          disabled={isSearching || disabled}
        />
        
        <button
          type="submit"
          disabled={!query.trim() || isSearching || disabled}
          className="absolute right-2 p-2 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSearching ? (
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
          ) : (
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          )}
        </button>
      </div>
      
      {disabled && (
        <p className="text-sm text-gray-500 mt-2 text-center">
          Upload and process a video first to enable search
        </p>
      )}
    </form>
  )
}