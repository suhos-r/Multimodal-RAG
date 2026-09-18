"""Plan 04 acceptance: SSE shape, ownership, abstain w/o LLM, scope isolation, persistence."""
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models import ChunkRegistry, Document, Message, Session
from app.services import llm
from .conftest import TestSession

CALLS = {"n": 0}


def mock_llm(messages):
    CALLS["n"] += 1
    user = [m["content"] for m in messages if m["role"] == "user"][-1]
    assert "CONTEXT:" in user  # prompt contract holds
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


async def _seed_doc(owner_id: str, scope: str, filename: str, text: str, page: int = 4) -> str:
    async with TestSession() as s:
        doc_id = uuid.uuid4()
        s.add(Document(id=doc_id, owner_id=uuid.UUID(owner_id), scope=scope, filename=filename,
                       mime="text/plain", bytes=len(text), blob_path="t", status="ready", page_count=1))
        s.add(ChunkRegistry(doc_id=doc_id, chunk_id=f"{doc_id}:0000", parent_id=None,
                            page=page, modality="text", text=text))
        await s.commit()
        return str(doc_id)


def _sse_done(body: bytes, expect_delta: bool = True) -> dict:
    events = [json.loads(ln[6:]) for ln in body.decode().splitlines() if ln.startswith("data: ")]
    if expect_delta:
        assert any("delta" in e for e in events), "must stream deltas"
    done = next(e["done"] for e in events if "done" in e)
    return done


async def _uid(token: str) -> str:
    from app.deps import decode_sub
    return decode_sub(token)


async def test_chat_cited_answer_and_persistence():
    CALLS["n"] = 0
    async with client() as c:
        tok = await _signup(c, "chat1@x.com")
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        me = await _uid(tok["access_token"])
        await _seed_doc(me, "private", "q3.pdf",
                        "Q3 revenue grew 12 percent year over year to 4.8 billion dollars, driven by Nimbus.")
        sid = (await c.post("/api/sessions", json={}, headers=h)).json()["id"]
        r = await c.post("/api/chat", json={"session_id": sid, "query": "What was Q3 revenue growth?"}, headers=h)
        assert r.status_code == 200, r.text
        assert "text/event-stream" in r.headers["content-type"]
        done = _sse_done(r.content)
        assert "[1]" in done["answer"] and done["cached"] is False
        assert done["citations"] and done["citations"][0]["page"] == 4
        assert done["citations"][0]["filename"] == "q3.pdf"
        assert CALLS["n"] == 1
        async with TestSession() as s:
            roles = [m.role for m in (await s.execute(
                select(Message).where(Message.session_id == uuid.UUID(sid)).order_by(Message.created_at))).scalars().all()]
            assert roles == ["user", "assistant"]
            sess = await s.get(Session, uuid.UUID(sid))
            assert sess.title != "New chat"  # auto-titled


async def test_empty_retrieval_abstains_without_llm():
    CALLS["n"] = 0
    async with client() as c:
        tok = await _signup(c, "chat2@x.com")
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        sid = (await c.post("/api/sessions", json={}, headers=h)).json()["id"]
        r = await c.post("/api/chat", json={"session_id": sid, "query": "Anything at all?"}, headers=h)
        done = _sse_done(r.content, expect_delta=False)
        assert done["answer"] == "I don't know based on the knowledge base."
        assert done["citations"] == [] and CALLS["n"] == 0


async def test_scope_isolation_and_ownership():
    async with client() as c:
        a = await _signup(c, "ca@x.com")
        b = await _signup(c, "cb@x.com")
        ha = {"Authorization": f"Bearer {a['access_token']}"}
        hb = {"Authorization": f"Bearer {b['access_token']}"}
        me_a = await _uid(a["access_token"])
        await _seed_doc(me_a, "private", "secret.txt", "Zorblax protocol requires citations for every sentence here.")
        sid_b = (await c.post("/api/sessions", json={}, headers=hb)).json()["id"]
        # B cannot use A's session
        sid_a = (await c.post("/api/sessions", json={}, headers=ha)).json()["id"]
        r = await c.post("/api/chat", json={"session_id": sid_a, "query": "hi"}, headers=hb)
        assert r.status_code == 404
        # B asking about A's content -> abstain (no leak)
        CALLS["n"] = 0
        r = await c.post("/api/chat", json={"session_id": sid_b, "query": "What does Zorblax require?"}, headers=hb)
        done = _sse_done(r.content, expect_delta=False)
        assert done["answer"] == "I don't know based on the knowledge base." and CALLS["n"] == 0
