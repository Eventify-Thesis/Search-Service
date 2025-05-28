from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
import os
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.http import models
import google.generativeai as genai
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize models and clients
embedding_model = None
qdrant_client = None
genai_client = None

def initialize_services():
    """Initialize embedding model, Qdrant client, and Gemini API"""
    global embedding_model, qdrant_client, genai_client
    
    try:
        # Initialize embedding model
        logger.info("Loading embedding model...")
        embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # Initialize Qdrant client (using cloud configuration like hybrid_searcher)
        logger.info("Connecting to Qdrant Cloud...")
        qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        # Set the same models as hybrid_searcher
        qdrant_client.set_model("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        
        # Initialize Gemini API
        logger.info("Initializing Gemini API...")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        genai.configure(api_key=gemini_api_key)
        genai_client = genai.GenerativeModel('gemini-2.0-flash')
        
        logger.info("All services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {str(e)}")
        raise

# Initialize services on module load
initialize_services()

class ChatRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    language: Optional[str] = "en"
    max_results: Optional[int] = 5

class EventResult(BaseModel):
    id: str
    title: str
    description: str
    city: str
    start_time: Optional[str] = ""
    end_time: Optional[str] = ""
    category: str
    score: float
    url: Optional[str] = ""

class ChatResponse(BaseModel):
    text: str
    events: List[EventResult]
    query_embedding_time: float
    search_time: float
    generation_time: float

@router.post("/chat", response_model=ChatResponse)
async def chat_with_events(request: ChatRequest):
    """
    Process a chat query by:
    1. Embedding the query using Qdrant's query method
    2. Searching Qdrant for relevant events
    3. Generating a response using Gemini
    4. Returning both the response and relevant events
    """
    try:
        import time
        
        logger.info(f"Processing chat query: '{request.query}'")
        
        # Step 1: Use Qdrant's query method (which handles embedding internally)
        start_time = time.time()
        
        # Step 2: Search Qdrant for relevant events using query method like hybrid_searcher
        search_results = qdrant_client.query(
            collection_name="events",
            query_text=request.query,
            limit=request.max_results
        )
        
        search_time = time.time() - start_time
        logger.info(f"Qdrant search completed in {search_time:.3f}s, found {len(search_results)} results")
        
        # Step 3: Process search results
        events = []
        context_events = []
        
        for result in search_results:
            # Use metadata instead of payload for Qdrant Cloud
            metadata = result.metadata if hasattr(result, 'metadata') else result.payload            
            # Convert Unix timestamp to datetime string if it exists
            start_time = ""
            if metadata.get("startTime") is not None:
                try:
                    start_time = datetime.fromtimestamp(float(metadata["startTime"])).isoformat()
                except (ValueError, TypeError):
                    start_time = ""
            
            event = EventResult(
                id=str(metadata.get("id", "")),
                title=metadata.get("eventName", ""),
                description=metadata.get("eventDescription", ""),
                city=metadata.get("city", ""),
                start_time=start_time,
                end_time="",  # Add end time conversion if needed
                category=metadata.get("categories", [""])[0] if metadata.get("categories") else "",
                score=float(result.score if hasattr(result, 'score') else 0.0),
                url=metadata.get("url", "")
            )
            events.append(event)
            
            
            # Prepare context for Gemini
            context_events.append({
                "title": event.title,
                "description": event.description,
                "city": event.city,
                "start_time": event.start_time,
                "category": event.category
            })
        
        # Step 4: Generate response using Gemini
        start_time = time.time()
        
        # Build prompt for Gemini
        context_text = ""
        if context_events:
            context_text = "Here are some relevant events I found:\n\n"
            for i, event in enumerate(context_events, 1):
                context_text += f"{i}. **{event['title']}**\n"
                context_text += f"   - Location: {event['city']}\n"
                context_text += f"   - Date: {event['start_time']}\n"
                context_text += f"   - Category: {event['category']}\n"
                context_text += f"   - Description: {event['description'][:200]}...\n\n"
        
        prompt = f"""You are a helpful event discovery assistant. A user asked: "{request.query}"

{context_text}

Please provide a natural, conversational response that:
1. Directly addresses the user's question
2. Highlights the most relevant events from the context
3. Provides helpful details about timing, location, and what to expect
4. Suggests related events or categories they might be interested in
5. Keep the tone friendly and enthusiastic about events

If no relevant events were found, suggest alternative search terms or popular event categories.

Response:"""

        try:
            response = genai_client.generate_content(prompt)
            generated_text = response.text
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            # Fallback response
            if events:
                generated_text = f"I found {len(events)} events related to your query '{request.query}'. Here are the top matches that might interest you!"
            else:
                generated_text = f"I couldn't find specific events matching '{request.query}', but let me suggest some popular categories you might enjoy: music concerts, food festivals, art exhibitions, or sports events."
        
        generation_time = time.time() - start_time
        logger.info(f"Response generated in {generation_time:.3f}s")
        
        return ChatResponse(
            text=generated_text,
            events=events,
            query_embedding_time=0.0,  # Embedding is handled internally by Qdrant
            search_time=search_time,
            generation_time=generation_time
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 