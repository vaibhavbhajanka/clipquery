from sqlalchemy.orm import Session
from fastapi import WebSocket, WebSocketDisconnect
from typing import List
import json
import os
import re
from openai import OpenAI

try:
    from pinecone import Pinecone
except ImportError:
    import pinecone
    Pinecone = pinecone

from app.models import VideoSegment as VideoSegmentModel


async def unified_video_search(db: Session, video_id: str, query: str, top_k: int = 5):
    """Unified search function used by both chat and search endpoints"""
    try:
        print(f"Searching for: '{query}' in video {video_id}")
        
        # Check if Pinecone is configured
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if pinecone_api_key and pinecone_api_key != "your_pinecone_key_here":
            try:
                # Use Pinecone for semantic search
                openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                pc = Pinecone(api_key=pinecone_api_key)
                
                index_name = os.getenv("PINECONE_INDEX_NAME", "clipquery-segments")
                if index_name in [index.name for index in pc.list_indexes()]:
                    # Generate query embedding
                    embedding = openai_client.embeddings.create(
                        model="text-embedding-3-small",
                        input=query,
                    )
                    
                    # Search Pinecone
                    index = pc.Index(index_name)
                    search_results = index.query(
                        vector=embedding.data[0].embedding,
                        filter={"video_id": video_id},
                        top_k=top_k,
                        include_metadata=True
                    )
                    
                    results = [
                        {
                            "text": match.metadata.get("text", ""),
                            "start_time": match.metadata.get("start_time", 0),
                            "end_time": match.metadata.get("end_time", 0),
                            "confidence": match.score or 0
                        }
                        for match in search_results.matches if match.metadata.get("text", "").strip()
                    ]
                    
                    print(f"Pinecone found {len(results)} results")
                    for i, result in enumerate(results[:3], 1):
                        print(f"   {i}. [{result['start_time']:.1f}s] (score: {result['confidence']:.3f}) {result['text'][:50]}...")
                    
                    return results
                    
            except Exception as pinecone_error:
                print(f"Pinecone error: {pinecone_error}")
        
        # Fallback to database search
        print(f"Using database search fallback")
        segments = db.query(VideoSegmentModel).filter(
            VideoSegmentModel.video_id == video_id,
            VideoSegmentModel.text.ilike(f"%{query}%")
        ).order_by(VideoSegmentModel.start_time).limit(top_k).all()
        
        # If no results and query has multiple words, try individual words
        if not segments and len(query.split()) > 1:
            words = query.split()
            for word in words:
                if len(word) > 3:  # Only search for meaningful words
                    word_segments = db.query(VideoSegmentModel).filter(
                        VideoSegmentModel.video_id == video_id,
                        VideoSegmentModel.text.ilike(f"%{word}%")
                    ).order_by(VideoSegmentModel.start_time).limit(3).all()
                    segments.extend(word_segments)
                    if len(segments) >= top_k:  # Don't get too many
                        break
        
        results = [
            {
                "text": segment.text,
                "start_time": segment.start_time,
                "end_time": segment.end_time,
                "confidence": 0.7  # Default confidence for text search
            }
            for segment in segments
        ]
        
        print(f"Database found {len(results)} results")
        return results
        
    except Exception as e:
        print(f"Search error: {e}")
        return []


