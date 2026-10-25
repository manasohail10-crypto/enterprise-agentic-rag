import secrets
import time
from contextlib import asynccontextmanager

import logfire
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import main as pipeline
from app.config import setting
from app.health import router as health_router
from app.request_context import get_request_id

REQUESTS = Counter("rag_requests_total", "Total /query requests", ["status"])
DURATION = Histogram("rag_request_duration_seconds", "Latency of /query requests in seconds")
GUARD_BLOCKS = Counter("guardrails_blocks_total", "Requests blocked or allowed by guardrails", ["blocked"])

bearer = HTTPBearer(auto_error=False)
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app):
    pipeline.start(strict=setting.STRICT_STARTUP)
    if not setting.API_KEY:
        logfire.warning("API_KEY is not set, /query is open to anyone")
    yield


app = FastAPI(title="Enterprise Agentic RAG API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(health_router)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


class QueryRequest(BaseModel):
    q: str
    thread_id: str | None = None


def verify_api_key(credentials=Depends(bearer)):
    if not setting.API_KEY:
        return
    if credentials is None or not secrets.compare_digest(credentials.credentials, setting.API_KEY):
        logfire.warning("rejected request: invalid or missing API key")
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/")
def home():
    return {"message": "Enterprise RAG API is running"}


@app.get("/graph", dependencies=[Depends(verify_api_key)])
def graph_image():
    try:
        png = pipeline.agent.get_graph().draw_mermaid_png()
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"could not draw the graph: {error}")
    return Response(content=png, media_type="image/png")


@app.post("/query", dependencies=[Depends(verify_api_key)])
@limiter.limit(f"{setting.RATE_LIMIT_PER_MINUTE}/minute")
def query(request: Request, body: QueryRequest):
    start = time.perf_counter()

    try:
        result = pipeline.ask(body.q, body.thread_id)
    except Exception:
        REQUESTS.labels(status="error").inc()
        DURATION.observe(time.perf_counter() - start)
        logfire.exception("query failed")
        return JSONResponse(
            status_code=500,
            content={
                "request_id": get_request_id(),
                "status": "error",
                "message": "Failed to process request. Please try again later.",
            },
        )

    GUARD_BLOCKS.labels(blocked=str(result["blocked"]).lower()).inc()
    REQUESTS.labels(status="blocked" if result["blocked"] else "success").inc()
    DURATION.observe(time.perf_counter() - start)
    return result