import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas
from ..db import get_db
from ..deps import get_current_user
from ..models import Message, Session

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


async def _owned(db: AsyncSession, session_id: uuid.UUID, user_id: str) -> Session:
    s = (await db.execute(select(Session).where(Session.id == session_id))).scalar_one_or_none()
    if s is None or str(s.user_id) != user_id:
        raise HTTPException(status_code=404, detail="session not found")
    return s


@router.post("", response_model=schemas.SessionOut, status_code=201)
async def create_session(
    body: schemas.SessionCreate, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)
):
    s = Session(user_id=uuid.UUID(user_id), title=(body.title or "New chat")[:120])
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return schemas.SessionOut(id=s.id, title=s.title, updated_at=s.updated_at, preview=None)


@router.get("", response_model=list[schemas.SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    rows = (await db.execute(select(Session).where(Session.user_id == uuid.UUID(user_id)).order_by(desc(Session.updated_at)))).scalars().all()
    out: list[schemas.SessionOut] = []
    for s in rows:
        last = (await db.execute(select(Message).where(Message.session_id == s.id).order_by(desc(Message.created_at)).limit(1))).scalar_one_or_none()
        out.append(schemas.SessionOut(id=s.id, title=s.title, updated_at=s.updated_at, preview=(last.content[:120] if last else None)))
    return out


@router.get("/{session_id}/messages", response_model=list[schemas.MessageOut])
async def get_messages(session_id: uuid.UUID, limit: int = 50, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    await _owned(db, session_id, user_id)
    rows = (await db.execute(select(Message).where(Message.session_id == session_id).order_by(Message.created_at).limit(min(limit, 200)))).scalars().all()
    return [schemas.MessageOut(id=m.id, role=m.role, content=m.content, citations=m.citations or [], model=m.model, cached=m.cached, created_at=m.created_at) for m in rows]


@router.patch("/{session_id}", response_model=schemas.SessionOut)
async def rename_session(session_id: uuid.UUID, body: schemas.SessionUpdate, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    s = await _owned(db, session_id, user_id)
    s.title = body.title
    s.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return schemas.SessionOut(id=s.id, title=s.title, updated_at=s.updated_at, preview=None)


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: uuid.UUID, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    s = await _owned(db, session_id, user_id)
    await db.delete(s)
    await db.commit()
    return None
