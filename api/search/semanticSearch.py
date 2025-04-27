from fastapi import APIRouter, Query, Depends
from app.hybrid_searcher import HybridSearcher, models
from app.auth import optional_verify_token
from typing import Optional

router = APIRouter()
hybrid_searcher = HybridSearcher(collection_name="events")

@router.get("")
def search_events(
    q: str = Query(...),
    limit: int = Query(default=15, ge=1, le=100),
    city: Optional[str] = Query(default=None),
    categories: Optional[list[str]] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    user: Optional[dict] = Depends(optional_verify_token),
):
    user_id = user["sub"] if user else None
    # Lowercase city and categories for case-insensitive search
    city_lower = city.lower() if city else None
    categories_lower = None
    extra_filter = None
    if categories:
        if isinstance(categories, str):
            categories = [categories]
        categories_lower = [cat.lower() for cat in categories]
        extra_filter = models.Filter(
            must=[models.FieldCondition(key="categories", match=models.MatchAny(values=categories_lower))]
        )
    return {"result": hybrid_searcher.search(
        text=q,
        city=city_lower,
        limit=limit,
        user_id=user_id,
        extra_filter=extra_filter,
        start_date=start_date,
        end_date=end_date
    )}
