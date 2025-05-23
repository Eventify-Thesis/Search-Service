from fastapi import APIRouter, HTTPException
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from app.hybrid_searcher import HybridSearcher, models, DatabasePool
from typing import Dict, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
import redis
import json
from datetime import timedelta
from typing import Optional
from fastapi import Query

router = APIRouter()

# Initialize Redis client
redis_client = redis.Redis(
    host=os.getenv('REDIS_HOST', 'redis'),  # Use environment variable or default to 'redis'
    port=int(os.getenv('REDIS_PORT', 6379)),
    decode_responses=True,  # This will automatically decode responses to strings
    socket_connect_timeout=5,  # Add timeout
    retry_on_timeout=True  # Retry on timeout
)

CACHE_KEY = "events_by_category"
CACHE_DURATION = timedelta(minutes=10)

def fetch_category_events(searcher: HybridSearcher, category_code: str, category_name_en: str, category_name_vi: str, userId: Optional[str] = Query(default=None)) -> tuple:
    """Fetch events for a single category"""
    extra_filter = models.Filter(
        must=[models.FieldCondition(key="categories", match=models.MatchAny(any=[category_code]))]
    ) if category_code else None

    events = searcher.search(
        text="",
        city="",
        limit=5,
        offset=0,
        user_id=userId,
        extra_filter=extra_filter,
        startDate=None,
        endDate=None
    )
    
    return category_code, {
        "title": {
            "en": category_name_en,
            "vi": category_name_vi
        },
        "events": events
    }

@router.get("/events-by-category")
async def get_events_by_category(userId: Optional[str] = Query(default=None)):
    # Try to get from cache first
    cached_data = redis_client.get(CACHE_KEY)
    if cached_data:
        try:
            return json.loads(cached_data)
        except json.JSONDecodeError:
            logging.warning("Failed to decode cached data, fetching fresh data")

    conn = None
    try:
        db_pool = DatabasePool.get_instance()
        conn = db_pool.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Fetch all categories in a single query
        cursor.execute("SELECT code, name_en, name_vi FROM categories")
        categories = cursor.fetchall()

        # Initialize HybridSearcher
        searcher = HybridSearcher(collection_name="events")

        # Use ThreadPoolExecutor to fetch events for all categories concurrently
        with ThreadPoolExecutor(max_workers=min(10, len(categories))) as executor:
            # Create tasks for each category
            futures = [
                executor.submit(
                    fetch_category_events,
                    searcher,
                    category["code"].lower(),
                    category["name_en"],
                    category["name_vi"],
                    userId
                )
                for category in categories
            ]
            
            # Collect results as they complete
            categorized_events = {}
            for future in futures:
                category_code, result = future.result()
                categorized_events[category_code] = result

        # Cache the results
        try:
            redis_client.setex(
                CACHE_KEY,
                CACHE_DURATION,
                json.dumps(categorized_events)
            )
        except redis.RedisError as e:
            logging.error(f"Failed to cache data: {e}")

        return categorized_events

    except Exception as e:
        logging.error("Error fetching events by category: %s", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.release_connection(conn)
