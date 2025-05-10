from fastapi import APIRouter, HTTPException
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from app.hybrid_searcher import HybridSearcher, models

router = APIRouter()


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST"),
        port=os.getenv("DATABASE_PORT"),
        user=os.getenv("DATABASE_USERNAME"),
        password=os.getenv("DATABASE_PASSWORD"),
        dbname=os.getenv("DATABASE_NAME")
    )


@router.get("/events-by-category")
def get_events_by_category():
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        # Fetch all categories
        cursor.execute("SELECT code, name_en, name_vi FROM categories")
        categories = cursor.fetchall()

        # Initialize HybridSearcher
        searcher = HybridSearcher(collection_name="events")

        # Organize events by category
        categorized_events = {}
        for category in categories:
            category_code = category["code"].lower()
            category_name_en = category["name_en"]
            category_name_vi = category["name_vi"]

            if category_code:
                extra_filter = models.Filter(
                    must=[models.FieldCondition(key="categories", match=models.MatchAny(any=[category_code]))]
                )
            else:
                extra_filter = None

            events = searcher.search(
                text="",
                city="",
                limit=5,
                user_id=None,
                extra_filter=extra_filter,
                startDate=None,
                endDate=None
            )
            
            categorized_events[category_code] = {
                "title": {
                    "en": category_name_en,
                    "vi": category_name_vi
                },
                "events": events
            }

        return categorized_events

    except Exception as e:
        logging.error("Error fetching events by category: %s", e)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        cursor.close()
        conn.close()
