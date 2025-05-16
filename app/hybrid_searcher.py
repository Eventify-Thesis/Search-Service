import psycopg2
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from datetime import datetime, timezone, timedelta

LOCAL_TIMEZONE = timezone(timedelta(hours=7))  # UTC+7 (Vietnam, Thailand, etc.)
load_dotenv()

class HybridSearcher:
    DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    SPARSE_MODEL = "prithivida/Splade_PP_en_v1"

    def __init__(self, collection_name):
        self.collection_name = collection_name
        self.qdrant_client = QdrantClient(os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
        self.qdrant_client.set_model(self.DENSE_MODEL)
        self.qdrant_client.set_sparse_model(self.SPARSE_MODEL)

    def get_event_by_id(self, event_id: str):
        """Fetch a single event by its id from Qdrant."""
        result = self.qdrant_client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[models.FieldCondition(key="id", match=models.MatchValue(value=event_id))]
            ),
            limit=1,
            with_vectors=False
        )
        if result and result[0]:
            return result[0][0].payload
        return None

    def search(self, text: str, city: str = None, limit: int = 15, offset: int = 0, user_id: str = None, extra_filter=None, startDate: str = None, endDate: str = None):
        query_filter_final = self._build_query_filter(city, extra_filter, startDate, endDate)

        search_result = self.qdrant_client.query(
            collection_name=self.collection_name,
            query_text=text,
            query_filter=query_filter_final,
            limit=limit,
            offset=offset  # Use offset to handle pagination
        )

        results = []
        for hit in search_result:
            filtered = {k: v for k, v in hit.metadata.items() if k != "document"}
            results.append(filtered)
            
        if user_id:
            bookmarked_ids = self._fetch_bookmarked_ids(user_id)
            self._annotate_with_bookmarks(results, bookmarked_ids)
        else:
            self._annotate_with_bookmarks(results, set())
        return results

    
    def _build_query_filter(self, city, extra_filter, startDate, endDate):
        query_filter = None
        if city:
            city = city.lower()
            query_filter = models.Filter(
                must=[models.FieldCondition(key="city", match=models.MatchValue(value=city))]
            )

        if extra_filter and hasattr(extra_filter, 'must'):
            for cond in extra_filter.must:
                if hasattr(cond, 'key') and cond.key == "categories":
                    if hasattr(cond.match, 'values'):
                        cond.match.values = [v.lower() for v in cond.match.values]

        date_filter = None
        if startDate or endDate:
            date_range = {}

            def parse_date_to_timestamp(date_str):
                if not date_str:
                    return None
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                dt = dt.replace(tzinfo=LOCAL_TIMEZONE)  # ✅ Assume input date is in UTC+7 timezone
                return dt.astimezone(timezone.utc).timestamp()  # ✅ Convert to UTC timestamp

            if startDate:
                date_range['gte'] = parse_date_to_timestamp(startDate)
            if endDate:
                date_range['lte'] = parse_date_to_timestamp(endDate)

            date_filter = models.FieldCondition(
                key="soonest_start_time",
                range=models.Range(**date_range)  # ✅ now gte/lte are floats, not strings
            )

        combined_must = []
        if query_filter and hasattr(query_filter, 'must'):
            combined_must += query_filter.must
        if extra_filter and hasattr(extra_filter, 'must'):
            combined_must += extra_filter.must
        if date_filter:
            combined_must.append(date_filter)

        return models.Filter(must=combined_must) if combined_must else None

    def _fetch_bookmarked_ids(self, user_id):
        conn = psycopg2.connect(
            host=os.getenv("DATABASE_HOST"),
            port=os.getenv("DATABASE_PORT"),
            user=os.getenv("DATABASE_USERNAME"),
            password=os.getenv("DATABASE_PASSWORD"),
            dbname=os.getenv("DATABASE_NAME")
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT event_id FROM interests WHERE user_id = %s
        """, (user_id,))
        bookmarked_ids = {row["event_id"] for row in cursor.fetchall()}
        conn.close()
        return bookmarked_ids

    def _annotate_with_bookmarks(self, results, bookmarked_ids):
        for item in results:
            item["bookmarked"] = item["id"] in bookmarked_ids
