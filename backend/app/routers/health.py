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
    # qdrant/redis checks are best-effort stubs until Plans 02/04 wire them
    import socket
    for name, host, port in (("qdrant", "localhost", 6333), ("redis", "localhost", 6379)):
        try:
            sock = socket.create_connection((host, port), timeout=1)
            sock.close()
            deps[name] = "ok"
        except Exception:
            deps[name] = "down"
    ok = all(v == "ok" for v in deps.values())
    return {"ok": ok, "deps": deps}
