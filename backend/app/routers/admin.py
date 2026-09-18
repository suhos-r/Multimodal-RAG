"""Admin stats: cache hit-rate, latency, tokens, helpfulness. Auth required."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..deps import get_current_user
from ..models import Feedback, Message
from ..services.cache import STATS

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    total_lookups = STATS["exact_hits"] + STATS["semantic_hits"] + STATS["misses"]
    hit_rate = round((STATS["exact_hits"] + STATS["semantic_hits"]) / total_lookups, 3) if total_lookups else 0.0
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    avg_lat = (await db.execute(select(func.avg(Message.latency_ms)).where(Message.created_at >= since))).scalar()
    tokens_24h = (await db.execute(select(func.sum(Message.tokens_in + Message.tokens_out)).where(
        Message.created_at >= since))).scalar()
    fb = (await db.execute(select(Feedback.rating, func.count()).group_by(Feedback.rating))).all()
    fb_map = {r: n for r, n in fb}
    up, down = fb_map.get(1, 0), fb_map.get(-1, 0)
    return {
        "cache_hit_rate_24h": hit_rate,
        "exact_hits": STATS["exact_hits"],
        "semantic_hits": STATS["semantic_hits"],
        "near_dup_hits": STATS["near_dup_hits"],
        "llm_calls_avoided": STATS["llm_calls_avoided"],
        "tokens_saved": STATS["tokens_saved"],
        "est_usd_saved": 0.0,  # local Ollama: $0 by construction
        "avg_latency_ms_24h": round(avg_lat, 1) if avg_lat else None,
        "tokens_24h": int(tokens_24h or 0),
        "helpfulness_pct": round(100 * up / (up + down), 1) if (up + down) else None,
        "feedback_up": up,
        "feedback_down": down,
    }
