import logfire

from app.services.web.tavily_service import web_search


def web_search_node(state):
    query = state["current_query"]

    with logfire.span("web search", query=query):
        results = web_search(query)

    if not results:
        logfire.warning("no web results", query=query)
        return {
            "documents": [],
            "web_sources": [],
            "status": "No documents found",
            "plan": state["plan"] + ["Web Search: No Results"],
        }

    return {
        "documents": [f"{item['title']}\n{item['content']}" for item in results],
        "web_sources": [{"title": item["title"], "url": item["url"]} for item in results],
        "status": "Found web context",
        "plan": state["plan"] + ["Web Search Used"],
    }