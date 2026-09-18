"""Plan 05 acceptance: exact/semantic hits skip LLM, filters gate hits, delete invalidates."""
import json
import time
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models import ChunkRegistry, Document
from app.services import cache as qcache
from app.services import embed, llm
from .conftest import TestSession

CALLS = {"n": 0}


def mock_llm(messages):
    CALLS["n"] += 1
    return ["Revenue grew 12 percent to 4.8 billion dollars [1]."]


def mock_embed(texts):
    out = []
    for t in texts:
        if "revenue" in t.lower():
            out.append([1.0] + [0.0] * 767)
        else:
            out.append([0.0, 1.0] + [0.0] * 766)
    return out


@pytest.fixture(autouse=True)
def _mocks():
    CALLS["n"] = 0
    qcache.clear_memory()
    llm.set_mock(mock_llm)
    embed.set_mock(mock_embed)
    yield
    llm.set_mock(mock_llm)
    embed.set_mock(mock_embed)


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _signup(c: AsyncClient, email: str):
    r = await c.post("/api/auth/signup", json={"email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    return r.json()


async def _seed_doc(owner_id: str, text: str) -> str:
    async with TestSession() as s:
        doc_id = uuid.uuid4()
        s.add(Document(id=doc_id, owner_id=uuid.UUID(owner_id), scope="private", filename="q3.pdf",
                       mime="text/plain", bytes=len(text), blob_path="t", status="ready", page_count=1))
        s.add(ChunkRegistry(doc_id=doc_id, chunk_id=f"{doc_id}:0000", parent_id=None,
                            page=4, modality="text", text=text))
        await s.commit()
        return str(doc_id)


def _done(body: bytes) -> dict:
    events = [json.loads(ln[6:]) for ln in body.decode().splitlines() if ln.startswith("data: ")]
    return next(e["done"] for e in events if "done" in e)


async def _ask(c, h, sid, query, **kw):
    t0 = time.perf_counter()
    r = await c.post("/api/chat", json={"session_id": sid, "query": query, **kw}, headers=h)
    assert r.status_code == 200, r.text
    return _done(r.content), (time.perf_counter() - t0) * 1000


async def _setup():
    c = client()
    tok = await _signup(c, "cache@x.com")
    h = {"Authorization": f"Bearer {tok['access_token']}"}
    from app.deps import decode_sub
    me = decode_sub(tok["access_token"])
    doc_id = await _seed_doc(me, "Q3 revenue grew 12 percent year over year to 4.8 billion dollars, driven by Nimbus.")
    sid = (await c.post("/api/sessions", json={}, headers=h)).json()["id"]
    return c, h, sid, doc_id


async def test_exact_repeat_skips_llm():
    c, h, sid, _ = await _setup()
    d1, _ = await _ask(c, h, sid, "What was Q3 revenue?")
    assert d1["cached"] is False and CALLS["n"] == 1
    d2, ms = await _ask(c, h, sid, "What was Q3 revenue?")
    assert d2["cached"] is True and d2["tier"] == "exact"
    assert d2["answer"] == d1["answer"] and CALLS["n"] == 1
    assert ms < 2000


async def test_semantic_paraphrase_hits():
    c, h, sid, _ = await _setup()
    await _ask(c, h, sid, "What was Q3 revenue?")
    d2, _ = await _ask(c, h, sid, "What was the Q3 revenue figure?")
    assert d2["cached"] is True and d2["tier"] == "semantic" and CALLS["n"] == 1


async def test_different_filters_miss_and_fresh_bypasses():
    c, h, sid, doc_id = await _setup()
    await _ask(c, h, sid, "What was Q3 revenue?")
    d, _ = await _ask(c, h, sid, "What was Q3 revenue?", doc_ids=["00000000-0000-0000-0000-000000000000"])
    assert d["cached"] is False  # unknown doc -> empty retrieval -> abstain, still a miss
    d, _ = await _ask(c, h, sid, "What was Q3 revenue?", fresh=True)
    assert d["cached"] is False and CALLS["n"] >= 2


async def test_delete_invalidates_cache():
    c, h, sid, doc_id = await _setup()
    await _ask(c, h, sid, "What was Q3 revenue?")
    d, _ = await _ask(c, h, sid, "What was Q3 revenue?")
    assert d["cached"] is True
    r = await c.delete(f"/api/documents/{doc_id}", headers=h)
    assert r.status_code == 204
    d, _ = await _ask(c, h, sid, "What was Q3 revenue?")
    assert d["cached"] is False  # invalidated -> miss (doc gone -> abstain)


async def test_admin_stats_reflect_hits():
    c, h, sid, _ = await _setup()
    await _ask(c, h, sid, "What was Q3 revenue?")
    await _ask(c, h, sid, "What was Q3 revenue?")
    r = await c.get("/api/admin/stats", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["exact_hits"] >= 1 and body["llm_calls_avoided"] >= 1
    assert body["cache_hit_rate_24h"] > 0
