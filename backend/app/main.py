import time
import uuid
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .routers.auth import router as auth_router
from .routers.sessions import router as sessions_router
from .routers.health import router as health_router
from .routers.documents import router as documents_router
from .routers.chat import router as chat_router
from .routers.admin import router as admin_router
from .routers.feedback import router as feedback_router

app = FastAPI(title="RAG API", version="0.1.0")


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    from .services.pii import redact
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    request.state.trace_id = trace_id
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "internal error", "code": "internal", "trace_id": trace_id})
    ms = (time.perf_counter() - t0) * 1000
    response.headers["X-Trace-ID"] = trace_id
    # access log: route + timing only, query string redacted (no bodies, no tokens)
    qs = redact(request.url.query)
    print(f"[http] {request.method} {request.url.path}?{qs} -> {response.status_code} {ms:.1f}ms trace={trace_id}",
          flush=True)
    METRICS["requests"] += 1
    METRICS["latency_ms"] += ms
    METRICS["by_route"][request.url.path] = METRICS["by_route"].get(request.url.path, 0) + 1
    return response


METRICS: dict = {"requests": 0, "latency_ms": 0.0, "by_route": {}}


@app.get("/metrics")
async def metrics():
    from .services.cache import STATS
    avg = METRICS["latency_ms"] / METRICS["requests"] if METRICS["requests"] else 0.0
    return {"http_requests": METRICS["requests"], "http_avg_latency_ms": round(avg, 1),
            "by_route": METRICS["by_route"], "cache": STATS,
            "llm": f"{settings.LLM_PROVIDER}/{settings.LLM_MODEL}"}


app.include_router(auth_router)
app.include_router(sessions_router)
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(admin_router)
app.include_router(feedback_router)


@app.get("/")
async def root():
    return {"ok": True, "llm": f"{settings.LLM_PROVIDER}/{settings.LLM_MODEL}"}
