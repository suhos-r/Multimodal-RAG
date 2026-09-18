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
from ..deps import get_current_user
from ..models import Message, Session
from ..services import citations as cit
from ..services import llm, retrieval

router = APIRouter(prefix="/api/chat", tags=["chat"])

ABSTAIN = settings.ABSTAIN_TEXT

# naive per-user rate limit: 30/min (swap point: slowapi/redis)
_CALLS: dict[str, list[float]] = {}
LIMIT, WINDOW = 30, 60.0


def _check_rate(user_id: str) -> None:
    now = time.time()
    buf = [t for t in _CALLS.get(user_id, []) if now - t < WINDOW]
    if len(buf) >= LIMIT:
        raise HTTPException(429, "rate limit exceeded, retry in a minute")
    buf.append(now)
    _CALLS[user_id] = buf


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
    _check_rate(user_id)
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
    hits = await retrieval.retrieve(db, body.query, user_id, body.scope, body.doc_ids, body.top_k)

    async def gen():
        if not hits:
            answer, cites = ABSTAIN, []
            ms = int((time.perf_counter() - t0) * 1000)
            db.add(Message(session_id=session.id, role="assistant", content=answer,
                           citations=cites, model="none", latency_ms=ms, cached=False))
            session.updated_at = datetime.now(timezone.utc)
            await db.commit()
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
        db.add(Message(session_id=session.id, role="assistant", content=answer, citations=cites,
                       model=settings.LLM_MODEL, tokens_in=approx_in,
                       tokens_out=len(answer.split()), latency_ms=ms, cached=False))
        session.updated_at = datetime.now(timezone.utc)
        if session.title == "New chat":
            session.title = body.query[:60]
        await db.commit()
        yield f"data: {json.dumps({'done': {'answer': answer, 'citations': cites, 'cached': False, 'model': settings.LLM_MODEL, 'latency_ms': ms}})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
