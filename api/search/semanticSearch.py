from fastapi import APIRouter, Query, Depends
from app.hybrid_searcher import HybridSearcher, models
from app.auth import optional_verify_token
from typing import Optional
from datetime import datetime, timedelta

router = APIRouter()
hybrid_searcher = HybridSearcher(collection_name="events")

@router.get("")
def search_events(
    q: Optional[str] = Query(default=None, description="Search query (optional, leave empty to search by category or city only)"),
    limit: int = Query(default=15, ge=1, le=100),
    page: int = Query(default=1, ge=1),  # Page number (defaults to 1)
    city: Optional[str] = Query(default=None),
    categories: Optional[list[str]] = Query(default=None),
    startDate: Optional[str] = Query(default=None, alias="start_date"),
    endDate: Optional[str] = Query(default=None, alias="end_date"),
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
        user_id=user_id,
        extra_filter=extra_filter,
        startDate=startDate,
        endDate=endDate
    )

    return {
        "result": results,
        "page": page,  # Return current page
        "limit": limit,  # Return limit
    }
