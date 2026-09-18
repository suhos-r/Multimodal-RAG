"""Plan 04 smoke: real Ollama LLM + embeddings, sqlite DB, lexical+dense retrieval.
Run:  python scripts/smoke04.py   (needs: ollama serve with llama3.1:8b-instruct-q4_K_M + nomic-embed-text)
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import Base, get_db
from app.main import app
from app.workers.tasks import ingest_doc_async

DB = "sqlite+aiosqlite:///./smoke04.db"
engine = create_async_engine(DB, future=True)
SmokeSession = async_sessionmaker(engine, expire_on_commit=False)


async def override_db():
    async with SmokeSession() as s:
        yield s


async def main():
    Path("smoke04.db").unlink(missing_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.services import embed as _embed_check  # noqa
    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r0 = await c.post("/api/auth/signup", json={"email": "smoke@x.com", "password": "password123"})
        print("signup:", r0.status_code, r0.text[:300])
        tok = r0.json()
        h = {"Authorization": f"Bearer {tok['access_token']}"}
        sid = (await c.post("/api/sessions", json={}, headers=h)).json()["id"]
        fact = ("The Kestrel acquisition closed in June for 900 million dollars. "
                "Nimbus cloud division grew 22 percent in Q3 on 2.1 billion revenue.")
        doc_id = (await c.post("/api/documents/upload", headers=h,
                               files={"file": ("facts.txt", fact.encode(), "text/plain")},
                               data={"scope": "private"})).json()["doc_id"]
        st = await ingest_doc_async(doc_id, SmokeSession)
        print("ingest:", st)

        from app.services import embed
        vec, backend = await embed.embed_query("What did Kestrel cost?")
        print("embed backend:", backend, "dim:", len(vec))

        body = {"session_id": sid, "query": "How much did the Kestrel acquisition cost and when did it close?"}
        # stream manually to show deltas
        async with c.stream("POST", "/api/chat", json=body, headers=h) as r:
            print("chat status:", r.status_code)
            async for line in r.aiter_lines():
                if line.startswith("data: "):
                    e = json.loads(line[6:])
                    if "delta" in e:
                        print(e["delta"], end="", flush=True)
                    else:
                        print("\n---DONE---")
                        print(json.dumps(e["done"], indent=2)[:800])
    await engine.dispose()


asyncio.run(main())
