"""Plan 07 acceptance: feedback ownership, upsert, dashboard movement."""
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models import ChunkRegistry, Document, Message, Session
from app.services import llm
from .conftest import TestSession


def mock_llm(messages):
    return ["Revenue grew 12 percent to 4.8 billion dollars [1]."]


@pytest.fixture(autouse=True)
def _mocks():
    from app.services import cache as qcache
    qcache.clear_memory()
    llm.set_mock(mock_llm)
    yield
    llm.set_mock(mock_llm)


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _signup(c: AsyncClient, email: str):
    r = await c.post("/api/auth/signup", json={"email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    return r.json()


async def _chat_answer_id(c, h, sid) -> str:
    import json as _json
    r = await c.post("/api/chat", json={"session_id": sid, "query": "What was Q3 revenue growth?"}, headers=h)
    assert r.status_code == 200, r.text
    assert _json.loads([ln for ln in r.content.decode().splitlines() if ln.startswith("data: ")][-1][6:])["done"]
    async with TestSession() as s:
        msgs = (await s.execute(select(Message).where(Message.session_id == uuid.UUID(sid)))).scalars().all()
        return str(next(m.id for m in msgs if m.role == "assistant"))


async def test_feedback_submit_get_upsert():
    async with client() as c:
        tok = await _signup(c, "fb1@x.com")
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        from app.deps import decode_sub
        me = decode_sub(tok["access_token"])
        sid = (await c.post("/api/sessions", json={}, headers=h)).json()["id"]
        async with TestSession() as s:
            doc_id = uuid.uuid4()
            s.add(Document(id=doc_id, owner_id=uuid.UUID(me), scope="private", filename="q3.pdf",
                           mime="text/plain", bytes=10, blob_path="t", status="ready", page_count=1))
            s.add(ChunkRegistry(doc_id=doc_id, chunk_id=f"{doc_id}:0000", parent_id=None, page=4,
                                modality="text",
                                text="Q3 revenue grew 12 percent year over year to 4.8 billion dollars."))
            await s.commit()
        mid = await _chat_answer_id(c, h, sid)
        r = await c.post("/api/feedback", json={"message_id": mid, "rating": -1, "comment": "too short",
                                                "corrected_answer": "Revenue grew 12% to $4.8B [1]."}, headers=h)
        assert r.status_code == 201
        first_id = r.json()["id"]
        r = await c.get("/api/feedback", params={"message_id": mid}, headers=h)
        assert r.json()["rating"] == -1 and r.json()["comment"] == "too short"
        # upsert same row
        r = await c.post("/api/feedback", json={"message_id": mid, "rating": 1}, headers=h)
        assert r.json()["id"] == first_id
        # dashboard moved
        stats = (await c.get("/api/admin/stats", headers=h)).json()
        assert stats["helpfulness_pct"] == 100.0 and stats["feedback_up"] == 1


async def test_feedback_isolation_and_validation():
    async with client() as c:
        a = await _signup(c, "fa@x.com")
        b = await _signup(c, "fbb@x.com")
        ha = {"Authorization": f"Bearer {a['access_token']}"}
        hb = {"Authorization": f"Bearer {b['access_token']}"}
        from app.deps import decode_sub
        me_a = decode_sub(a["access_token"])
        sid = (await c.post("/api/sessions", json={}, headers=ha)).json()["id"]
        async with TestSession() as s:
            doc_id = uuid.uuid4()
            s.add(Document(id=doc_id, owner_id=uuid.UUID(me_a), scope="private", filename="q3.pdf",
                           mime="text/plain", bytes=10, blob_path="t", status="ready", page_count=1))
            s.add(ChunkRegistry(doc_id=doc_id, chunk_id=f"{doc_id}:0000", parent_id=None, page=4,
                                modality="text",
                                text="Q3 revenue grew 12 percent year over year to 4.8 billion dollars."))
            await s.commit()
        mid = await _chat_answer_id(c, ha, sid)
        r = await c.post("/api/feedback", json={"message_id": mid, "rating": -1}, headers=hb)
        assert r.status_code == 404  # B cannot rate A's message
        r = await c.post("/api/feedback", json={"message_id": mid, "rating": 0}, headers=ha)
        assert r.status_code in (400, 422)
        r = await c.post("/api/feedback", json={"message_id": str(uuid.uuid4()), "rating": 1}, headers=ha)
        assert r.status_code == 404


async def test_rollup_counts_and_candidates():
    import importlib.util
    from pathlib import Path as _Path
    spec = importlib.util.spec_from_file_location(
        "rollup_feedback", str(_Path(__file__).parent.parent.parent / "scripts" / "rollup_feedback.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    async with client() as c:
        tok = await _signup(c, "fb2@x.com")
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        from app.deps import decode_sub
        me = decode_sub(tok["access_token"])
        sid = (await c.post("/api/sessions", json={}, headers=h)).json()["id"]
        async with TestSession() as s:
            doc_id = uuid.uuid4()
            s.add(Document(id=doc_id, owner_id=uuid.UUID(me), scope="private", filename="q3.pdf",
                           mime="text/plain", bytes=10, blob_path="t", status="ready", page_count=1))
            s.add(ChunkRegistry(doc_id=doc_id, chunk_id=f"{doc_id}:0000", parent_id=None, page=4,
                                modality="text",
                                text="Q3 revenue grew 12 percent year over year to 4.8 billion dollars."))
            await s.commit()
        mid = await _chat_answer_id(c, h, sid)
        await c.post("/api/feedback", json={"message_id": mid, "rating": -1,
                                            "corrected_answer": "fixed answer"}, headers=h)
        stats = await mod.rollup(TestSession)
        assert stats["total"] == 1 and stats["down"] == 1
        assert stats["helpfulness_pct"] == 0.0
        assert stats["corrected_count"] == 1 and stats["candidates"][0]["message_id"] == mid
        assert stats["failing_doc_ids"] == [str(doc_id)]
