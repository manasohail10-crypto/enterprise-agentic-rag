import logfire
from qdrant_client import QdrantClient
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import setting
from app.services.retrieval.embedding import embed_query

client = QdrantClient(url=setting.QDRANT_CLUSTER_ENDPOINT, api_key=setting.QDRANT_API_KEY)


def log_retry(retry_state):
    logfire.warning("qdrant search failed, retrying", attempt=retry_state.attempt_number)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
    before_sleep=log_retry,
)
def query_qdrant(vector, limit):
    response = client.query_points(
        collection_name=setting.QDRANT_COLLECTION,
        query=vector,
        limit=limit,
        with_payload=True,
    )
    return [
        {
            "content": point.payload.get("text", ""),
            "source": point.payload.get("source", "unknown"),
            "domain": point.payload.get("domain", "general"),
            "score": point.score,
        }
        for point in response.points
    ]


def search_enterprise_knowledge(query, limit=8):
    try:
        vector = embed_query(query)
        return query_qdrant(vector, limit)
    except Exception:
        logfire.exception("qdrant search failed")
        return []