"""Hybrid retrieval: Postgres lexical (always) + Qdrant dense (when up) -> RRF -> rerank -> small-to-big."""
import re
from dataclasses import dataclass, field

from sqlalchemy import select

from ..config import settings
from ..models import ChunkRegistry, Document

STOP = set(("what when where which who how many much does do is are was were the a an and or of to in on for with "
            "is are be as at by from that this it its into over after our applies apply tier does").split())


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1}


def overlap_score(query_words: set[str], text: str) -> float:
    cw = words(text)
    if not query_words or not cw:
        return 0.0
    inter = len(query_words & cw)
    return inter / len(query_words) + 0.01 * inter / max(len(cw), 1)


@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    filename: str
    page: int | None
    modality: str
    text: str  # served text (parent-expanded for small-to-big)
    child_text: str = ""  # original retrieved text (== text unless expanded)
    dense_score: float = 0.0
    sparse_score: float = 0.0
    fused_score: float = 0.0
    expanded: bool = False


async def _candidate_rows(db, user_id: str, doc_ids: list[str] | None):
    """All chunks the user may see: global docs + own private docs. Enforced in SQL."""
    uid = __import__("uuid").UUID(user_id)
    doc_q = select(Document).where(
        (Document.scope == "global") | ((Document.scope == "private") & (Document.owner_id == uid)))
    if doc_ids:
        doc_q = doc_q.where(Document.id.in_([__import__("uuid").UUID(d) for d in doc_ids]))
    docs = (await db.execute(doc_q)).scalars().all()
    if not docs:
        return [], {}
    by_id = {str(d.id): d for d in docs}
    rows = (await db.execute(
        select(ChunkRegistry).where(ChunkRegistry.doc_id.in_([d.id for d in docs])))).scalars().all()
    return rows, by_id


def _rrf(ranks: dict[str, int], k: int = 60) -> float:
    return sum(1.0 / (k + r) for r in ranks.values())


async def retrieve(db, query: str, user_id: str, scope: str = "both",
                   doc_ids: list[str] | None = None, top_k: int = 8) -> list[Hit]:
    rows, docs_by_id = await _candidate_rows(db, user_id, doc_ids)
    if not rows:
        return []
    if scope == "global":
        rows = [r for r in rows if docs_by_id[str(r.doc_id)].scope == "global"]
    elif scope == "private":
        rows = [r for r in rows if docs_by_id[str(r.doc_id)].scope == "private"]
    if not rows:
        return []

    qw = words(query)
    sparse_ranked = sorted(rows, key=lambda r: overlap_score(qw, r.text or ""), reverse=True)
    sparse_rank = {r.chunk_id: i + 1 for i, r in enumerate(sparse_ranked)}

    dense_rank: dict[str, int] = {}
    dense_scores: dict[str, float] = {}
    try:
        from .embed import embed_query
        from .qdrant_store import QdrantStore
        store = QdrantStore()
        if store.available:
            qvec, _ = await embed_query(query)
            scopes = ["global", f"user:{user_id}"] if scope == "both" else (
                ["global"] if scope == "global" else [f"user:{user_id}"])
            for i, hit in enumerate(store.search(qvec, scopes, doc_ids, limit=20)):
                cid = hit["chunk_id"]
                if cid and cid not in dense_rank:
                    dense_rank[cid] = i + 1
                    dense_scores[cid] = hit["score"]
    except Exception:
        pass

    fused = []
    for r in rows:
        ranks = {"sparse": sparse_rank[r.chunk_id]}
        if r.chunk_id in dense_rank:
            ranks["dense"] = dense_rank[r.chunk_id]
        fused.append((_rrf(ranks), r))
    fused.sort(key=lambda t: t[0], reverse=True)

    # rerank top-20 -> top_k by query-term overlap (swap point: cross-encoder)
    pool = fused[:20]
    if settings.RERANK_ENABLED:
        pool.sort(key=lambda t: overlap_score(qw, t[1].text or ""), reverse=True)
    top = pool[:top_k]

    by_chunk = {r.chunk_id: r for r in rows}
    hits: list[Hit] = []
    for fused_score, r in top:
        doc = docs_by_id[str(r.doc_id)]
        text, expanded = (r.text or ""), False
        if r.parent_id and r.parent_id in by_chunk and by_chunk[r.parent_id].text:
            text, expanded = by_chunk[r.parent_id].text, True  # small-to-big: serve parent
        hits.append(Hit(chunk_id=r.chunk_id, doc_id=str(r.doc_id), filename=doc.filename,
                        page=r.page, modality=r.modality, text=text, child_text=r.text or "",
                        dense_score=dense_scores.get(r.chunk_id, 0.0),
                        sparse_score=overlap_score(qw, r.text or ""),
                        fused_score=fused_score, expanded=expanded))
    return hits
