"""Layout edge cases: over-long pages fall back to windows, page preserved."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.chunkers import layout as layout_m
from app.parsers.normalize import RawBlock


def test_long_page_fallback_keeps_page_and_bounds_size():
    text = " ".join(f"Sentence {i} carries some content here." for i in range(600))  # ~3600 words
    chunks = layout_m.chunk([RawBlock(modality="text", text=text, page=7)], "doc9")
    assert len(chunks) > 1
    assert all(c.page == 7 for c in chunks)
    assert all(len(c.text.split()) <= 800 + 1 for c in chunks)
    assert chunks[0].text.rstrip()[-1] == "."
