"""Layout-aware chunking: one chunk per page/section/slide/table.

Rules (binding):
- text blocks: one chunk per block (page/section preserved, never merged across pages)
- table blocks: NEVER split (kept whole; overflow >2000 words falls back to
  row-groups with the header row repeated)
- image/audio/video blocks: atomic, one chunk each
"""
from ..parsers.normalize import RawBlock
from .base import Chunk, approx_tokens

TABLE_MAX_WORDS = 2000
# Safety cap: text blocks beyond this fall back to sentence-boundary windows
# WITHIN the same page (page metadata preserved). Prevents giant unbounded
# chunks on very long pages while keeping normal pages whole.
LAYOUT_MAX_WORDS = 2000
LAYOUT_FALLBACK = 800
LAYOUT_FALLBACK_OVERLAP = 150


def _split_table(text: str) -> list[str]:
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if len(text.split()) <= TABLE_MAX_WORDS or len(lines) <= 2:
        return [text]
    header = lines[0]
    body = lines[1:]
    groups: list[str] = []
    cur = [header]
    cur_len = len(header.split())
    for ln in body:
        n = len(ln.split())
        if cur_len + n > TABLE_MAX_WORDS and len(cur) > 1:
            groups.append("\n".join(cur))
            cur, cur_len = [header], len(header.split())
        cur.append(ln)
        cur_len += n
    if len(cur) > 1 or (len(cur) == 1 and cur[0] != header):
        groups.append("\n".join(cur))
    return groups or [text]


def chunk(blocks: list[RawBlock], doc_id: str) -> list[Chunk]:
    out: list[Chunk] = []
    ordinal = 0
    for b in blocks:
        modality = b.modality or "text"
        if modality == "table":
            pieces = _split_table(b.text or "")
        elif modality in ("image", "audio", "video"):
            pieces = [(b.text or "").strip() or f"({modality} block)"]
        elif len((b.text or "").split()) > LAYOUT_MAX_WORDS:
            # over-long page: sentence-boundary windows, page preserved
            from .base import sentence_split
            sents = sentence_split(b.text or "")
            pieces, cur, cur_len = [], [], 0
            for s in sents:
                n = len(s.split())
                if cur and cur_len + n > LAYOUT_FALLBACK:
                    pieces.append(" ".join(cur))
                    carry = " ".join(" ".join(cur).split()[-LAYOUT_FALLBACK_OVERLAP:])
                    cur, cur_len = ([carry] if carry else []), len(carry.split())
                cur.append(s)
                cur_len += n
            if cur:
                pieces.append(" ".join(cur))
            pieces = pieces or [(b.text or "").strip()]
        else:
            pieces = [(b.text or "").strip()]
        for piece in pieces:
            if len(piece.split()) < 3 and modality == "text":
                continue
            out.append(Chunk(chunk_id=f"{doc_id}:{ordinal:04d}", parent_id=None, text=piece,
                             page=b.page, bbox=b.bbox, ts=b.ts, modality=modality,
                             token_count=approx_tokens(piece),
                             meta={"strategy": "layout", "atomic": modality in ("table", "image", "audio", "video")}))
            ordinal += 1
    return out
