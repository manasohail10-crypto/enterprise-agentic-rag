import logfire
from tavily import TavilyClient
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import setting

MAX_CHARS = 1500

client = None


def log_retry(retry_state):
    logfire.warning("tavily search failed, retrying", attempt=retry_state.attempt_number)


def get_client():
    global client
    if client is None:
        client = TavilyClient(api_key=setting.TAVILY_API_KEY)
    return client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
    before_sleep=log_retry,
)
def call_tavily(query, max_results):
    return get_client().search(
        query=query,
        max_results=max_results,
        search_depth="basic",
        include_answer=False,
        timeout=20,
    )


def web_search(query):
    if not setting.WEB_SEARCH_ENABLED or not setting.TAVILY_API_KEY:
        logfire.info("web search is off or has no key")
        return []

    try:
        with logfire.span("tavily search", query=query):
            response = call_tavily(query, setting.TAVILY_MAX_RESULTS)
    except Exception:
        logfire.exception("web search failed")
        return []

    results = []
    for item in response.get("results", []):
        content = (item.get("content") or "").strip()
        if not content or not item.get("url"):
            continue
        results.append(
            {
                "title": item.get("title") or item["url"],
                "url": item["url"],
                "content": content[:MAX_CHARS],
            }
        )

    logfire.info("web results", count=len(results))
    return results