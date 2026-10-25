import sys
from concurrent.futures import ThreadPoolExecutor

import logfire
import requests
from qdrant_client import QdrantClient

from app.config import setting
from app.gateway.client import portkey_client

JINA_EMBED_URL = "https://api.jina.ai/v1/embeddings"
JINA_RERANK_URL = "https://api.jina.ai/v1/rerank"


class ConnectionResult:
    def __init__(self, name, healthy, message=""):
        self.name = name
        self.healthy = healthy
        self.message = message

    def to_dict(self):
        status = "ok" if self.healthy else "unavailable"
        if self.message:
            status = f"{status}: {self.message}"
        return {"status": status, "healthy": self.healthy, "message": self.message}


def run_check(name, check):
    try:
        return ConnectionResult(name, True, check())
    except Exception as error:
        logfire.warning("health check failed", service=name, error=str(error))
        return ConnectionResult(name, False, str(error))


def check_postgres():
    if not setting.POSTGRES_URI:
        return "not configured, chat memory is in-memory only"
    import psycopg

    with psycopg.connect(setting.POSTGRES_URI, connect_timeout=5) as connection:
        connection.execute("SELECT 1")
    return "reachable"


def check_qdrant():
    client = QdrantClient(url=setting.QDRANT_CLUSTER_ENDPOINT, api_key=setting.QDRANT_API_KEY, timeout=5)
    if not client.collection_exists(setting.QDRANT_COLLECTION):
        raise RuntimeError(f"collection '{setting.QDRANT_COLLECTION}' not found, run ingestion")
    return "reachable"


def check_llm_gateway():
    response = portkey_client.chat.completions.create(
        model=setting.GROQ_MODEL,
        messages=[{"role": "user", "content": "Say hello in one word."}],
        max_completion_tokens=100,
        timeout=10,
    )
    if not response.choices:
        raise RuntimeError("empty response")
    return "reachable"


def call_jina(url, body):
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {setting.JINA_API_KEY}"},
        json=body,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def check_jina_embeddings():
    if not setting.JINA_API_KEY:
        return "not configured, using the local model"
    body = {"model": "jina-embeddings-v3", "task": "retrieval.query", "normalized": True, "input": ["probe"]}
    if not call_jina(JINA_EMBED_URL, body).get("data"):
        raise RuntimeError("empty embedding data")
    return "reachable"


def check_jina_reranker():
    if not setting.JINA_API_KEY:
        return "not configured, reranking is skipped"
    body = {
        "model": "jina-reranker-v3",
        "query": "health check",
        "documents": ["document one", "document two"],
        "top_n": 2,
        "return_documents": False,
    }
    if "results" not in call_jina(JINA_RERANK_URL, body):
        raise RuntimeError("missing results")
    return "reachable"


def check_logfire():
    if not setting.LOGFIRE_TOKEN:
        return "token not set, spans are not sent"
    return "token set"


CHECKS = {
    "postgres": check_postgres,
    "qdrant": check_qdrant,
    "llm_gateway": check_llm_gateway,
    "jina_embeddings": check_jina_embeddings,
    "jina_reranker": check_jina_reranker,
    "logfire": check_logfire,
}


def check_all_connections():
    with ThreadPoolExecutor() as pool:
        futures = {name: pool.submit(run_check, name, check) for name, check in CHECKS.items()}
        return {name: future.result() for name, future in futures.items()}


def log_connection_summary(results):
    for name, result in results.items():
        if result.healthy:
            logfire.info("service healthy", service=name, message=result.message)
        else:
            logfire.warning("service unavailable", service=name, message=result.message)
    return all(result.healthy for result in results.values())


def print_report(results):
    print("\nConnection report")
    print("=" * 60)
    for name, result in results.items():
        print(f"{'OK' if result.healthy else 'FAIL':5}{name:18}{result.message}")
    print("=" * 60)
    healthy = all(result.healthy for result in results.values())
    print("All connections healthy." if healthy else "One or more connections failed.")
    return 0 if healthy else 1


if __name__ == "__main__":
    logfire.configure(token=setting.LOGFIRE_TOKEN, send_to_logfire="if-token-present")
    sys.exit(print_report(check_all_connections()))