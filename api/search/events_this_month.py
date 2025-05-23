from fastapi import APIRouter
from datetime import datetime, timedelta
from app.hybrid_searcher import HybridSearcher
import calendar
import logging
from typing import Optional
from fastapi import Query

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
router = APIRouter()
hybrid_searcher = HybridSearcher(collection_name="events")

@router.get("/events/this-month")
def get_events_this_month(userId: Optional[str] = Query(default=None)):
    today = datetime.now()
    start_of_month = today.replace(day=1)
    year = today.year
    month = today.month
    _, last_day = calendar.monthrange(year, month)
    end_of_month = today.replace(day=last_day)

    events = hybrid_searcher.search(
        text="",
        city="",
        limit=15,
        offset=0,
        user_id=userId,
        extra_filter=None,
        startDate=start_of_month.strftime("%Y-%m-%d"),
        endDate=end_of_month.strftime("%Y-%m-%d")
    )
    return {"events": events}