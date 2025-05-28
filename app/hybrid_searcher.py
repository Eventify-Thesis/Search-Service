import psycopg2
import os
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from datetime import datetime, timezone, timedelta

LOCAL_TIMEZONE = timezone(timedelta(hours=7))  # UTC+7 (Vietnam, Thailand, etc.)
load_dotenv()

class DatabasePool:
    _instance = None
    _pool = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if DatabasePool._pool is None:
            DatabasePool._pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                host=os.getenv("DATABASE_HOST"),
                port=os.getenv("DATABASE_PORT"),
                user=os.getenv("DATABASE_USERNAME"),
                password=os.getenv("DATABASE_PASSWORD"),
                dbname=os.getenv("DATABASE_NAME")
            )

    def get_connection(self):
        return self._pool.getconn()

    def release_connection(self, conn):
        self._pool.putconn(conn)

class HybridSearcher:
    DENSE_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self, collection_name):
        self.collection_name = collection_name
        self.qdrant_client = QdrantClient(os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
        self.qdrant_client.set_model(self.DENSE_MODEL)
        self.db_pool = DatabasePool.get_instance()

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

    def search(self, text: str, city: str = None, limit: int = 15, offset: int = 0, user_id: str = None, extra_filter=None, startDate: str = None, endDate: str = None, min_lat: float = None, max_lat: float = None, min_lon: float = None, max_lon: float = None, score_thresholds: float = None):
        """
        Search for events with optional user interest annotation.
        If user_id is provided, the results will include isInterested field.
        """
        # Get base search results
        results = self._search_base(text, city, limit, offset, extra_filter, startDate, endDate, min_lat, max_lat, min_lon, max_lon, score_thresholds)
        
        # Add interest data if user_id is provided
        if user_id:
            bookmarked_ids = self._fetch_bookmarked_ids(user_id)
            self._annotate_with_bookmarks(results, bookmarked_ids)
        else:
            self._annotate_with_bookmarks(results, set())
            
        return results

    def _search_base(self, text: str, city: str = None, limit: int = 15, offset: int = 0, extra_filter=None, startDate: str = None, endDate: str = None, min_lat: float = None, max_lat: float = None, min_lon: float = None, max_lon: float = None, score_thresholds: float = None):
        """
        Perform base search without user interest annotation.
        This method is used internally and can be used for caching base results.
        """
        query_filter_final = self._build_query_filter(city, extra_filter, startDate, endDate, min_lat, max_lat, min_lon, max_lon)

        search_result = self.qdrant_client.query(
            collection_name=self.collection_name,
            query_text=text,
            query_filter=query_filter_final,
            limit=limit,
            offset=offset
        )

        results = []
        print(score_thresholds)
        for hit in search_result:
            if score_thresholds and text != "" and hit.score < score_thresholds:
                continue
            filtered = {k: v for k, v in hit.metadata.items() if k != "document"}
            results.append(filtered)
            
        return results
    
    def _build_query_filter(self, city, extra_filter, startDate, endDate, min_lat, max_lat, min_lon, max_lon):
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
                key="startTime",
                range=models.Range(**date_range)  # ✅ now gte/lte are floats, not strings
            )

        # Bounding box geo filter - leverages Qdrant's native spatial index for efficient map-based querying
        geo_filter = None
        if all(coord is not None for coord in [min_lat, max_lat, min_lon, max_lon]):
            print(f"Building geo filter with coordinates: min_lat={min_lat}, max_lat={max_lat}, min_lon={min_lon}, max_lon={max_lon}")
            try:
                geo_filter = models.FieldCondition(
                    key="location",
                    geo_bounding_box=models.GeoBoundingBox(
                        top_left=models.GeoPoint(lat=max_lat, lon=min_lon),
                        bottom_right=models.GeoPoint(lat=min_lat, lon=max_lon)
                    )
                )
                print("Successfully created geo filter")
            except Exception as e:
                print(f"Error creating geo filter: {str(e)}")
                raise

        combined_filters = []
        if query_filter and hasattr(query_filter, 'must'):
            combined_filters += query_filter.must
        if extra_filter and hasattr(extra_filter, 'must'):
            combined_filters += extra_filter.must
        if date_filter:
            combined_filters.append(date_filter)
        if geo_filter:
            combined_filters.append(geo_filter)

        final_filter = models.Filter(must=combined_filters) if combined_filters else None
        print(f"Final filter: {final_filter}")
        return final_filter

    def _fetch_bookmarked_ids(self, user_id):
        conn = None
        try:
            conn = self.db_pool.get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("""
                SELECT event_id FROM interests WHERE user_id = %s
            """, (user_id,))
            bookmarked_ids = {row["event_id"] for row in cursor.fetchall()}
            return bookmarked_ids
        finally:
            if conn:
                self.db_pool.release_connection(conn)

    def _annotate_with_bookmarks(self, results, bookmarked_ids):
        for item in results:
            item["isInterested"] = item["id"] in bookmarked_ids