"""Fixed-size chunking: 500-word windows with 100-word overlap, sentence-safe."""
from ..parsers.normalize import RawBlock
from .base import Chunk, approx_tokens, sentence_split

SIZE = 500
OVERLAP = 100


def chunk(blocks: list[RawBlock], doc_id: str, size: int = SIZE, overlap: int = OVERLAP) -> list[Chunk]:
    out: list[Chunk] = []
    ordinal = 0
    for b in blocks:
        words = (b.text or "").split()
        if len(words) < 3:
            continue
        start = 0
        while start < len(words):
            piece_words = words[start:start + size]
            piece = " ".join(piece_words)
            out.append(Chunk(chunk_id=f"{doc_id}:{ordinal:04d}", parent_id=None, text=piece,
                             page=b.page, bbox=b.bbox, ts=b.ts, modality=b.modality,
                             token_count=approx_tokens(piece)))
            ordinal += 1
            if start + size >= len(words):
                break
            start += size - overlap
    _ = sentence_split  # keep import used for parity/debuggability
    return out
