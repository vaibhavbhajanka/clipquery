'use client'

import { useState, useEffect, useRef } from 'react'
import ChatMessage from './ChatMessage'

interface ChatMessageData {
  id: string
  message: string
  isUser: boolean
  timestamp: Date
  searchSegments?: any[]  // Store search segment data for accurate seeking
}

interface ChatPanelProps {
  videoId: string | null
  disabled?: boolean
  onSeek?: (timestamp: number) => void
}

export default function ChatPanel({ videoId, disabled, onSeek }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessageData[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isConnected, setIsConnected] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const [reconnectAttempts, setReconnectAttempts] = useState(0)
  
  const websocketRef = useRef<WebSocket | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const currentResponseRef = useRef<string>('')
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const maxReconnectAttempts = 5

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // Manual retry function
  const retryConnection = () => {
    setReconnectAttempts(0)
    setConnectionError(null)
    setIsConnected(false)
    
    // Close existing connection if any
    if (websocketRef.current) {
      websocketRef.current.close(1000, 'Manual retry')
    }
    
    // Clear any pending reconnection
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    
    // Trigger new connection
    setTimeout(() => {
      if (videoId) {
        // The useEffect will handle the reconnection
        setConnectionError('Connecting...')
      }
    }, 100)
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Connect to WebSocket when videoId is available
  useEffect(() => {
    // console.log('ChatPanel effect triggered - videoId:', videoId, 'disabled:', disabled)
    
    if (!videoId) {
      console.log('Not connecting - no videoId')
      return
    }

    const connectWebSocket = async () => {
      try {
        // Fetch WebSocket configuration from server
        const configResponse = await fetch('/api/ws-config')
        const config = await configResponse.json()
        
        const wsUrl = `${config.wsUrl}/ws/chat/${videoId}`
        // console.log('Attempting WebSocket connection to:', wsUrl)
        const ws = new WebSocket(wsUrl)
        
        ws.onopen = () => {
          // console.log('WebSocket connected successfully')
          setIsConnected(true)
          setConnectionError(null)
          setReconnectAttempts(0) // Reset reconnect attempts on successful connection
        }

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            
            if (data.type === 'chunk') {
              // Streaming response chunk
              currentResponseRef.current += data.content
              
              // Update the last message if it's an AI response being streamed
              setMessages(prev => {
                const lastMessage = prev[prev.length - 1]
                if (lastMessage && !lastMessage.isUser && lastMessage.id === 'streaming') {
                  return [
                    ...prev.slice(0, -1),
                    {
                      ...lastMessage,
                      message: currentResponseRef.current
                    }
                  ]
                }
                return prev
              })
              
            } else if (data.type === 'complete') {
              // Response complete
              setIsTyping(false)
              currentResponseRef.current = ''
              
              // Update the streaming message with final response and proper ID
              setMessages(prev => {
                const lastMessage = prev[prev.length - 1]
                if (lastMessage && !lastMessage.isUser && lastMessage.id === 'streaming') {
                  return [
                    ...prev.slice(0, -1),
                    {
                      ...lastMessage,
                      id: `ai-${Date.now()}`,
                      message: data.full_response || lastMessage.message,
                      searchSegments: data.search_segments || []  // Store search segments for accurate seeking
                    }
                  ]
                }
                return prev
              })
              
              // console.log(`Response complete. Video context used: ${data.video_context_used}, Segments: ${data.segments_found || 0}`)
              
            } else if (data.type === 'error') {
              setIsTyping(false)
              currentResponseRef.current = ''
              
              // Replace streaming message with error message
              setMessages(prev => {
                const lastMessage = prev[prev.length - 1]
                if (lastMessage && !lastMessage.isUser && lastMessage.id === 'streaming') {
                  return [
                    ...prev.slice(0, -1),
                    {
                      id: `error-${Date.now()}`,
                      message: `Sorry, I encountered an error: ${data.message}`,
                      isUser: false,
                      timestamp: new Date()
                    }
                  ]
                }
                return prev
              })
              
              setConnectionError(null) // Clear connection error if it was just a processing error
            }
            
          } catch (error) {
            // console.error('Error parsing WebSocket message:', error)
            setIsTyping(false)
            setConnectionError('Received invalid response from server')
            
            // Remove streaming message if parsing failed
            setMessages(prev => prev.filter(msg => msg.id !== 'streaming'))
          }
        }

        ws.onclose = (event) => {
          // console.log('WebSocket disconnected', event.code, event.reason)
          setIsConnected(false)
          setIsTyping(false)
          
          // Clear any streaming message
          setMessages(prev => prev.filter(msg => msg.id !== 'streaming'))
          
          // Attempt to reconnect with exponential backoff if not intentionally closed
          if (event.code !== 1000 && event.code !== 1001 && videoId && reconnectAttempts < maxReconnectAttempts) {
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000) // Max 10 seconds
            setConnectionError(`Connection lost. Reconnecting in ${Math.ceil(delay/1000)}s... (${reconnectAttempts + 1}/${maxReconnectAttempts})`)
            
            reconnectTimeoutRef.current = setTimeout(() => {
              // console.log(`Reconnect attempt ${reconnectAttempts + 1}/${maxReconnectAttempts}`)
              setReconnectAttempts(prev => prev + 1)
              setConnectionError(null)
              connectWebSocket()
            }, delay)
          } else if (reconnectAttempts >= maxReconnectAttempts) {
            setConnectionError('Unable to connect to chat service. Please refresh the page.')
          }
        }

        ws.onerror = (error) => {
          // console.error('WebSocket error:', error)
          setConnectionError('Connection error. Retrying...')
          setIsConnected(false)
          setIsTyping(false)
          
          // Clear any streaming message
          setMessages(prev => prev.filter(msg => msg.id !== 'streaming'))
        }

        websocketRef.current = ws

      } catch (error) {
        // console.error('Failed to connect WebSocket:', error)
        setConnectionError('Failed to connect to chat service')
      }
    }

    // Small delay to ensure component is fully mounted
    const connectionTimeout = setTimeout(() => {
      connectWebSocket()
    }, 100)

    // Cleanup on unmount
    return () => {
      clearTimeout(connectionTimeout)
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      if (websocketRef.current && websocketRef.current.readyState === WebSocket.OPEN) {
        websocketRef.current.close(1000, 'Component unmounting')
      }
    }
  }, [videoId])

  const sendMessage = async () => {
    if (!inputMessage.trim() || !isConnected || !websocketRef.current) {
      return
    }

    const userMessage: ChatMessageData = {
      id: `user-${Date.now()}`,
      message: inputMessage.trim(),
      isUser: true,
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    
    // Clear input and show typing indicator immediately
    const originalMessage = inputMessage.trim()
    setInputMessage('')
    setIsTyping(true)
    currentResponseRef.current = ''

    // Add placeholder AI message for streaming
    const aiMessage: ChatMessageData = {
      id: 'streaming',
      message: '',
      isUser: false,
      timestamp: new Date()
    }
    setMessages(prev => [...prev, aiMessage])

    try {
      // Send message directly to WebSocket - backend handles RAG context
      websocketRef.current.send(JSON.stringify({
        message: originalMessage
      }))

    } catch (error) {
      // console.error('Failed to send message:', error)
      setIsTyping(false)
      setConnectionError('Failed to send message. Please try again.')
      
      // Remove the placeholder message
      setMessages(prev => prev.filter(msg => msg.id !== 'streaming'))
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !isTyping) {  // Prevent Enter during AI response
      e.preventDefault()
      sendMessage()
    }
  }

  const handleTimestampClick = (timestamp: number, searchSegment?: any) => {
    if (onSeek) {
      // Use search segment start_time for accurate seeking (like search results)
      // This takes user to the beginning of the relevant segment, not just the mentioned timestamp
      if (searchSegment && searchSegment.start_time !== undefined) {
        onSeek(searchSegment.start_time)
      } else {
        // Fallback to the parsed timestamp if no segment data
        onSeek(timestamp)
      }
    }
  }

  const canTypeMessage = videoId && !disabled  // Allow typing when video is uploaded and ready
  const canSendMessage = videoId && !disabled && isConnected && inputMessage.trim() && !isTyping  // Only send when everything is ready

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Connection Status - Improved Design */}
      {!isConnected && videoId && !disabled && (
        <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-amber-400 rounded-full animate-pulse"></div>
            <p className="text-sm text-amber-700 font-medium">
              {connectionError || 'Connecting to chat...'}
            </p>
          </div>
        </div>
      )}

      {connectionError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-sm text-red-700 font-medium">{connectionError}</p>
            </div>
            {reconnectAttempts >= maxReconnectAttempts && (
              <button
                onClick={retryConnection}
                className="px-3 py-1 bg-red-100 hover:bg-red-200 text-red-700 text-xs font-medium rounded-lg transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        </div>
      )}

      {/* Chat Messages - Enhanced Design */}
      <div className="flex-1 overflow-y-auto mb-6 space-y-4 px-1 min-h-0">
        {messages.length === 0 ? (
          <div className="text-center py-16">
            <div className="w-16 h-16 mx-auto mb-6 bg-gradient-to-br from-blue-100 to-purple-100 rounded-2xl flex items-center justify-center">
              <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Ask me anything about your video</h3>
            <p className="text-sm text-gray-500 leading-relaxed max-w-sm mx-auto">
              I can help you understand the content, find specific moments, or answer questions about what's discussed.
            </p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center">
              <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-xs font-medium">
                "What's this video about?"
              </span>
              <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-xs font-medium">
                "Summarize the key points"
              </span>
              <span className="px-3 py-1 bg-gray-100 text-gray-600 rounded-full text-xs font-medium">
                "Find the main topics"
              </span>
            </div>
          </div>
        ) : (
          <>
            {messages.map(msg => (
              <ChatMessage
                key={msg.id}
                message={msg.message}
                isUser={msg.isUser}
                timestamp={msg.timestamp}
                searchSegments={msg.searchSegments}
                onTimestampClick={handleTimestampClick}
              />
            ))}
            {isTyping && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 text-gray-900 px-5 py-4 rounded-2xl shadow-sm max-w-xs">
                  <div className="flex items-center space-x-2">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.1s'}}></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                    </div>
                    <span className="text-sm text-gray-500 font-medium">AI is thinking...</span>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area - Enhanced Design */}
      <div className="border-t border-gray-100 pt-4 px-1">
        <div className="flex items-end space-x-2 sm:space-x-3">
          <div className="flex-1">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={
                !videoId
                  ? "Upload a video first..."
                  : disabled 
                    ? "Processing video... Chat will be available when ready" 
                    : !isConnected 
                      ? "Connecting to chat service..." 
                      : "Ask about this video..."
              }
              disabled={!canTypeMessage}
              className="w-full px-3 sm:px-4 py-2 sm:py-3 text-sm sm:text-base text-gray-900 placeholder-gray-400 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-50 disabled:text-gray-500"
            />
          </div>
          <button
            onClick={sendMessage}
            disabled={!canSendMessage}
            className={`p-2 sm:p-3 rounded-xl font-medium transition-all duration-200 flex items-center justify-center min-w-[40px] sm:min-w-[48px] ${
              canSendMessage
                ? 'bg-blue-600 text-white hover:bg-blue-700 shadow-sm hover:shadow-md transform hover:scale-105 active:scale-95'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'
            }`}
          >
            {isTyping ? (
              <div className="w-4 h-4 sm:w-5 sm:h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
            ) : (
              <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            )}
          </button>
        </div>
        
        {!disabled && isConnected && (
          <p className="text-xs text-gray-400 mt-2 sm:mt-3 text-center">
            Press Enter to send • Click timestamps to jump to video moments
          </p>
        )}
      </div>
    </div>
  )
}