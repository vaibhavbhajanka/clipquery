import { NextResponse } from 'next/server'

export async function GET() {
  // Return WebSocket URL configuration for the client
  // This keeps the actual URL hidden server-side
  const WS_URL = process.env.WS_URL || 'ws://localhost:8000'
  
  // In production, you might want to return a relative WebSocket endpoint
  // that your infrastructure (like a reverse proxy) can handle
  return NextResponse.json({
    wsUrl: WS_URL,
    // You could add additional config here if needed
  })
}