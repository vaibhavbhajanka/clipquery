import { NextRequest, NextResponse } from 'next/server'

const API_URL = process.env.API_URL || 'http://localhost:8000'

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ filename: string }> }
) {
  const resolvedParams = await params
  try {
    const response = await fetch(`${API_URL}/video/${resolvedParams.filename}`, {
      headers: request.headers,
    })

    // Stream the video response
    const headers = new Headers()
    response.headers.forEach((value, key) => {
      headers.set(key, value)
    })

    return new NextResponse(response.body, {
      status: response.status,
      headers,
    })
  } catch (error) {
    console.error('Video proxy error:', error)
    return NextResponse.json(
      { error: 'Failed to fetch video' },
      { status: 500 }
    )
  }
}