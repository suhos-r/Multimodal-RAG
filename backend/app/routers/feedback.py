"""Per-message feedback: thumbs/comment/correction. One row per (message, user)."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_current_user
from ..models import Feedback, Message, Session

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    message_id: uuid.UUID
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(default=None, max_length=1000)
    corrected_answer: str | None = Field(default=None, max_length=4000)


@router.post("", status_code=201)
async def submit(body: FeedbackIn, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    if body.rating == 0:
        raise HTTPException(400, "rating must be 1 or -1")
    msg = (await db.execute(select(Message).where(Message.id == body.message_id))).scalar_one_or_none()
    if msg is None:
        raise HTTPException(404, "message not found")
    sess = (await db.execute(select(Session).where(Session.id == msg.session_id))).scalar_one_or_none()
    if sess is None or str(sess.user_id) != user_id:
        raise HTTPException(404, "message not found")  # anti-enumeration
    existing = (await db.execute(select(Feedback).where(
        Feedback.message_id == body.message_id, Feedback.user_id == uuid.UUID(user_id)))).scalar_one_or_none()
    if existing is None:
        fb = Feedback(message_id=body.message_id, user_id=uuid.UUID(user_id), rating=body.rating,
                      comment=body.comment, corrected_answer=body.corrected_answer)
        db.add(fb)
        await db.commit()
        await db.refresh(fb)
        return {"id": str(fb.id)}
    existing.rating, existing.comment, existing.corrected_answer = body.rating, body.comment, body.corrected_answer
    await db.commit()
    return {"id": str(existing.id)}


@router.get("")
async def mine(message_id: uuid.UUID, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    fb = (await db.execute(select(Feedback).where(
        Feedback.message_id == message_id, Feedback.user_id == uuid.UUID(user_id)))).scalar_one_or_none()
    if fb is None:
        raise HTTPException(404, "no feedback")
    return {"id": str(fb.id), "rating": fb.rating, "comment": fb.comment,
            "corrected_answer": fb.corrected_answer}
