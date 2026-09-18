"""ingest_doc: parse -> chunk -> register -> (best-effort qdrant) -> ready.

Async core takes an explicit session factory so tests can inject sqlite
while prod uses the Postgres SessionLocal. Sync wrapper only used by
worker threads / scripts (never inside a running event loop).
"""
import asyncio
import uuid

from ..chunkers.default import default_chunk
from ..models import ChunkRegistry, Document
from ..parsers.router import parse_file


def _upsert_qdrant(doc_id: str, scope: str, chunks: list) -> None:
    """Best-effort dense index. Postgres registry (with text) is source of truth."""
    try:
        from ..config import settings as _settings
        from ..services import embed as _embed
        from ..services.qdrant_store import QdrantStore
        import asyncio as _asyncio

        async def _vectors():
            return await _embed.embed_texts([c.text for c in chunks])

        try:
            _asyncio.get_running_loop()
            return  # worker thread/process context only; skip when loop running
        except RuntimeError:
            vecs, _ = _asyncio.run(_vectors())
        if not vecs:
            return
        store = QdrantStore()
        if not store.available or not store.ensure(_settings.EMBED_DIM):
            return
        store.upsert([{"vector": v, "payload": {
            "scope": scope, "doc_id": doc_id, "chunk_id": c.chunk_id,
            "page": c.page, "modality": c.modality, "text": c.text[:2000]}}
            for c, v in zip(chunks, vecs)])
    except Exception:
        pass  # registry in Postgres is source of truth for Plan 02 acceptance


async def ingest_doc_async(doc_id: str, session_factory=None) -> str:
    if session_factory is None:
        from ..db import SessionLocal as session_factory
    from sqlalchemy import delete, select
    async with session_factory() as db:
        doc = (await db.execute(select(Document).where(Document.id == uuid.UUID(doc_id)))).scalar_one_or_none()
        if doc is None:
            return "missing"
        try:
            doc.status = "parsing"
            await db.commit()
            blocks, warning = parse_file(doc.blob_path, doc.mime)
            doc.status = "chunking"
            await db.commit()
            from ..chunkers import get as get_chunker
            chunker = get_chunker()  # CHUNK_STRATEGY env (Plan 03 winner)
            chunk_objs = chunker(blocks, doc_id)
            doc.status = "embedding"
            await db.commit()
            await db.execute(delete(ChunkRegistry).where(ChunkRegistry.doc_id == doc.id))
            for c in chunk_objs:
                db.add(ChunkRegistry(doc_id=doc.id, chunk_id=c.chunk_id, parent_id=c.parent_id,
                                     page=c.page, modality=c.modality, text=c.text))
            doc.page_count = len({b.page for b in blocks if b.page}) or 1
            if warning:
                doc.error = warning[:500]
            await db.commit()
            scope = "global" if doc.scope == "global" else f"user:{doc.owner_id}"
            _upsert_qdrant(doc_id, scope, chunk_objs)
            doc.status = "ready"
            await db.commit()
            return "ready"
        except Exception as e:
            doc.status = "failed"
            doc.error = f"{e.__class__.__name__}: {e}"[:500]
            await db.commit()
            return "failed"


def ingest_doc_sync(doc_id: str, session_factory=None) -> str:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(ingest_doc_async(doc_id, session_factory))
    raise RuntimeError("ingest_doc_sync cannot run inside a running loop; await ingest_doc_async instead")


try:
    from .celery_app import celery_app
    if celery_app is not None:
        @celery_app.task(name="ingest_doc", bind=True, max_retries=3)
        def ingest_doc(self, doc_id: str):
            try:
                return ingest_doc_sync(doc_id)
            except Exception as e:
                raise self.retry(exc=e, countdown=2 ** self.request.retries)
    else:
        def ingest_doc(doc_id: str):
            return ingest_doc_sync(doc_id)
except ImportError:
    def ingest_doc(doc_id: str):
        return ingest_doc_sync(doc_id)
