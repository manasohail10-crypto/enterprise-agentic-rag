import logfire

from app.config import setting
from app.services.retrieval.qdrant_service import search_enterprise_knowledge
from app.services.retrieval.ranking_service import rerank_with_scores

SEARCH_LIMIT = 30
TOP_N = 5


def no_context(state, reason):
    logfire.warning(reason, query=state["current_query"])
    return {
        "documents": [],
        "doc_sources": [],
        "web_sources": [],
        "status": "No documents found",
        "plan": state["plan"] + ["No Context Found"],
    }


def retrieve_node(state):
    query = state["current_query"]

    with logfire.span("knowledge retrieval", query=query):
        results = search_enterprise_knowledge(query, limit=SEARCH_LIMIT)
        logfire.info("candidates retrieved", count=len(results))

        if not results:
            return no_context(state, "no documents found")

        texts = [result["content"] for result in results]
        with logfire.span("reranking"):
            ranked = rerank_with_scores(query, texts, top_n=TOP_N)

        good = [item for item in ranked if item["score"] is None or item["score"] >= setting.RERANK_MIN_SCORE]
        scores = [item["score"] for item in ranked if item["score"] is not None]
        logfire.info("passages kept", kept=len(good), best_score=max(scores) if scores else None)

        if not good:
            return no_context(state, "no passage was good enough")

    doc_sources = [
        {
            "source": results[item["index"]]["source"],
            "domain": results[item["index"]].get("domain", "general"),
        }
        for item in good
    ]

    return {
        "documents": [item["text"] for item in good],
        "doc_sources": doc_sources,
        "web_sources": [],
        "status": "Found technical context",
        "plan": state["plan"] + ["Context Retrieved"],
    }