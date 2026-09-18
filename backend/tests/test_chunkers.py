"""Unit tests for the 5 chunkers: overlap math, table atomicity, parent linkage."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.chunkers import REGISTRY, get
from app.chunkers import layout as layout_m
from app.chunkers import proposition as prop_m
from app.parsers.normalize import RawBlock

DOC = "doc1"


def blocks(*texts: str, modality: str = "text", page: int = 1) -> list[RawBlock]:
    return [RawBlock(modality=modality, text=t, page=page) for t in texts]


def test_registry_has_all_five():
    assert sorted(REGISTRY) == ["fixed", "layout", "proposition", "recursive", "semantic"]
    assert get("fixed") is REGISTRY["fixed"]


def test_fixed_overlap_math():
    text = " ".join(f"w{i}" for i in range(1200))
    chunks = REGISTRY["fixed"](blocks(text), DOC)
    assert len(chunks) == 3  # 500, 500 (400+100 overlap), 400
    first, second = chunks[0].text.split(), chunks[1].text.split()
    assert first[-100:] == second[:100]  # 100-word overlap
    assert all(c.token_count == len(c.text.split()) for c in chunks)


def test_recursive_preserves_ids_and_pages():
    chunks = REGISTRY["recursive"](blocks("Alpha. Beta. Gamma.", page=2), DOC)
    assert chunks and all(c.page == 2 for c in chunks)
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_semantic_splits_topics():
    a = ("The Meridian refund policy allows returns within 30 days of purchase for a full refund. "
         "Digital goods are refundable within 14 days of download with a receipt. "
         "After 30 days, store credit is issued instead of cash to the customer.")
    b = ("Deployments run Tuesday and Thursday at 10am UTC via the Tern pipeline. "
         "Rollback uses tern rollback to a prior build identifier. "
         "Health checks must pass within five minutes before announcing completion.")
    chunks = REGISTRY["semantic"](blocks(a + " " + b), DOC)
    assert len(chunks) >= 2  # topic shift forces a breakpoint


def test_proposition_parent_linkage():
    text = " ".join(f"Sentence number {i} about refunds." for i in range(60))
    chunks = REGISTRY["proposition"](blocks(text), DOC)
    parents = [c for c in chunks if c.meta.get("role") == "parent"]
    children = [c for c in chunks if c.meta.get("role") == "child"]
    assert parents and children
    by_id = {c.chunk_id: c for c in chunks}
    for ch in children:
        assert ch.parent_id in by_id
        served = prop_m.expand_to_parent(ch.chunk_id, by_id)
        assert served.meta.get("role") == "parent"
        assert ch.text in served.text  # parent window contains the child


def test_layout_table_atomic_and_image_atomic():
    table = "H1 | H2\n" + "\n".join(f"r{i}c1 | r{i}c2 value here" for i in range(50))
    chunks = layout_m.chunk(blocks(table, modality="table"), DOC)
    assert len(chunks) == 1  # small table never split
    assert chunks[0].meta["atomic"] is True
    img = layout_m.chunk(blocks("IMAGE x: floor plan", modality="image"), DOC)
    assert len(img) == 1 and img[0].modality == "image"
    # pages never merged
    two = layout_m.chunk(blocks("Page one text here.", page=1) + blocks("Page two text here.", page=2), DOC)
    assert [c.page for c in two] == [1, 2]


def test_layout_big_table_keeps_header():
    header = "H1 | H2 | H3"
    big = header + "\n" + "\n".join(" ".join(f"cell{i}{j}" for j in range(40)) for i in range(300))
    chunks = layout_m.chunk(blocks(big, modality="table"), DOC)
    assert len(chunks) > 1
    assert all(c.text.split("\n")[0] == header for c in chunks)  # header repeated
