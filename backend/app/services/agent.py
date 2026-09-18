"""Self-reflective RAG agent: RETRIEVE -> GRADE -> [REWRITE] -> GENERATE -> CRITIQUE -> [REFLECT+RETRY] -> CITE.

Plain async state machine (no LangGraph dependency); node semantics and loop
guards match plans/06. Every node appends to trace[], persisted on the message.
"""
import json
import re
import time

from ..config import settings
from . import citations as cit
from . import llm, retrieval
from .retrieval import Hit

MAX_ITERS = 2
REWRITE_TRIES = 1
TIME_BUDGET_S = 45
GRADE_KEEP = 0.5

GRADER_SYSTEM = (
    "Score each SOURCE 0-1 for relevance to the QUESTION. "
    "Return ONLY JSON: [{\"id\": <n>, \"score\": <0-1>, \"reason\": \"<short>\"}]."
)
REWRITER_SYSTEM = (
    "Given the QUESTION and why retrieved sources failed, write 2 alternative "
    "queries (keywords, synonyms, split multi-hop). Return ONLY JSON: [\"alt1\", \"alt2\"]."
)
CRITIC_SYSTEM = (
    "Judge the DRAFT against SOURCES. Return ONLY JSON: "
    "{\"faithful\": 1-5, \"complete\": 1-5, \"cited\": true/false, \"issues\": [\"...\"]}. "
    "faithful: every sentence entailed by a cited quote. "
    "complete: all sub-questions answered. cited: every claim has [n]."
)


