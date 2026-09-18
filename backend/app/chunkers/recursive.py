"""Recursive chunking: split on separators hierarchically, 800-word windows, 150 overlap."""
from ..parsers.normalize import RawBlock
from .base import Chunk, approx_tokens

SIZE = 800
OVERLAP = 150
SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", " "]


def _recursive_split(text: str, seps: list[str]) -> list[str]:
    if not seps:
        return [text]
    sep, rest = seps[0], seps[1:]
    if sep not in text:
        return _recursive_split(text, rest)
    parts: list[str] = []
    for p in text.split(sep):
        p = p.strip()
        if p:
            parts.extend(_recursive_split(p, rest) if len(p.split()) > SIZE else [p])
    return parts


def chunk(blocks: list[RawBlock], doc_id: str, size: int = SIZE, overlap: int = OVERLAP) -> list[Chunk]:
    out: list[Chunk] = []
    ordinal = 0
    for b in blocks:
        units = _recursive_split(b.text or "", SEPARATORS)
        # greedily merge units into windows
        window: list[str] = []
        wlen = 0
        windows: list[str] = []
        for u in units:
            ulen = len(u.split())
            if wlen + ulen > size and window:
                windows.append(" ".join(window))
                # overlap: carry last ~overlap words
                carry = " ".join(" ".join(window).split()[-overlap:])
                window, wlen = [carry] if carry else [], len(carry.split())
            window.append(u)
            wlen += ulen
        if window:
            windows.append(" ".join(window))
        for w in windows:
            if len(w.split()) < 3:
                continue
            out.append(Chunk(chunk_id=f"{doc_id}:{ordinal:04d}", parent_id=None, text=w,
                             page=b.page, bbox=b.bbox, ts=b.ts, modality=b.modality,
                             token_count=approx_tokens(w)))
            ordinal += 1
    return out
