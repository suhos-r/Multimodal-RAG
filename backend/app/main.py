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
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    request.state.trace_id = trace_id
    try:
        response = await call_next(request)
    except Exception:
        return JSONResponse(status_code=500, content={"detail": "internal error", "code": "internal", "trace_id": trace_id})
    response.headers["X-Trace-ID"] = trace_id
    return response


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
