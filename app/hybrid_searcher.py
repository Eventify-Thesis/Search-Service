import psycopg2
import os
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models
from datetime import datetime, timezone, timedelta
import redis
import json
import hashlib
import logging

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
    CACHE_DURATION = timedelta(minutes=5)  # Cache for 5 minutes

    def __init__(self, collection_name):
        self.collection_name = collection_name
        self.qdrant_client = QdrantClient(os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
        self.qdrant_client.set_model(self.DENSE_MODEL)
        self.db_pool = DatabasePool.get_instance()
        
        # Initialize Redis client
        try:
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'redis'),
                port=int(os.getenv('REDIS_PORT', 6379)),
                decode_responses=True,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test Redis connection
            self.redis_client.ping()
        except Exception as e:
            logging.warning(f"Redis connection failed: {e}. Caching will be disabled.")
            self.redis_client = None

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

    def _generate_cache_key(self, text: str, city: str = None, limit: int = 15, offset: int = 0, 
                          extra_filter=None, startDate: str = None, endDate: str = None, 
                          min_lat: float = None, max_lat: float = None, min_lon: float = None, 
                          max_lon: float = None, score_thresholds: float = None):
        """Generate a unique cache key based on search parameters"""
        # Create a string representation of all search parameters
        params = {
            'text': text or '',
            'city': city or '',
            'limit': limit,
            'offset': offset,
            'startDate': startDate or '',
            'endDate': endDate or '',
            'min_lat': min_lat,
            'max_lat': max_lat,
            'min_lon': min_lon,
            'max_lon': max_lon,
            'score_thresholds': score_thresholds,
            'collection': self.collection_name
        }
        
        # Handle extra_filter
        if extra_filter:
            # Convert filter to a serializable format
            filter_str = str(extra_filter)
            params['extra_filter'] = filter_str
        
        # Create hash of parameters
        params_str = json.dumps(params, sort_keys=True)
        cache_key = f"search:{hashlib.md5(params_str.encode()).hexdigest()}"
        return cache_key

    def _search_base(self, text: str, city: str = None, limit: int = 15, offset: int = 0, extra_filter=None, startDate: str = None, endDate: str = None, min_lat: float = None, max_lat: float = None, min_lon: float = None, max_lon: float = None, score_thresholds: float = None):
        """
        Perform base search without user interest annotation.
        This method is used internally and can be used for caching base results.
        """
        # Try to get results from cache first
        if self.redis_client:
            try:
                cache_key = self._generate_cache_key(text, city, limit, offset, extra_filter, 
                                                   startDate, endDate, min_lat, max_lat, 
                                                   min_lon, max_lon, score_thresholds)
                cached_results = self.redis_client.get(cache_key)
                if cached_results:
                    return json.loads(cached_results)
            except Exception as e:
                logging.warning(f"Cache retrieval failed: {e}")

        # If no cache hit, perform the actual search
        query_filter_final = self._build_query_filter(city, extra_filter, startDate, endDate, min_lat, max_lat, min_lon, max_lon)

        search_result = self.qdrant_client.query(
            collection_name=self.collection_name,
            query_text=text,
            query_filter=query_filter_final,
            limit=limit,
            offset=offset
        )

        results = []
        for hit in search_result:
            if score_thresholds and text != "" and hit.score < score_thresholds:
                continue
            filtered = {k: v for k, v in hit.metadata.items() if k != "document"}
            results.append(filtered)
        
        # Cache the results
        if self.redis_client:
            try:
                cache_key = self._generate_cache_key(text, city, limit, offset, extra_filter, 
                                                   startDate, endDate, min_lat, max_lat, 
                                                   min_lon, max_lon, score_thresholds)
                self.redis_client.setex(
                    cache_key,
                    self.CACHE_DURATION,
                    json.dumps(results)
                )
            except Exception as e:
                logging.warning(f"Cache storage failed: {e}")
            
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

            if startDate:
                start_timestamp = self._parse_date_to_timestamp(startDate)
                if start_timestamp:
                    date_range['gte'] = start_timestamp
            if endDate:
                end_timestamp = self._parse_date_to_timestamp(endDate)
                if end_timestamp:
                    # Add 23:59:59 to include the entire end date
                    date_range['lte'] = end_timestamp + (24 * 3600 - 1)

            if date_range:
                date_filter = models.FieldCondition(
                    key="startTime",
                    range=models.Range(**date_range)
                )

        # Bounding box geo filter - leverages Qdrant's native spatial index for efficient map-based querying
        geo_filter = None
        if all(coord is not None for coord in [min_lat, max_lat, min_lon, max_lon]):
            try:
                geo_filter = models.FieldCondition(
                    key="location",
                    geo_bounding_box=models.GeoBoundingBox(
                        top_left=models.GeoPoint(lat=max_lat, lon=min_lon),
                        bottom_right=models.GeoPoint(lat=min_lat, lon=max_lon)
                    )
                )
            except Exception as e:
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
        return final_filter

    def _parse_date_to_timestamp(self, date_str):
        """Parse date string to UTC timestamp"""
        if not date_str:
            return None
        
        try:
            # Try with time first
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            try:
                # Try date only
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                return None
        
        # Set timezone and convert to UTC timestamp
        dt = dt.replace(tzinfo=LOCAL_TIMEZONE)
        return dt.astimezone(timezone.utc).timestamp()

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