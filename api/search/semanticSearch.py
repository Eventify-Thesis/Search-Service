from fastapi import APIRouter, Query, Depends
from app.hybrid_searcher import HybridSearcher, models
from app.auth import optional_verify_token
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter()
hybrid_searcher = HybridSearcher(collection_name="events")
score_thresholds = 0.3

@router.get("")
def search_events(
    q: Optional[str] = Query(default=None, description="Search query (optional, leave empty to search by category or city only)"),
    limit: int = Query(default=15, ge=1, le=100),
    page: int = Query(default=1, ge=1),  # Page number (defaults to 1)
    city: Optional[str] = Query(default=None),
    categories: Optional[list[str]] = Query(default=None),
    userId: Optional[str] = Query(default=None),
    startDate: Optional[str] = Query(default=None),
    endDate: Optional[str] = Query(default=None),
    min_lat: Optional[float] = Query(default=None, description="Minimum latitude for bounding box filter"),
    max_lat: Optional[float] = Query(default=None, description="Maximum latitude for bounding box filter"),
    min_lon: Optional[float] = Query(default=None, description="Minimum longitude for bounding box filter"),
    max_lon: Optional[float] = Query(default=None, description="Maximum longitude for bounding box filter"),
    user: Optional[dict] = Depends(optional_verify_token),
):
    """
    Search for events using semantic text, category, city, and date filters.
    Pagination is handled by `page` and `limit` parameters.
    """
    user_id = user["sub"] if user else None
    # Lowercase city and categories for case-insensitive search
    city_lower = city.lower() if city else None
    categories_lower = None
    extra_filter = None

    if categories:
        # If categories is a list of 1 element containing commas -> split
        if len(categories) == 1 and ',' in categories[0]:
            categories = [cat.strip() for cat in categories[0].split(",") if cat.strip()]
        
        categories_lower = [cat.lower() for cat in categories]
        extra_filter = models.Filter(
            must=[models.FieldCondition(key="categories", match=models.MatchAny(any=categories_lower))]  # Filter by categories
        )

    # Get results from searcher
    search_text = q if q is not None else ""
    
    # Calculate offset based on page and limit (offset = (page - 1) * limit)
    offset = (page - 1) * limit
    
    results = hybrid_searcher.search(
        text=search_text,
        city=city_lower,
        limit=limit,
        offset=offset,  # Pass the offset to the search function
        user_id=userId,
        extra_filter=extra_filter,
        startDate=startDate,
        endDate=endDate,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        score_thresholds=score_thresholds
    )

    return {
        "result": results,
        "page": page,  # Return current page
        "limit": limit,  # Return limit
    }
