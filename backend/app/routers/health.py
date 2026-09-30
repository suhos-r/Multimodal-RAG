from fastapi import APIRouter
from sqlalchemy import text

from ..db import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    deps: dict[str, str] = {}
    try:
        async with SessionLocal() as s:
            await s.execute(text("SELECT 1"))
        deps["db"] = "ok"
    except Exception as e:
        deps["db"] = f"down: {e.__class__.__name__}"
    # redis is informational only: nothing at runtime requires it (cache is
    # Postgres+memory, the celery worker is optional). ok gates on db+qdrant.
    import socket
    for name, host, port in (("qdrant", "localhost", 6333), ("redis", "localhost", 6379)):
        try:
            sock = socket.create_connection((host, port), timeout=1)
            sock.close()
            deps[name] = "ok"
        except Exception:
            deps[name] = "down"
    ok = deps.get("db") == "ok" and deps.get("qdrant") == "ok"
    return {"ok": ok, "deps": deps}
