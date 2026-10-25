from functools import lru_cache

import logfire
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from sentence_transformers import SentenceTransformer

from app.config import setting

JINA_URL = "https://api.jina.ai/v1/embeddings"
JINA_MODEL = "jina-embeddings-v3"
FALLBACK_MODEL = "mixedbread-ai/mxbai-embed-large-v1"
EMBEDDING_DIM = 1024
BATCH_SIZE = 32


def get_embedding_dim():
    return EMBEDDING_DIM


@lru_cache
def load_fallback_model():
    return SentenceTransformer(FALLBACK_MODEL)


@retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=2, min=2, max=60), reraise=True)
def embed_jina_batch(texts, task):
    response = requests.post(
        JINA_URL,
        headers={"Authorization": f"Bearer {setting.JINA_API_KEY}"},
        json={"model": JINA_MODEL, "task": task, "normalized": True, "input": texts},
        timeout=60,
    )
    response.raise_for_status()
    data = sorted(response.json()["data"], key=lambda item: item["index"])
    return [item["embedding"] for item in data]


def embed(texts, is_query):
    if not texts:
        return []

    if setting.JINA_API_KEY:
        task = "retrieval.query" if is_query else "retrieval.passage"
        vectors = []
        for i in range(0, len(texts), BATCH_SIZE):
            with logfire.span("jina embedding batch", start=i):
                vectors += embed_jina_batch(texts[i : i + BATCH_SIZE], task)
        return vectors

    model = load_fallback_model()
    encode = model.encode_query if is_query else model.encode_document
    return encode(texts, batch_size=BATCH_SIZE, show_progress_bar=False).tolist()


def embed_query(query):
    return embed([query], is_query=True)[0]


def embed_texts(texts):
    return embed(texts, is_query=False)