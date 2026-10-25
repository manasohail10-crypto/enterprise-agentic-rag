import logfire
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import setting

JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"
JINA_RERANK_MODEL = "jina-reranker-v3"


def log_retry(retry_state):
    logfire.warning("jina rerank failed, retrying", attempt=retry_state.attempt_number)


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=20),
    reraise=True,
    before_sleep=log_retry,
)
def call_jina(query, documents, top_n):
    response = requests.post(
        JINA_RERANK_URL,
        headers={"Authorization": f"Bearer {setting.JINA_API_KEY}"},
        json={
            "model": JINA_RERANK_MODEL,
            "query": query,
            "documents": documents,
            "top_n": top_n,
            "return_documents": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["results"]


def rerank_with_scores(query, documents, top_n=5):
    if not documents:
        return []

    if not setting.JINA_API_KEY:
        logfire.warning("JINA_API_KEY not set, skipping reranking")
        return [{"text": text, "score": None, "index": i} for i, text in enumerate(documents[:top_n])]

    try:
        with logfire.span("jina rerank", count=len(documents)):
            results = call_jina(query, documents, top_n)
    except Exception:
        logfire.exception("reranking failed, using the original order")
        return [{"text": text, "score": None, "index": i} for i, text in enumerate(documents[:top_n])]

    ranked = [
        {"text": documents[item["index"]], "score": float(item["relevance_score"]), "index": item["index"]}
        for item in results[:top_n]
    ]
    logfire.info("rerank scores", scores=[round(item["score"], 3) for item in ranked])
    return ranked


def rerank_documents(query, documents, top_n=5):
    return [item["text"] for item in rerank_with_scores(query, documents, top_n)]