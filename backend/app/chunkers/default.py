"""Default chunker stub (Plan 03 will add variants). Recursive 800 chars / 150 overlap."""
from ..parsers.normalize import RawBlock


def default_chunk(blocks: list[RawBlock], doc_id: str, size: int = 800, overlap: int = 150) -> list[dict]:
    chunks: list[dict] = []
    ordinal = 0
    for b in blocks:
        text = (b.text or "").strip()
        if len(text) < 10:
            continue
        start = 0
        while start < len(text):
            piece = text[start:start + size]
            # sentence-safe cut
            if len(piece) == size and start + size < len(text):
                cut = max(piece.rfind(". "), piece.rfind("\n"))
                if cut > size // 2:
                    piece = piece[:cut + 1]
            chunks.append({"chunk_id": f"{doc_id}:{ordinal:04d}", "parent_id": None,
                           "text": piece, "page": b.page, "modality": b.modality,
                           "char_start": start, "char_end": start + len(piece)})
            ordinal += 1
            if start + size >= len(text):
                break
            start += size - overlap
    return chunks
