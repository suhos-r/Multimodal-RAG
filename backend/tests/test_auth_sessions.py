"""Plan 01 acceptance tests: auth + per-user session isolation."""
from httpx import ASGITransport, AsyncClient

from app.main import app


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def signup(c: AsyncClient, email: str, pw: str = "password123"):
    r = await c.post("/api/auth/signup", json={"email": email, "password": pw})
    assert r.status_code == 201, r.text
    return r.json()


async def test_auth_happy_and_refresh():
    async with client() as c:
        tok = await signup(c, "a@x.com")
        assert tok["access_token"] and tok["refresh_token"]
        r = await c.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"})
        assert r.status_code == 200
        r = await c.post("/api/auth/refresh", json={"refresh_token": tok["refresh_token"]})
        assert r.status_code == 200


async def test_duplicate_and_bad_password():
    async with client() as c:
        await signup(c, "b@x.com")
        r = await c.post("/api/auth/signup", json={"email": "b@x.com", "password": "password123"})
        assert r.status_code == 409
        r = await c.post("/api/auth/login", json={"email": "b@x.com", "password": "wrongpass1"})
        assert r.status_code == 401


async def test_session_isolation_and_crud():
    async with client() as c:
        a = await signup(c, "ua@x.com")
        b = await signup(c, "ub@x.com")
        ha, hb = {"Authorization": f"Bearer {a['access_token']}"}, {"Authorization": f"Bearer {b['access_token']}"}
        s1 = (await c.post("/api/sessions", json={}, headers=ha)).json()
        s2 = (await c.post("/api/sessions", json={"title": "Second"}, headers=ha)).json()
        lst_b = (await c.get("/api/sessions", headers=hb)).json()
        assert lst_b == []
        # B cannot read A's session
        r = await c.get(f"/api/sessions/{s1['id']}/messages", headers=hb)
        assert r.status_code == 404
        # A rename + delete
        r = await c.patch(f"/api/sessions/{s1['id']}", json={"title": "Renamed"}, headers=ha)
        assert r.json()["title"] == "Renamed"
        r = await c.delete(f"/api/sessions/{s2['id']}", headers=ha)
        assert r.status_code == 204
        lst_a = (await c.get("/api/sessions", headers=ha)).json()
        assert len(lst_a) == 1 and lst_a[0]["title"] == "Renamed"


async def test_unauthorized_rejected():
    async with client() as c:
        r = await c.get("/api/sessions")
        assert r.status_code in (401, 403)
