"""Nightly feedback rollup: helpfulness, failing docs, eval candidates.

Run:  python scripts/rollup_feedback.py [--write-candidates]
Writes low-rated cases to evals/feedback_candidates.jsonl for HUMAN review
before they ever enter the gold set (review gate, never automatic).
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Feedback, Message


async def rollup(session_factory=SessionLocal) -> dict:
    async with session_factory() as db:
        total = (await db.execute(select(func.count()).select_from(Feedback))).scalar_one()
        ups = (await db.execute(select(func.count()).select_from(Feedback).where(Feedback.rating == 1))).scalar_one()
        downs = total - ups
        # docs behind downvoted answers (via message citations)
        failing: dict[str, int] = {}
        rows = (await db.execute(select(Message.citations).join(
            Feedback, Feedback.message_id == Message.id).where(Feedback.rating == -1))).all()
        for (cites,) in rows:
            for c in (cites or []):
                if isinstance(c, dict) and c.get("doc_id"):
                    failing[c["doc_id"]] = failing.get(c["doc_id"], 0) + 1
        # corrected answers become eval candidates
        corrected = (await db.execute(select(Feedback.corrected_answer, Feedback.message_id).where(
            Feedback.corrected_answer.is_not(None)))).all()
        return {"total": total, "up": ups, "down": downs,
                "helpfulness_pct": round(100 * ups / total, 1) if total else None,
                "failing_doc_ids": sorted(failing, key=failing.get, reverse=True)[:10],
                "corrected_count": len(corrected),
                "candidates": [{"message_id": str(mid), "corrected_answer": a} for a, mid in corrected]}


async def main() -> None:
    write = "--write-candidates" in sys.argv
    stats = await rollup()
    print(json.dumps({k: v for k, v in stats.items() if k != "candidates"}, indent=2))
    if write and stats["candidates"]:
        out = Path(__file__).parent.parent / "evals" / "feedback_candidates.jsonl"
        with open(out, "a", encoding="utf-8") as f:
            for c in stats["candidates"]:
                f.write(json.dumps(c) + "\n")
        print(f"appended {len(stats['candidates'])} candidates to {out} (REVIEW BEFORE gold)")


if __name__ == "__main__":
    asyncio.run(main())
