import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_db

Path("dbg2.db").unlink(missing_ok=True)
e = create_async_engine("sqlite+aiosqlite:///./dbg2.db", future=True)
S = async_sessionmaker(e, expire_on_commit=False)


async def override_db():
    async with S() as s:
        yield s


async def main():
    async with e.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    from app.main import app
    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/auth/signup", json={"email": "d2@x.com", "password": "password123"})
        print("signup:", r.status_code, r.text[:300])
    await e.dispose()


asyncio.run(main())
print("DONE")
