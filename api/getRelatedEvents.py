from fastapi import APIRouter, Query, HTTPException
from app.hybrid_searcher import HybridSearcher
from typing import Optional
from fastapi import Query

router = APIRouter()
hybrid_searcher = HybridSearcher(collection_name="events")

@router.get("/events/{event_id}/related")
def get_related_events(
    event_id: int,
    limit: int = Query(default=4, ge=1, le=50),
    userId: Optional[str] = Query(default=None)
):
    event = hybrid_searcher.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Build location string from components
    location_parts = filter(None, [
        event.get("street"),
        event.get("ward"),
        event.get("district"),
        event.get("city")
    ])
    location_str = ", ".join(location_parts)

    parts = [event["eventName"]]
    if event.get("event_description"):
        parts.append(event["event_description"])
    if location_str:
        parts.append(f"Located at {location_str}")
    if event.get("categories"):
        parts.append(f"Categories: {', '.join(event['categories'])}")
    query = ". ".join(parts)
    
    results = hybrid_searcher.search(
        text=query,
        limit=limit+1,  # fetch one extra in case the event itself is returned
        offset=0,
        user_id=userId,
        extra_filter=None
    )
    
    # Exclude the current event from results
    filtered = [e for e in results if str(e.get("id")) != str(event_id)]
    return {"related_events": filtered[:limit]}