async def handle_chat_websocket(websocket: WebSocket, video_id: str, db: Session):
    """Handle WebSocket chat functionality"""
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            user_message = message_data.get("message", "")
            
            if not user_message.strip():
                continue
                
            print(f"User message: {user_message}")
            
            # Use unified search function (same as search endpoint)
            try:
                search_results = await unified_video_search(db, video_id, user_message, top_k=5)
                print(f"Chat search: Found {len(search_results)} results")
                
            except Exception as e:
                print(f"Chat search error: {e}")
                search_results = []
            
            # Build context from search results with timestamp info
            search_segments = []
            context_with_timestamps = []
            
            if search_results:
                print(f"Building context from {len(search_results)} results")
                
                # Process all results and build context with timestamp references
                for i, result in enumerate(search_results):
                    start_time = result.get('start_time', 0)
                    end_time = result.get('end_time', start_time)
                    text = result.get('text', '').strip()
                    confidence = result.get('confidence', 0)
                    
                    if text:
                        # Add timestamp info to the context
                        context_with_timestamps.append(f"[{start_time:.1f}s] {text}")
                        
                        # Store segment data for frontend
                        search_segments.append({
                            'start_time': start_time,
                            'end_time': end_time,
                            'text': text,
                            'confidence': confidence,
                            'similarity_score': confidence,
                            'timestamp_text': f"{start_time:.1f}s",
                            'relevance_rank': i + 1
                        })
                        
                        print(f"   [{start_time:.1f}s] (score: {confidence:.3f}): {text[:60]}...")
            else:
                print("No segments found for context building")
            
            # Combine context with timestamps for better answers
            video_context = " ".join(context_with_timestamps) if context_with_timestamps else ""
            
            # Enhanced system prompt for natural, contextual responses
            system_prompt = """You are an intelligent video assistant that helps users understand video content. You have access to the video's transcript and can provide contextual answers.

Guidelines for responses:
- Be conversational and helpful - answer the user's question directly
- Only mention timestamps in [XX.Xs] format when they genuinely add value to help the user find relevant content
- Keep responses concise but informative (2-3 sentences ideal)
- Focus on being accurate and useful
- If the video content doesn't contain relevant information, say so honestly
- Don't force timestamp references into responses where they're not helpful"""
            
            if video_context:
                system_prompt += f"\n\nRelevant video content found:\n{video_context}"
                system_prompt += f"\n\nWhen answering, include timestamps like [5.0s] from the content above if they help the user locate relevant information. The timestamps are already formatted correctly - just include them naturally in your response when they add value."
            else:
                system_prompt += "\n\nNo specific video segments match this query. Answer based on general knowledge if appropriate, or let the user know the video doesn't contain relevant information."
            
            # Call OpenAI with improved error handling
            try:
                openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    stream=True,
                    max_tokens=250,
                    temperature=0.4
                )
                
                # Stream response with better error handling
                full_response = ""
                try:
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            full_response += content
                            
                            await websocket.send_text(json.dumps({
                                "type": "chunk",
                                "content": content
                            }))
                    
                    # Send completion signal with enhanced debugging data
                    await websocket.send_text(json.dumps({
                        "type": "complete",
                        "full_response": full_response,
                        "video_context_used": bool(video_context),
                        "segments_found": len(context_with_timestamps),
                        "search_segments": search_segments  # Include segment data for accurate seeking
                    }))
                    
                    # Enhanced debugging output
                    print(f"Chat Response Complete for query: '{user_message}'")
                    print(f"   Search Results: {len(search_results)} segments found")
                    print(f"   Context Used: {bool(video_context)}")
                    print(f"   Response Length: {len(full_response)} chars")
                    print(f"   AI Response: \"{full_response[:100]}...\"" if len(full_response) > 100 else f"   AI Response: \"{full_response}\"")
                    
                    # Check if response contains timestamp patterns
                    timestamp_patterns = [
                        r'\[\d+(?:\.\d+)?s\]',  # [5.0s]
                        r'(?:at|around) \d+(?:\.\d+)? seconds?',  # at 5.0 seconds
                        r'At \d+(?:\.\d+)?s',  # At 5.0s
                    ]
                    found_timestamps = []
                    for pattern in timestamp_patterns:
                        matches = re.findall(pattern, full_response, re.IGNORECASE)
                        found_timestamps.extend(matches)
                    
                    if found_timestamps:
                        print(f"   Timestamps in response: {found_timestamps}")
                    else:
                        print(f"   No timestamps found in AI response")
                    
                    if search_segments:
                        print(f"   Matched Segments:")
                        for i, seg in enumerate(search_segments, 1):
                            similarity = seg.get('similarity_score', 0)
                            confidence = seg.get('confidence', 0)
                            timestamp = seg.get('start_time', 0)
                            text_preview = seg.get('text', '')[:60] + "..." if len(seg.get('text', '')) > 60 else seg.get('text', '')
                            print(f"      {i}. [{timestamp:.1f}s] (score:{confidence:.3f})")
                            print(f"         \"{text_preview}\"")
                    else:
                        print(f"   No segments sent to frontend")
                        print(f"   This means no context was provided to the AI")
                    
                except Exception as stream_error:
                    print(f"Streaming error: {stream_error}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Response streaming interrupted"
                    }))
                
            except Exception as e:
                print(f"OpenAI error: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"AI service temporarily unavailable: {str(e)}"
                }))
    
    except WebSocketDisconnect:
        raise  # Re-raise to be handled by caller
    except Exception as e:
        print(f"Chat handler error: {e}")
        raise