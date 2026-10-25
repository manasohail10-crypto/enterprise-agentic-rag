import time

import logfire
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.services.health.connection_checker import check_all_connections

CACHE_SECONDS = 60

router = APIRouter(tags=["health"])
cache = {"time": 0.0, "results": None}


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/ready")
def ready():
    now = time.monotonic()
    if cache["results"] is None or now - cache["time"] > CACHE_SECONDS:
        cache["results"] = check_all_connections()
        cache["time"] = now

    results = cache["results"]
    checks = {name: result.to_dict()["status"] for name, result in results.items()}
    healthy = all(result.healthy for result in results.values())

    if not healthy:
        logfire.warning("readiness check failed", checks=checks)

    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "not_ready", "checks": checks},
    )