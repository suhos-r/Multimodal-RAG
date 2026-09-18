"""Embeddings via local Ollama (nomic-embed-text, 768d). Hash fallback when offline."""
import hashlib
import math

import httpx

from ..config import settings

_MOCK = None


def set_mock(fn) -> None:
    """Tests: fn(texts: list[str]) -> list[list[float]]."""
    global _MOCK
    _MOCK = fn


def hash_embed(texts: list[str], dim: int = 768) -> list[list[float]]:
    """Deterministic dependency-free fallback. Same dim so Qdrant/tests stay compatible."""
    out = []
    for t in texts:
        vec = [0.0] * dim
        for w in t.lower().split():
            vec[int(hashlib.sha256(w.encode()).hexdigest(), 16) % dim] += 1.0
        n = math.sqrt(sum(v * v for v in vec)) or 1.0
        out.append([v / n for v in vec])
    return out


async def embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    """Returns (vectors, backend) where backend is 'ollama' or 'hash'."""
    if _MOCK is not None:
        return _MOCK(texts), "mock"
    if not texts:
        return [], "ollama"
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            all_vecs: list[list[float]] = []
            for i in range(0, len(texts), 32):
                r = await client.post(f"{settings.OLLAMA_BASE_URL}/api/embed",
                                      json={"model": settings.EMBED_MODEL, "input": texts[i:i + 32]})
                r.raise_for_status()
                all_vecs.extend(r.json()["embeddings"])
            return all_vecs, "ollama"
    except Exception as e:
        import sys as _sys
        print(f"[embed] Ollama {settings.EMBED_MODEL} failed ({e.__class__.__name__}: {str(e)[:120]}), "
              "using deterministic hash fallback", file=_sys.stderr)
        return hash_embed(texts, settings.EMBED_DIM), "hash"


async def embed_query(text: str) -> tuple[list[float], str]:
    vecs, backend = await embed_texts([text])
    return (vecs[0] if vecs else [0.0] * settings.EMBED_DIM), backend
