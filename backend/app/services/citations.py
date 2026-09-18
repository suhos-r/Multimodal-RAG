"""Citation verifier: maps [n] markers to hits, drops unsupported sentences."""
import re

from ..config import settings
from .retrieval import Hit, words

MARKER = re.compile(r"\[(\d+)\]")


def _sentence_support(sentence: str, text: str) -> float:
    sw, tw = words(sentence), words(text)
    sw = {w for w in sw if not w.isdigit()}
    if not sw:
        return 1.0
    return len(sw & tw) / len(sw)


def verify(answer: str, hits: list[Hit]) -> tuple[str, list[dict]]:
    """Returns (cleaned_answer, citations[]). Never invents page numbers."""
    # normalize models that echo the placeholder literally ("[n]" -> first source)
    answer = re.sub(r"\[n\]", "[1]", answer)
    by_n = {i + 1: h for i, h in enumerate(hits)}
    citations = []
    for n, h in by_n.items():
        quote = " ".join(h.text.split()[:40])
        citations.append({"id": n, "doc_id": h.doc_id, "filename": h.filename, "page": h.page,
                          "modality": h.modality, "quote": quote, "score": round(h.fused_score, 4)})

    if not hits:
        return settings.ABSTAIN_TEXT, []

    kept: list[str] = []
    for sent in re.split(r"(?<=[.!?])\s+", answer.strip()):
        if not sent.strip():
            continue
        nums = [int(m) for m in MARKER.findall(sent)]
        valid = [n for n in nums if n in by_n and _sentence_support(MARKER.sub("", sent), by_n[n].text) >= 0.15]
        if valid:
            # normalize markers to valid ones only
            sent = MARKER.sub(lambda m: m.group(0) if int(m.group(1)) in valid else "", sent)
            kept.append(sent)
        # sentences without markers are dropped (unsupported) — except abstain text
    if not kept:
        return settings.ABSTAIN_TEXT, []
    used = sorted({int(m) for s in kept for m in MARKER.findall(s)})
    return " ".join(kept), [c for c in citations if c["id"] in used]


def build_context(hits: list[Hit]) -> str:
    return "\n".join(f"[{i + 1}] (doc={h.filename} p={h.page}) {h.text[:1500]}" for i, h in enumerate(hits))


SYSTEM_PROMPT = (
    "You answer ONLY from CONTEXT. Every factual sentence ends with a citation marker "
    "like [1] or [2] matching the SOURCES numbers.\n"
    "Example: SOURCES:\n[1] Revenue grew 12 percent.\n[2] Refunds take 5 days.\n"
    "Correct answer: Revenue grew 12 percent [1]. Refunds take 5 days [2].\n"
    "Rules: use ONLY the numbers shown in SOURCES (never [n], never new numbers). "
    "If CONTEXT lacks the answer, say exactly: \"I don't know based on the knowledge base.\" "
    "Never invent page numbers. Keep answers concise."
)
