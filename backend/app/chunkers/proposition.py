"""Proposition chunking (small-to-big): atomic sentence propositions as children,
each linked to an ~800-word parent window. Retrieve child, serve parent.

Rule-based (no LLM call): sentences are the atomic units; parents are built
by greedily merging sentences. Swap in an LLM splitter later without changing
the interface.
"""
from ..parsers.normalize import RawBlock
from .base import Chunk, approx_tokens, sentence_split

PARENT_SIZE = 800


def chunk(blocks: list[RawBlock], doc_id: str) -> list[Chunk]:
    out: list[Chunk] = []
    ordinal = 0
    for b in blocks:
        sents = sentence_split(b.text or "")
        if not sents:
            continue
        # build parent windows first
        parents: list[list[str]] = []
        cur: list[str] = []
        cur_len = 0
        for s in sents:
            n = len(s.split())
            if cur and cur_len + n > PARENT_SIZE:
                parents.append(cur)
                cur, cur_len = [], 0
            cur.append(s)
            cur_len += n
        if cur:
            parents.append(cur)
        for pi, psents in enumerate(parents):
            parent_id = f"{doc_id}:p{pi:03d}"
            parent_text = " ".join(psents)
            out.append(Chunk(chunk_id=parent_id, parent_id=None, text=parent_text,
                             page=b.page, bbox=b.bbox, ts=b.ts, modality=b.modality,
                             token_count=approx_tokens(parent_text),
                             meta={"strategy": "proposition", "role": "parent"}))
            for s in psents:
                if len(s.split()) < 3:
                    continue
                out.append(Chunk(chunk_id=f"{doc_id}:{ordinal:04d}", parent_id=parent_id, text=s,
                                 page=b.page, bbox=b.bbox, ts=b.ts, modality=b.modality,
                                 token_count=approx_tokens(s),
                                 meta={"strategy": "proposition", "role": "child"}))
                ordinal += 1
    return out


def expand_to_parent(chunk_id: str, index: dict[str, Chunk]) -> Chunk:
    """Small-to-big serve step: given a retrieved child, return its parent window."""
    c = index[chunk_id]
    if c.meta.get("role") == "child" and c.parent_id and c.parent_id in index:
        return index[c.parent_id]
    return c
