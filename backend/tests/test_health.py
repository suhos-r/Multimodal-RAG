"""Health semantics: ok gates on db+qdrant; redis is informational (nothing requires it)."""
from httpx import ASGITransport, AsyncClient

from app.main import app


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_health_gating_rule():
    async with client() as c:
        r = await c.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert set(body) == {"ok", "deps"}
        assert set(body["deps"]) == {"db", "qdrant", "redis"}
        # the rule itself, in any environment (CI sqlite has no qdrant/redis up):
        assert body["ok"] == (body["deps"]["db"] == "ok" and body["deps"]["qdrant"] == "ok")
        # redis must NEVER gate ok: ok may be true while redis is down
        if body["deps"]["redis"] == "down" and body["deps"]["db"] == "ok" and body["deps"]["qdrant"] == "ok":
            assert body["ok"] is True
