from fastapi import APIRouter, Query, HTTPException
from app.hybrid_searcher import HybridSearcher, models

router = APIRouter()
hybrid_searcher = HybridSearcher(collection_name="events")

@router.get("/events/{event_id}/related")
def get_related_events(event_id: str, limit: int = Query(default=4, ge=1, le=50)):
    event = hybrid_searcher.get_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    parts = [event["eventName"]]
    if event.get("event_description"):
        parts.append(event["event_description"])
    if event.get("location_str"):
        parts.append(f"Located at {event['location_str']}")
    if event.get("categories_str"):
        parts.append(f"Categories: {event['categories_str']}")
    query = ". ".join(parts)
    
    results = hybrid_searcher.search(
        text=query,
        limit=limit+1,  # fetch one extra in case the event itself is returned
        extra_filter=extra_filter
    )
    # Exclude the current event from results
    filtered = [e for e in results if str(e.get("id")) != str(event_id)]
    return {"related_events": filtered[:limit]}