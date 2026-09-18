"""Shared test DB: single sqlite engine + single get_db override for all test modules."""
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.main import app

test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


async def override_db():
    async with TestSession() as s:
        yield s


app.dependency_overrides[get_db] = override_db


@pytest_asyncio.fixture(autouse=True)
async def _schema():
    from app.deps import clear_rate_limits
    clear_rate_limits()
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
