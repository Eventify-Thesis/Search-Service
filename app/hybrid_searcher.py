import psycopg2
import os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

load_dotenv()

class HybridSearcher:
    DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    SPARSE_MODEL = "prithivida/Splade_PP_en_v1"

    def __init__(self, collection_name):
        self.collection_name = collection_name
        self.qdrant_client = QdrantClient(os.getenv("QDRANT_URL"), api_key=os.getenv("QDRANT_API_KEY"))
        self.qdrant_client.set_model(self.DENSE_MODEL)
        self.qdrant_client.set_sparse_model(self.SPARSE_MODEL)

    def search(self, text: str, city: str = None, limit: int = 15, user_id: str = None):
        query_filter = None
        if city:
            query_filter = models.Filter(
                must=[models.FieldCondition(key="city", match=models.MatchValue(value=city))]
            )

        search_result = self.qdrant_client.query(
            collection_name=self.collection_name,
            query_text=text,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,          # Keep metadata
            with_vectors=False,         # No need to return vectors
            payload_selector=models.PayloadSelectorExclude(
                fields=["document"]     # This hides the "document" field
            )
        )

        results = [
            {k: v for k, v in hit.payload.items() if k != "document"}
            for hit in search_result
        ]

        if user_id:
            # Connect to DB and get bookmarked event_ids
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

            for item in results:
                item["bookmarked"] = item["id"] in bookmarked_ids
        else:
            for item in results:
                item["bookmarked"] = False

        return results