def _json_block(text: str):
    m = re.search(r"(\[.*\]|\{.*\})", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON in model output")
    return json.loads(m.group(1))


def _trace(trace: list, node: str, ms: int, detail: str = "") -> None:
    trace.append({"node": node, "ms": ms, "detail": detail[:300]})


async def _grade(query: str, hits: list[Hit]) -> list[dict]:
    srcs = "\n".join(f"[{i + 1}] {h.text[:600]}" for i, h in enumerate(hits))
    out = await llm.acomplete([{"role": "system", "content": GRADER_SYSTEM},
                               {"role": "user", "content": f"QUESTION: {query}\nSOURCES:\n{srcs}"}],
                              temperature=0.0, max_tokens=800)
    try:
        grades = _json_block(out["text"])
    except Exception:
        return [{"id": i + 1, "score": 0.5, "reason": "unparseable grade"} for i in range(len(hits))]
    return grades


async def _rewrite(query: str, reasons: str) -> list[str]:
    out = await llm.acomplete(
        [{"role": "system", "content": REWRITER_SYSTEM},
         {"role": "user", "content": f"QUESTION: {query}\nFAILURES: {reasons[:1000]}"}],
        temperature=0.3, max_tokens=300)
    try:
        alts = _json_block(out["text"])
        alts = [a for a in alts if isinstance(a, str) and a.strip()][:2]
        if alts:
            return alts
    except Exception:
        pass
    return [f"{query} keywords", f"{query} overview"]


async def _generate(query: str, hits: list[Hit], history: list[dict], feedback: str = "") -> str:
    extra = f"\nPREVIOUS CRITIQUE + FIX PLAN (address these, do not repeat mistakes):\n{feedback}\n" if feedback else ""
    messages = [{"role": "system", "content": cit.SYSTEM_PROMPT}]
    messages += history
    messages.append({"role": "user",
                     "content": f"QUESTION: {query}\n\nCONTEXT:\n{cit.build_context(hits)}{extra}"})
    out = await llm.acomplete(messages, temperature=0.1)
    return out["text"]


async def _critique(query: str, draft: str, hits: list[Hit]) -> dict:
    out = await llm.acomplete(
        [{"role": "system", "content": CRITIC_SYSTEM},
         {"role": "user", "content": f"QUESTION: {query}\nDRAFT:\n{draft[:2000]}\nSOURCES:\n{cit.build_context(hits)}"}],
        temperature=0.0, max_tokens=400)
    try:
        c = _json_block(out["text"])
        return {"faithful": int(c.get("faithful", 1)), "complete": int(c.get("complete", 1)),
                "cited": bool(c.get("cited", False)), "issues": list(c.get("issues", []))[:5]}
    except Exception:
        return {"faithful": 1, "complete": 1, "cited": False, "issues": ["unparseable critique"]}


def _reflect(crit: dict) -> str:
    fixes = []
    if crit["faithful"] < 4:
        fixes.append("drop claims not entailed by a cited quote; only state what sources support")
    if crit["complete"] < 4:
        fixes.append("answer every sub-question; check each against sources")
    if not crit["cited"]:
        fixes.append("attach [n] to every factual sentence using only shown source numbers")
    fixes.extend(f"issue: {i}" for i in crit["issues"][:3])
    return "FIX PLAN: " + "; ".join(fixes)


async def run_agent(db, query: str, user_id: str, scope: str = "both",
                    doc_ids: list[str] | None = None, top_k: int = 8,
                    history: list[dict] | None = None, emit=None) -> dict:
    """Run the reflect loop. emit(node, status) called for SSE progress. Returns
    {answer, citations, trace, iters, llm_calls}."""
    t_start = time.perf_counter()
    trace: list = []
    history = history or []
    calls = {"n": 0}

    async def _emit(node: str, status: str):
        _trace(trace, node, int((time.perf_counter() - t_start) * 1000), status)
        if emit is not None:
            await emit(node, status)

    def over_budget() -> bool:
        return (time.perf_counter() - t_start) > TIME_BUDGET_S

    # RETRIEVE
    t0 = time.perf_counter()
    hits = await retrieval.retrieve(db, query, user_id, scope, doc_ids, max(top_k, 10))
    _trace(trace, "RETRIEVE", int((time.perf_counter() - t0) * 1000), f"{len(hits)} hits")
    if emit is not None:
        await emit("RETRIEVE", "done")
    if not hits:
        return {"answer": settings.ABSTAIN_TEXT, "citations": [], "trace": trace, "iters": 0, "llm_calls": 0}

    # GRADE (+ optional REWRITE retry)
    grades, tries = [], 0
    while True:
        t0 = time.perf_counter()
        grades = await _grade(query, hits)
        calls["n"] += 1
        _trace(trace, "GRADE_DOCS", int((time.perf_counter() - t0) * 1000),
               f"kept {sum(1 for g in grades if g.get('score', 0) >= GRADE_KEEP)}/{len(grades)}")
        if emit is not None:
            await emit("GRADE_DOCS", "done")
        kept = [h for h, g in zip(hits, grades) if g.get("score", 0) >= GRADE_KEEP]
        if kept or tries >= REWRITE_TRIES or over_budget():
            hits = kept or hits  # fall through with best available; empty only if no hits at all
            if not kept:
                return {"answer": settings.ABSTAIN_TEXT, "citations": [], "trace": trace,
                        "iters": 0, "llm_calls": calls["n"]}
            break
        tries += 1
        reasons = "; ".join(f"[{g.get('id')}] {g.get('reason', '')}" for g in grades)
        t0 = time.perf_counter()
        alts = await _rewrite(query, reasons)
        calls["n"] += 1
        _trace(trace, "REWRITE_QUERY", int((time.perf_counter() - t0) * 1000), alts[0][:120])
        if emit is not None:
            await emit("REWRITE_QUERY", "done")
        t0 = time.perf_counter()
        hits = await retrieval.retrieve(db, alts[0], user_id, scope, doc_ids, max(top_k, 10))
        _trace(trace, "RETRIEVE", int((time.perf_counter() - t0) * 1000), f"retry: {len(hits)} hits")

    # GENERATE -> CRITIQUE -> REFLECT (max MAX_ITERS retries)
    feedback, iters = "", 0
    draft = ""
    while True:
        t0 = time.perf_counter()
        draft = await _generate(query, hits, history, feedback)
        calls["n"] += 1
        _trace(trace, "GENERATE", int((time.perf_counter() - t0) * 1000), f"iter {iters}")
        if emit is not None:
            await emit("GENERATE", "done")
        t0 = time.perf_counter()
        crit = await _critique(query, draft, hits)
        calls["n"] += 1
        _trace(trace, "CRITIQUE", int((time.perf_counter() - t0) * 1000),
               f"faithful={crit['faithful']} complete={crit['complete']} cited={crit['cited']}")
        if emit is not None:
            await emit("CRITIQUE", "done")
        if (crit["faithful"] >= 4 and crit["complete"] >= 4 and crit["cited"]) or iters >= MAX_ITERS or over_budget():
            if iters >= MAX_ITERS or over_budget():
                if not (crit["faithful"] >= 4 and crit["complete"] >= 4 and crit["cited"]):
                    return {"answer": settings.ABSTAIN_TEXT, "citations": [], "trace": trace,
                            "iters": iters, "llm_calls": calls["n"]}
            break
        feedback = _reflect(crit)
        _trace(trace, "REFLECT", 0, feedback[:200])
        iters += 1

    answer, cites = cit.verify(draft, hits)  # agent cannot bypass verifier
    return {"answer": answer, "citations": cites, "trace": trace, "iters": iters, "llm_calls": calls["n"]}
