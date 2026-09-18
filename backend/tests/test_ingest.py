"""Plan 02 acceptance: upload each type -> ready, isolation, re-ingest idempotent, bad type rejected."""
import uuid

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.main import app
from app.models import ChunkRegistry, Document
from app.workers.tasks import ingest_doc_async
from .conftest import TestSession


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _signup(c: AsyncClient, email: str):
    r = await c.post("/api/auth/signup", json={"email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    return r.json()


async def _upload(c, headers, filename: str, content: bytes, mime: str):
    r = await c.post("/api/documents/upload", headers=headers,
                     files={"file": (filename, content, mime)}, data={"scope": "private"})
    assert r.status_code == 202, r.text
    return r.json()["doc_id"]


async def test_upload_txt_and_csv_ready():
    async with client() as c:
        tok = await _signup(c, "doc1@x.com")
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        d1 = await _upload(c, h, "notes.txt", b"Hello world. " * 100, "text/plain")
        assert await ingest_doc_async(d1, TestSession) == "ready"
        d2 = await _upload(c, h, "data.csv", b"a,b\n1,2\n3,4\n", "text/csv")
        assert await ingest_doc_async(d2, TestSession) == "ready"
        async with TestSession() as s:
            n = (await s.execute(select(func.count()).select_from(ChunkRegistry))).scalar_one()
            assert n >= 2
            docs = (await s.execute(select(Document))).scalars().all()
            assert all(d.status == "ready" for d in docs)


async def test_private_isolation_and_delete():
    async with client() as c:
        a = await _signup(c, "isa@x.com")
        b = await _signup(c, "isb@x.com")
        ha = {"Authorization": f"Bearer {a['access_token']}"}
        hb = {"Authorization": f"Bearer {b['access_token']}"}
        d = await _upload(c, ha, "secret.txt", b"top secret " * 50, "text/plain")
        assert await ingest_doc_async(d, TestSession) == "ready"
        r = await c.get(f"/api/documents/{d}/status", headers=hb)
        assert r.status_code == 404
        r = await c.delete(f"/api/documents/{d}", headers=hb)
        assert r.status_code == 404
        r = await c.delete(f"/api/documents/{d}", headers=ha)
        assert r.status_code == 204
        r = await c.delete(f"/api/documents/{d}", headers=ha)
        assert r.status_code == 404


async def test_reingest_idempotent():
    async with client() as c:
        tok = await _signup(c, "re@x.com")
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        d = await _upload(c, h, "rep.txt", b"repeat me. " * 200, "text/plain")
        assert await ingest_doc_async(d, TestSession) == "ready"
        async with TestSession() as s:
            n1 = (await s.execute(select(func.count()).select_from(ChunkRegistry).where(ChunkRegistry.doc_id == uuid.UUID(d)))).scalar_one()
        assert await ingest_doc_async(d, TestSession) == "ready"
        async with TestSession() as s:
            n2 = (await s.execute(select(func.count()).select_from(ChunkRegistry).where(ChunkRegistry.doc_id == uuid.UUID(d)))).scalar_one()
        assert n1 == n2 and n1 >= 1


async def test_unsupported_rejected():
    async with client() as c:
        tok = await _signup(c, "rej@x.com")
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        r = await c.post("/api/documents/upload", headers=h,
                         files={"file": ("x.exe", b"mz", "application/octet-stream")}, data={"scope": "private"})
        assert r.status_code == 415


async def test_download_roundtrip_and_isolation():
    async with client() as c:
        a = await _signup(c, "dla@x.com")
        b = await _signup(c, "dlb@x.com")
        ha = {"Authorization": f"Bearer {a['access_token']}"}
        hb = {"Authorization": f"Bearer {b['access_token']}"}
        r = await c.post("/api/documents/upload", headers=ha,
                         files={"file": ("hello.txt", b"hello download", "text/plain")}, data={"scope": "private"})
        d = r.json()["doc_id"]
        r = await c.get(f"/api/documents/{d}/download", headers=ha)
        assert r.status_code == 200 and r.content == b"hello download"
        r = await c.get(f"/api/documents/{d}/download", headers=hb)
        assert r.status_code == 404
