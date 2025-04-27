from fastapi import APIRouter
import os
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter()

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DATABASE_HOST"),
        port=os.getenv("DATABASE_PORT"),
        user=os.getenv("DATABASE_USERNAME"),
        password=os.getenv("DATABASE_PASSWORD"),
        dbname=os.getenv("DATABASE_NAME")
    )

@router.get("/metadata")
def get_search_metadata():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    # Fetch categories
    cursor.execute("SELECT id, code, name_en, name_vi, image FROM categories ORDER BY name_en ASC")
    categories = [
        {
            "name": {"en": row["name_en"], "vi": row["name_vi"]},
            "id": row["id"],
            "code": row["code"],
            "image": row["image"],
            "deeplink": f"https://ticketbox.vn/search?cate={row['code']}&utm_medium=cate-{row['code']}&utm_source=tkb-view-search"
        }
        for row in cursor.fetchall()
    ]
    # Fetch cities
    cursor.execute("SELECT id, origin_id, name, name_en FROM cities WHERE status=1 ORDER BY sort ASC, name_en ASC")
    cities = [
        {
            "id": row["origin_id"],
            "code": row["origin_id"],
            "name": {"en": row["name_en"], "vi": row["name"]},
            "image": "",  # You can add image URLs if you have them
            "deeplink": f"https://ticketbox.vn/search?local={row['origin_id']}&utm_medium={row['origin_id']}&utm_source=tkb-view-search"
        }
        for row in cursor.fetchall()
    ]
    conn.close()
    response = {
        "status": 1,
        "message": "Success",
        "data": {
            "result": {
                "categories": categories,
                "cities": cities,
                "promotions": None,
                "trendingKeywords": []  # You can fill this if you have trending keywords logic
            }
        },
        "code": 0,
        "traceId": ""
    }
    return response
