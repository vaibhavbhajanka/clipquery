'use client'

interface TabSwitcherProps {
  activeTab: 'search' | 'chat'
  onTabChange: (tab: 'search' | 'chat') => void
  disabled?: boolean
}

export default function TabSwitcher({ activeTab, onTabChange, disabled }: TabSwitcherProps) {
  return (
    <div className="flex bg-gray-50 rounded-xl p-1 mb-4 sm:mb-6">
      <button
        onClick={() => onTabChange('search')}
        disabled={disabled}
        className={`flex-1 py-2 sm:py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold rounded-lg transition-all duration-200 ${
          activeTab === 'search'
            ? 'bg-white text-blue-600 shadow-sm'
            : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
        } ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
      >
        <div className="flex items-center justify-center space-x-1 sm:space-x-2">
          <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span>Search</span>
        </div>
      </button>
      
      <button
        onClick={() => onTabChange('chat')}
        disabled={disabled}
        className={`flex-1 py-2 sm:py-3 px-3 sm:px-4 text-xs sm:text-sm font-semibold rounded-lg transition-all duration-200 ${
          activeTab === 'chat'
            ? 'bg-white text-blue-600 shadow-sm'
            : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
        } ${disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
      >
        <div className="flex items-center justify-center space-x-1 sm:space-x-2">
          <svg className="w-3 h-3 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <span>Chat</span>
        </div>
      </button>
    </div>
  )
}