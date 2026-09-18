"""Shared Chunk schema + Chunker protocol (binding for all strategies)."""
from pydantic import BaseModel


class Chunk(BaseModel):
    chunk_id: str  # f"{doc_id}:{ordinal:04d}"
    parent_id: str | None = None
    text: str
    page: int | None = None
    bbox: dict | None = None
    ts: list | None = None
    modality: str = "text"
    token_count: int = 0
    meta: dict = {}


def approx_tokens(text: str) -> int:
    """Free, dependency-free token estimate (whitespace words). Deterministic."""
    return len(text.split())


def sentence_split(text: str) -> list[str]:
    import re
    parts = re.split(r"(?<=[.!?\n])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]
