"""Semantic chunking: breakpoint where adjacent-sentence similarity drops.

Free default: deterministic lexical (Jaccard) similarity — no model download.
If `sentence-transformers` + BGE-M3 is installed, set USE_EMBED=1 to use it.
"""
import os
import re

from ..parsers.normalize import RawBlock
from .base import Chunk, approx_tokens, sentence_split

STOP = set("the a an and or of to in on for with is are was were be as at by from that this it its into over after q q1 q2 q3".split())
BREAKPOINT = 0.35  # Jaccard < threshold => new chunk
MAX_WORDS = 1000


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _embed_sims(sentences: list[str]) -> list[float] | None:
    if os.getenv("USE_EMBED") != "1":
        return None
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        model = SentenceTransformer("BAAI/bge-m3")
        vecs = model.encode(sentences, normalize_embeddings=True)
        sims = [float(np.dot(vecs[i], vecs[i + 1])) for i in range(len(vecs) - 1)]
        return sims
    except ImportError:
        return None


def chunk(blocks: list[RawBlock], doc_id: str) -> list[Chunk]:
    out: list[Chunk] = []
    ordinal = 0
    for b in blocks:
        sents = sentence_split(b.text or "")
        if not sents:
            continue
        sims = _embed_sims(sents)
        cur: list[str] = [sents[0]]
        cur_len = len(sents[0].split())
        for i in range(1, len(sents)):
            sim = sims[i - 1] if sims else _jaccard(_words(sents[i - 1]), _words(sents[i]))
            new_topic = (sims is not None and sim < 0.75) or (sims is None and sim < BREAKPOINT)
            if (new_topic and cur_len > 30) or cur_len + len(sents[i].split()) > MAX_WORDS:
                text = " ".join(cur)
                out.append(Chunk(chunk_id=f"{doc_id}:{ordinal:04d}", parent_id=None, text=text,
                                 page=b.page, bbox=b.bbox, ts=b.ts, modality=b.modality,
                                 token_count=approx_tokens(text), meta={"strategy": "semantic"}))
                ordinal += 1
                cur, cur_len = [], 0
            cur.append(sents[i])
            cur_len += len(sents[i].split())
        if cur:
            text = " ".join(cur)
            out.append(Chunk(chunk_id=f"{doc_id}:{ordinal:04d}", parent_id=None, text=text,
                             page=b.page, bbox=b.bbox, ts=b.ts, modality=b.modality,
                             token_count=approx_tokens(text), meta={"strategy": "semantic"}))
            ordinal += 1
    return out
