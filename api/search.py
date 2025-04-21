from fastapi import APIRouter, Query, Depends
from app.hybrid_searcher import HybridSearcher
from app.auth import optional_verify_token
from typing import Optional

router = APIRouter()
hybrid_searcher = HybridSearcher(collection_name="events")

@router.get("")
def search_events(
    q: str = Query(...),
    limit: int = Query(default=15, ge=1, le=100),
    city: Optional[str] = Query(default=None),
    user: Optional[dict] = Depends(optional_verify_token),
):
    user_id = user["sub"] if user else None
    return {"result": hybrid_searcher.search(
        text=q,
        city=city,
        limit=limit,
        user_id=user_id
    )}
