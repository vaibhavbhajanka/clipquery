import { NextRequest, NextResponse } from 'next/server'

const API_URL = process.env.API_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: { filename: string } }
) {
  try {
    const response = await fetch(`${API_URL}/video-url/${params.filename}`)
    const data = await response.json()
    return NextResponse.json(data, { status: response.status })
  } catch (error) {
    console.error('Video URL proxy error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch video URL' },
      { status: 500 }
    )
  }
}