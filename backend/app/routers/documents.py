import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas_docs
from ..db import get_db
from ..deps import get_current_user
from ..models import ChunkRegistry, Document

router = APIRouter(prefix="/api/documents", tags=["documents"])

MAX_BYTES = 100 * 1024 * 1024
UPLOAD_ROOT = Path("data/uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

ALLOWED_SUFFIXES = {".pdf", ".docx", ".pptx", ".txt", ".md", ".html", ".csv", ".xlsx", ".xls",
                    ".png", ".jpg", ".jpeg", ".webp", ".mp3", ".wav", ".m4a", ".ogg", ".mp4", ".mov"}


def _blob_path(scope: str, user_id: str, doc_id: str, filename: str) -> Path:
    p = UPLOAD_ROOT / scope / user_id / doc_id
    p.mkdir(parents=True, exist_ok=True)
    safe = "".join(c for c in filename if c.isalnum() or c in "._- ")[:120] or "file"
    return p / safe


@router.post("/upload", status_code=202)
async def upload(
    file: UploadFile = File(...),
    scope: str = Form(default="private"),
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user),
):
    if scope not in ("private", "global"):
        raise HTTPException(400, "scope must be private|global")
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "file exceeds 100MB")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, f"unsupported type {suffix}")
    doc_id = str(uuid.uuid4())
    dest = _blob_path(scope, user_id, doc_id, file.filename or "file")
    dest.write_bytes(data)
    mime = mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    doc = Document(owner_id=uuid.UUID(user_id), scope=scope, filename=file.filename or "file",
                   mime=mime, bytes=len(data), blob_path=str(dest), status="queued")
    # keep our generated uuid
    doc.id = uuid.UUID(doc_id)
    db.add(doc)
    await db.commit()
    # Ingestion is triggered explicitly via POST /documents/{id}/process
    # (worker, demo script, or tests) — no auto thread here so unit tests
    # stay hermetic and prod can use Celery without request-thread DB use.
    return {"doc_id": doc_id, "status": "queued"}


@router.post("/{doc_id}/process")
async def process_doc(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    from ..workers.tasks import ingest_doc_async
    from sqlalchemy import select
    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
    if doc is None or str(doc.owner_id) != user_id:
        raise HTTPException(404, "document not found")
    from ..db import SessionLocal
    status = await ingest_doc_async(str(doc_id), SessionLocal)
    return {"doc_id": str(doc_id), "status": status}


@router.get("", response_model=list[schemas_docs.DocumentOut])
async def list_docs(db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    rows = (await db.execute(select(Document).where(Document.owner_id == uuid.UUID(user_id)).order_by(Document.created_at.desc()))).scalars().all()
    return [schemas_docs.DocumentOut(doc_id=r.id, filename=r.filename, mime=r.mime, scope=r.scope,
                                     status=r.status, page_count=r.page_count, error=r.error) for r in rows]


@router.get("/{doc_id}/status")
async def doc_status(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
    if doc is None or str(doc.owner_id) != user_id:
        raise HTTPException(404, "document not found")
    progress = {"queued": 5, "parsing": 25, "chunking": 55, "embedding": 80, "ready": 100, "failed": 100}[doc.status]
    return {"status": doc.status, "progress": progress, "error": doc.error, "page_count": doc.page_count}


@router.get("/{doc_id}/download")
async def download_doc(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    from fastapi.responses import FileResponse
    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
    if doc is None or str(doc.owner_id) != user_id:
        raise HTTPException(404, "document not found")
    if not Path(doc.blob_path).exists():
        raise HTTPException(410, "blob no longer stored")
    return FileResponse(doc.blob_path, filename=doc.filename, media_type=doc.mime)


@router.delete("/{doc_id}", status_code=204)
async def delete_doc(doc_id: uuid.UUID, db: AsyncSession = Depends(get_db), user_id: str = Depends(get_current_user)):
    doc = (await db.execute(select(Document).where(Document.id == doc_id))).scalar_one_or_none()
    if doc is None or str(doc.owner_id) != user_id:
        raise HTTPException(404, "document not found")
    await db.execute(delete(ChunkRegistry).where(ChunkRegistry.doc_id == doc.id))
    try:
        Path(doc.blob_path).unlink(missing_ok=True)
    except Exception:
        pass
    # Plan 05: invalidate cached answers that cited this doc
    try:
        from ..services import cache as _qcache
        await _qcache.invalidate_doc(db, str(doc_id))
    except Exception:
        pass
    # best-effort qdrant delete
    try:
        from qdrant_client import QdrantClient, models
        from ..config import settings
        client = QdrantClient(url=settings.QDRANT_URL, timeout=5)
        client.delete(collection_name="text-v1", points_selector=models.FilterSelector(
            filter=models.Filter(must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=str(doc_id)))])))
    except Exception:
        pass
    await db.delete(doc)
    await db.commit()
    return None
