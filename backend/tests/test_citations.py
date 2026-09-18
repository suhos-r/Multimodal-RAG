"""Unit tests for the citation verifier: no invented pages, unsupported dropped."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.citations import verify
from app.services.retrieval import Hit

HITS = [
    Hit(chunk_id="d:0000", doc_id="doc-a", filename="q3.pdf", page=4, modality="text",
        text="Q3 revenue grew 12 percent year over year to 4.8 billion dollars, driven by Nimbus.", fused_score=0.9),
    Hit(chunk_id="d:0001", doc_id="doc-b", filename="policy.txt", page=1, modality="text",
        text="Refunds are processed within 5 business days to the original payment method.", fused_score=0.5),
]


def test_supported_sentence_kept_with_citation():
    ans, cites = verify("Revenue grew 12 percent to 4.8 billion dollars [1].", HITS)
    assert "[1]" in ans
    assert cites and cites[0]["doc_id"] == "doc-a" and cites[0]["page"] == 4
    assert len(cites[0]["quote"].split()) <= 40


def test_literal_n_placeholder_normalized():
    ans, cites = verify("Revenue grew 12 percent to 4.8 billion dollars [n].", HITS)
    assert "[1]" in ans and cites and cites[0]["doc_id"] == "doc-a"


def test_unsupported_sentence_dropped_and_bad_marker_removed():
    ans, cites = verify("Revenue grew 12 percent [1]. The moon is cheese [2]. Unmarked claim here.", HITS)
    assert "moon" not in ans and "Unmarked" not in ans
    assert "[1]" in ans and cites and cites[0]["id"] == 1


def test_all_unsupported_abstains():
    ans, cites = verify("The moon is made of cheese.", HITS)
    assert ans == "I don't know based on the knowledge base." and cites == []


def test_no_hits_abstains_without_llm():
    ans, cites = verify("Anything at all [1].", [])
    assert ans == "I don't know based on the knowledge base." and cites == []
