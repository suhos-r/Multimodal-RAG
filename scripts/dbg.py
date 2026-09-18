import asyncio
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base
from app.routers.auth import signup
from app.schemas import SignupIn


async def main():
    Path("dbg.db").unlink(missing_ok=True)
    e = create_async_engine("sqlite+aiosqlite:///./dbg.db", future=True)
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    S = async_sessionmaker(e, expire_on_commit=False)
    async with S() as s:
        try:
            r = await signup(SignupIn(email="d@x.com", password="password123"), s)
            print("OK", r.token_type)
        except Exception:
            traceback.print_exc()
    await e.dispose()


asyncio.run(main())
print("DONE")
