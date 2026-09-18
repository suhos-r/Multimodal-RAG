import json
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_db
from ..deps import check_rate, get_current_user
from ..models import Message, Session
from ..services import cache as qcache
from ..services import citations as cit
from ..services import llm, retrieval
from ..services import agent as rag_agent

router = APIRouter(prefix="/api/chat", tags=["chat"])

ABSTAIN = settings.ABSTAIN_TEXT

# shared in-process limiter lives in deps (swap point: redis)


class ChatIn(BaseModel):
    session_id: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)
    scope: str = "both"
    doc_ids: list[str] | None = None
    top_k: int = Field(default=8, ge=1, le=20)
    mode: str = "fast"  # fast|agent (agent wired in Plan 06)
    fresh: bool = False  # bypass cache (Plan 05)


async def _owned_session(db: AsyncSession, session_id: uuid.UUID, user_id: str) -> Session:
    s = (await db.execute(select(Session).where(Session.id == session_id))).scalar_one_or_none()
    if s is None or str(s.user_id) != user_id:
        raise HTTPException(404, "session not found")
    return s


async def _history(db: AsyncSession, session_id: uuid.UUID, n: int = 6) -> list[dict]:
    rows = (await db.execute(select(Message).where(Message.session_id == session_id)
                             .order_by(Message.created_at.desc()).limit(n))).scalars().all()
    return [{"role": m.role, "content": m.content[:1000]} for m in reversed(rows)]


@router.post("")
async def chat(body: ChatIn, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    check_rate(f"chat:{user_id}", 30, 60.0)
    session = await _owned_session(db, body.session_id, user_id)
    if body.scope not in ("both", "global", "private"):
        raise HTTPException(400, "scope must be both|global|private")

    # NOTE: `db` stays open for the whole SSE stream (FastAPI finalizes
    # dependencies after the response body is fully sent), so the generator
    # below reuses it instead of opening new sessions (test-override safe).
    history = await _history(db, session.id)  # before inserting current query
    db.add(Message(session_id=session.id, role="user", content=body.query))
    await db.commit()

    t0 = time.perf_counter()
    model = settings.LLM_MODEL if body.mode != "agent" else settings.LLM_MODEL + "+agent"

    async def _touch(updated_title: str | None = None):
        session.updated_at = datetime.now(timezone.utc)
        if session.title == "New chat" and updated_title:
            session.title = updated_title[:60]
        await db.commit()

    async def _save_assistant(answer: str, cites: list, ms: int, cached: bool,
                              tokens_in: int = 0, agent_trace: list | None = None):
        db.add(Message(session_id=session.id, role="assistant", content=answer, citations=cites,
                       model=model, tokens_in=tokens_in, tokens_out=len(answer.split()),
                       latency_ms=ms, cached=cached, agent_trace=agent_trace or []))
        await _touch(body.query)

    async def gen():
        # --- Plan 06 agent mode (bypasses cache; full trace persisted) ---
        if body.mode == "agent":
            _trace_buf: list = []

            async def emit(node: str, status: str):
                _trace_buf.append((node, status))

            # run agent first, then stream node events + answer (simpler SSE ordering)
            res = await rag_agent.run_agent(db, body.query, user_id, body.scope, body.doc_ids,
                                            body.top_k, history, emit=emit)
            for node, status in _trace_buf:
                yield f"data: {json.dumps({'node': node, 'status': status})}\n\n"
            ms = int((time.perf_counter() - t0) * 1000)
            await _save_assistant(res["answer"], res["citations"], ms, cached=False,
                                  agent_trace=res["trace"])
            for i in range(0, len(res["answer"]), 200):
                yield f"data: {json.dumps({'delta': res['answer'][i:i + 200]})}\n\n"
            yield f"data: {json.dumps({'done': {'answer': res['answer'], 'citations': res['citations'], 'cached': False, 'mode': 'agent', 'iters': res['iters'], 'trace_steps': len(res['trace']), 'model': model, 'latency_ms': ms}})}\n\n"
            return

        # --- Plan 05 cache lookup (skipped with ?fresh=true or agent mode) ---
        if not body.fresh and body.mode != "agent":
            hit = await qcache.lookup(db, body.query, body.scope, body.doc_ids, body.top_k, model)
            if hit is not None and hit["tier"] in ("exact", "semantic"):
                ms = int((time.perf_counter() - t0) * 1000)
                await _save_assistant(hit["answer"], hit["citations"], ms, cached=True)
                yield f"data: {json.dumps({'delta': hit['answer']})}\n\n"
                yield f"data: {json.dumps({'done': {'answer': hit['answer'], 'citations': hit['citations'], 'cached': True, 'tier': hit['tier'], 'model': model, 'latency_ms': ms}})}\n\n"
                return
            near_docs = hit["doc_ids"] if (hit is not None and hit["tier"] == "near_dup" and hit.get("doc_ids")) else None
        else:
            near_docs = None

        eff_doc_ids = near_docs or body.doc_ids
        hits = await retrieval.retrieve(db, body.query, user_id, body.scope, eff_doc_ids, body.top_k)
        if not hits:
            answer, cites = ABSTAIN, []
            ms = int((time.perf_counter() - t0) * 1000)
            await _save_assistant(answer, cites, ms, cached=False)
            if not body.fresh and body.mode != "agent":
                await qcache.store(db, body.query, body.scope, body.doc_ids, body.top_k, model,
                                   answer, cites, [], negative=True)
            yield f"data: {json.dumps({'done': {'answer': answer, 'citations': cites, 'cached': False, 'model': 'none', 'latency_ms': ms}})}\n\n"
            return
        messages = [{"role": "system", "content": cit.SYSTEM_PROMPT}]
        messages += history
        messages.append({"role": "user",
                         "content": f"QUESTION: {body.query}\n\nCONTEXT:\n{cit.build_context(hits)}"})
        parts: list[str] = []
        async for delta in llm.astream(messages):
            parts.append(delta)
            yield f"data: {json.dumps({'delta': delta})}\n\n"
        raw = "".join(parts)
        answer, cites = cit.verify(raw, hits)
        ms = int((time.perf_counter() - t0) * 1000)
        approx_in = sum(len(m["content"].split()) for m in messages)
        await _save_assistant(answer, cites, ms, cached=False, tokens_in=approx_in)
        if not body.fresh and body.mode != "agent":
            await qcache.store(db, body.query, body.scope, body.doc_ids, body.top_k, model,
                               answer, cites, [h.doc_id for h in hits])
        yield f"data: {json.dumps({'done': {'answer': answer, 'citations': cites, 'cached': False, 'model': model, 'latency_ms': ms}})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
