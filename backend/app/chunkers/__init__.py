"""Chunker registry: name -> chunk function. Switch via CHUNK_STRATEGY env."""
from . import fixed, layout, proposition, recursive, semantic
from .base import Chunk  # noqa: F401 (re-export for convenience)

REGISTRY = {
    "fixed": fixed.chunk,
    "recursive": recursive.chunk,
    "semantic": semantic.chunk,
    "proposition": proposition.chunk,
    "layout": layout.chunk,
}

DEFAULT = "recursive"


def get(name: str | None = None):
    import os
    key = (name or os.getenv("CHUNK_STRATEGY", DEFAULT)).lower()
    if key not in REGISTRY:
        raise ValueError(f"unknown chunker {key!r}; choose from {sorted(REGISTRY)}")
    return REGISTRY[key]
