"""Repeat-query cache: L1 exact (sha256) + L2 semantic (cosine>=0.97) + L3 near-dup reuse.

Durable store: Postgres query_cache. Hot store: in-process TTL dict
(swap point: Redis — same get/put semantics, keyed identically).
Semantic vectors: same embedding backend as retrieval (Ollama nomic-embed-text
in prod, mock/hash in tests). All comparisons gated on filters_hash equality.
"""
import hashlib
import math
import time
import unicodedata
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ..models import QueryCache

SEM_THRESHOLD = 0.97
NEAR_DUP_LOW = 0.90
TTL_H = 24
NEG_TTL_H = 1  # unanswerable results refresh sooner

_mem: dict[str, tuple[dict, float]] = {}  # key -> (payload, expires_ts)
STATS = {"exact_hits": 0, "semantic_hits": 0, "near_dup_hits": 0, "misses": 0,
         "tokens_saved": 0, "llm_calls_avoided": 0}


def clear_memory() -> None:
    _mem.clear()
    for k in STATS:
        STATS[k] = 0


def norm_query(q: str) -> str:
    q = unicodedata.normalize("NFKC", q).lower().strip()
    q = "".join(c for c in q if c.isalnum() or c.isspace())
    return " ".join(q.split())


def filters_hash(scope: str, doc_ids: list[str] | None, top_k: int, model: str) -> str:
    return hashlib.sha256("|".join([scope, ",".join(sorted(doc_ids or [])), str(top_k), model]).encode()).hexdigest()


def exact_key(norm_q: str, fhash: str) -> str:
    return "ex:" + hashlib.sha256(f"{norm_q}|{fhash}".encode()).hexdigest()


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def _mem_get(key: str) -> dict | None:
    item = _mem.get(key)
    if not item:
        return None
    payload, exp = item
    if time.time() > exp:
        _mem.pop(key, None)
        return None
    return payload


def _mem_put(key: str, payload: dict, ttl_s: float) -> None:
    _mem[key] = (payload, time.time() + ttl_s)


def _bump(row, saved_tokens: int) -> None:
    row.hits = (row.hits or 0) + 1
    row.tokens_saved = (row.tokens_saved or 0) + saved_tokens


async def lookup(db, query: str, scope: str, doc_ids: list[str] | None, top_k: int, model: str,
                 negative: bool = False) -> dict | None:
    """L1 exact -> L2 semantic. Returns payload {answer,citations,doc_ids,tier,key} or None."""
    nq = norm_query(query)
    fh = filters_hash(scope, doc_ids, top_k, model)
    key = exact_key(nq, fh)
    now = datetime.now(timezone.utc)

    hit = _mem_get(key)
    if hit is None:
        row = (await db.execute(select(QueryCache).where(QueryCache.key == key))).scalar_one_or_none()
        if row is not None and (row.expires_at is None or row.expires_at > now):
            hit = {"answer": row.response, "citations": row.citations or [],
                   "doc_ids": row.doc_ids or [], "key": key, "_row_key": key}
            _mem_put(key, hit, max((row.expires_at - now).total_seconds(), 1) if row.expires_at else TTL_H * 3600)
    if hit is not None:
        STATS["exact_hits"] += 1
        STATS["llm_calls_avoided"] += 1
        saved = len(hit["answer"].split())
        STATS["tokens_saved"] += saved
        row = (await db.execute(select(QueryCache).where(QueryCache.key == hit.get("_row_key", key)))).scalar_one_or_none()
        if row is not None:
            _bump(row, saved)
            await db.commit()
        return {**hit, "tier": "exact"}

    # L2 semantic (skip when caller only wants exact, e.g. negative results still use L1)
    from .embed import embed_query
    qvec, _ = await embed_query(query)
    rows = (await db.execute(select(QueryCache).where(
        QueryCache.filters_hash == fh,
        (QueryCache.expires_at.is_(None)) | (QueryCache.expires_at > now)))).scalars().all()
    best, best_sim = None, 0.0
    for r in rows:
        if not r.embedding:
            continue
        sim = cosine(qvec, r.embedding)
        if sim > best_sim:
            best, best_sim = r, sim
    if best is not None and best_sim >= NEAR_DUP_LOW:
        saved = len(best.response.split())
        _bump(best, saved)
        await db.commit()
        payload = {"answer": best.response, "citations": best.citations or [],
                   "doc_ids": best.doc_ids or [], "key": best.key}
        if best_sim >= SEM_THRESHOLD:
            STATS["semantic_hits"] += 1
            STATS["llm_calls_avoided"] += 1
            STATS["tokens_saved"] += saved
            _mem_put(exact_key(nq, fh), {**payload, "_row_key": best.key}, TTL_H * 3600)
            return {**payload, "tier": "semantic", "sim": round(best_sim, 4)}
        STATS["near_dup_hits"] += 1
        return {**payload, "tier": "near_dup", "sim": round(best_sim, 4)}
    STATS["misses"] += 1
    return None


async def store(db, query: str, scope: str, doc_ids: list[str] | None, top_k: int, model: str,
                answer: str, citations: list, hit_doc_ids: list[str], negative: bool = False) -> None:
    from .embed import embed_query
    nq = norm_query(query)
    fh = filters_hash(scope, doc_ids, top_k, model)
    key = exact_key(nq, fh)
    ttl = timedelta(hours=NEG_TTL_H if negative else TTL_H)
    now = datetime.now(timezone.utc)
    try:
        qvec, _ = await embed_query(query)
    except Exception:
        qvec = []
    payload = {"answer": answer, "citations": citations, "doc_ids": hit_doc_ids, "key": key}
    _mem_put(key, payload, ttl.total_seconds())
    row = (await db.execute(select(QueryCache).where(QueryCache.key == key))).scalar_one_or_none()
    if row is None:
        db.add(QueryCache(key=key, norm_query=nq, embedding=qvec, response=answer, citations=citations,
                          filters_hash=fh, doc_ids=hit_doc_ids, hits=1, expires_at=now + ttl))
    else:
        row.response, row.citations, row.embedding = answer, citations, qvec
        row.doc_ids, row.expires_at = hit_doc_ids, now + ttl
    await db.commit()


async def invalidate_doc(db, doc_id: str) -> int:
    rows = (await db.execute(select(QueryCache))).scalars().all()
    n = 0
    for r in rows:
        if doc_id in (r.doc_ids or []):
            await db.delete(r)
            n += 1
    await db.commit()
    _mem.clear()
    return n
