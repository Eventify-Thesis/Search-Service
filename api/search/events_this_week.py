from fastapi import APIRouter
from datetime import datetime, timedelta
from app.hybrid_searcher import HybridSearcher
from app.cache_decorator import cache_endpoint
import logging
from typing import Optional
from fastapi import Query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
hybrid_searcher = HybridSearcher(collection_name="events")

@router.get("/events/this-week")
@cache_endpoint(duration_minutes=10, prefix="events_week")
def get_events_this_week(userId: Optional[str] = Query(default=None)):
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    logger.info(start_of_week)
    logger.info(start_of_week.strftime("%Y-%m-%d"))
    logger.info(end_of_week)
    logger.info(end_of_week.strftime("%Y-%m-%d"))
    events = hybrid_searcher.search(
        text="",
        city="",
        limit=15,
        offset=0,
        user_id=userId,
        extra_filter=None,
        startDate=start_of_week.strftime("%Y-%m-%d"),
        endDate=end_of_week.strftime("%Y-%m-%d")
    )
    return {"events": events}