"""Plan 06 acceptance: grade/rewrite/critique/reflect loop with traces."""
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models import ChunkRegistry, Document, Message
from app.services import agent as rag_agent
from app.services import llm
from .conftest import TestSession

CALLS = {"n": 0}
STATE = {"grades": [], "critics": [], "drafts": []}
Q3 = "Q3 revenue grew 12 percent year over year to 4.8 billion dollars, driven by Nimbus."


def mock_llm(messages):
    CALLS["n"] += 1
    system = messages[0]["content"]
    if "Score each SOURCE" in system:
        return [json.dumps(STATE["grades"])]
    if "alternative" in system:
        return ['["kestrel cost keywords", "kestrel overview"]']
    if "Judge the DRAFT" in system:
        return [json.dumps(STATE["critics"].pop(0))]
    return [STATE["drafts"].pop(0)]


@pytest.fixture(autouse=True)
def _mocks():
    from app.services import cache as qcache
    qcache.clear_memory()
    CALLS["n"] = 0
    STATE.update({"grades": [{"id": 1, "score": 0.9, "reason": "topical"}],
                  "critics": [{"faithful": 5, "complete": 5, "cited": True, "issues": []}],
                  "drafts": ["Revenue grew 12 percent to 4.8 billion dollars [1]."]})
    llm.set_mock(mock_llm)
    yield
    llm.set_mock(mock_llm)


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _signup(c: AsyncClient, email: str):
    r = await c.post("/api/auth/signup", json={"email": email, "password": "password123"})
    assert r.status_code == 201, r.text
    return r.json()


async def _seed(owner_id: str, text: str = Q3) -> None:
    async with TestSession() as s:
        doc_id = uuid.uuid4()
        s.add(Document(id=doc_id, owner_id=uuid.UUID(owner_id), scope="private", filename="q3.pdf",
                       mime="text/plain", bytes=len(text), blob_path="t", status="ready", page_count=1))
        s.add(ChunkRegistry(doc_id=doc_id, chunk_id=f"{doc_id}:0000", parent_id=None,
                            page=4, modality="text", text=text))
        await s.commit()


async def _run(query: str, user_id: str):
    async with TestSession() as db:
        return await rag_agent.run_agent(db, query, user_id, "both", None, 8, [])


async def test_happy_path_single_pass():
    async with client() as c:
        me = (await _signup(c, "ag1@x.com"))
        from app.deps import decode_sub
        uid = decode_sub(me["access_token"])
        await _seed(uid)
        res = await _run("What was Q3 revenue growth?", uid)
        assert "[1]" in res["answer"] and res["citations"]
        nodes = [t["node"] for t in res["trace"]]
        assert nodes == ["RETRIEVE", "GRADE_DOCS", "GENERATE", "CRITIQUE"]
        assert res["llm_calls"] == 3 and CALLS["n"] == 3


async def test_rewrite_then_abstain_on_irrelevant():
    STATE["grades"] = [{"id": 1, "score": 0.1, "reason": "off-topic"}]
    async with client() as c:
        me = await _signup(c, "ag2@x.com")
        from app.deps import decode_sub
        uid = decode_sub(me["access_token"])
        await _seed(uid, "The cafeteria menu rotates weekly between Italian and Thai food.")
        res = await _run("What was Q3 revenue growth?", uid)
        nodes = [t["node"] for t in res["trace"]]
        assert "REWRITE_QUERY" in nodes
        assert res["answer"] == "I don't know based on the knowledge base."


async def test_empty_retrieval_no_llm():
    async with client() as c:
        me = await _signup(c, "ag3@x.com")
        from app.deps import decode_sub
        uid = decode_sub(me["access_token"])
        res = await _run("Anything?", uid)
        assert res["answer"] == "I don't know based on the knowledge base."
        assert res["llm_calls"] == 0 and CALLS["n"] == 0


async def test_critique_failure_regenerates():
    STATE["critics"] = [{"faithful": 2, "complete": 5, "cited": False, "issues": ["no citation marker"]},
                        {"faithful": 5, "complete": 5, "cited": True, "issues": []}]
    STATE["drafts"] = ["Revenue grew a lot, trust me.",
                       "Revenue grew 12 percent to 4.8 billion dollars [1]."]
    async with client() as c:
        me = await _signup(c, "ag4@x.com")
        from app.deps import decode_sub
        uid = decode_sub(me["access_token"])
        await _seed(uid)
        res = await _run("What was Q3 revenue growth?", uid)
        nodes = [t["node"] for t in res["trace"]]
        assert nodes.count("GENERATE") == 2 and "REFLECT" in nodes
        assert "[1]" in res["answer"]


async def test_agent_mode_via_chat_streams_nodes_and_trace():
    async with client() as c:
        tok = await _signup(c, "ag5@x.com")
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        from app.deps import decode_sub
        await _seed(decode_sub(tok["access_token"]))
        sid = (await c.post("/api/sessions", json={}, headers=h)).json()["id"]
        r = await c.post("/api/chat", json={"session_id": sid, "query": "What was Q3 revenue?", "mode": "agent"}, headers=h)
        assert r.status_code == 200, r.text
        events = [json.loads(ln[6:]) for ln in r.content.decode().splitlines() if ln.startswith("data: ")]
        assert any("node" in e for e in events)
        done = next(e["done"] for e in events if "done" in e)
        assert done["mode"] == "agent" and "[1]" in done["answer"]
        async with TestSession() as s:
            msgs = (await s.execute(select(Message).where(Message.session_id == uuid.UUID(sid)))).scalars().all()
            assistant = next(m for m in msgs if m.role == "assistant")
            assert assistant.agent_trace and any(t["node"] == "CRITIQUE" for t in assistant.agent_trace)
