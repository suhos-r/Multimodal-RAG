"""Create all tables (idempotent). Used by docker entrypoint and first-time setup.

Run:  python -m app.init_db   (from backend/, with DATABASE_URL set)
"""
import asyncio

from . import models  # noqa: F401 — register tables on Base.metadata
from .db import Base, engine


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("init_db: tables ready")


if __name__ == "__main__":
    asyncio.run(main())
