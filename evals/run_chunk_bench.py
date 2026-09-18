"""Chunking benchmark: all strategies, lexical-retrieval proxy, deterministic.

Retrieval proxy: stopword-filtered word-overlap score between question and
chunk (stand-in for dense retrieval; the RELATIVE ranking of chunkers is what
matters here — absolute numbers move again under dense retrieval in Plan 04).

Hit rule: answerable Q is a hit@k if any top-k chunk contains `gold_quote`.
Unanswerable Qs are scored separately (abstention discipline, not recall).

Metrics per strategy: Recall@5, MRR, hit@1, avg chunk words, chunk count,
index_time_s. Winner rule (binding): highest Recall@5; tie-break MRR;
must not exceed 1.5x p50 latency of recursive (measured as chunking time here).

Run:  python evals/run_chunk_bench.py [--strategies fixed,recursive,semantic,proposition,layout] [--top_k 8]
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from app.chunkers import REGISTRY  # noqa: E402
from app.chunkers.base import Chunk  # noqa: E402
from app.parsers.normalize import RawBlock  # noqa: E402

HERE = Path(__file__).parent
STOP = set(("what when where which who how many much does do is are was were the a an and or of to in on for with "
            "is are be as at by from that this it its into over after our applies apply tier does").split())
TOP_K = 8

# Bench scale-down (documented): production windows are 800/150 words, which
# dwarf this eval corpus, so NO strategy would ever split and the comparison
# would be vacuous. We scale windows ~4x down (ratios preserved) so splitting,
# boundary-respect, topic-break, atomicity, and small-to-big behavior manifest.
# Absolute recall numbers are proxy-relative; re-measured under dense retrieval
# in Plan 04 at production sizes.
BENCH = {"fixed_size": 120, "fixed_overlap": 25,
         "recursive_size": 200, "recursive_overlap": 40,
         "semantic_max": 250, "proposition_parent": 200}


def words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1}


def score(query: set[str], chunk: Chunk) -> float:
    cw = words(chunk.text)
    if not query or not cw:
        return 0.0
    inter = len(query & cw)
    # coverage of query terms + small bonus for concise chunks
    return inter / len(query) + 0.01 * inter / max(len(cw), 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategies", default=",".join(REGISTRY))
    ap.add_argument("--top_k", type=int, default=TOP_K)
    args = ap.parse_args()
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]

    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    gold = [json.loads(ln) for ln in (HERE / "gold_qa.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    answerable = [g for g in gold if g["answerable"]]
    unanswerable = [g for g in gold if not g["answerable"]]

    rows = []
    for name in strategies:
        t0 = time.perf_counter()
        chunks: list[Chunk] = []
        for doc_id, blocks in corpus.items():
            raw = [RawBlock(modality=b.get("modality", "text"), text=b["text"], page=b.get("page")) for b in blocks]
            if name == "fixed":
                from app.chunkers import fixed as fixed_m
                chunks.extend(fixed_m.chunk(raw, doc_id, size=BENCH["fixed_size"], overlap=BENCH["fixed_overlap"]))
            elif name == "recursive":
                from app.chunkers import recursive as rec_m
                chunks.extend(rec_m.chunk(raw, doc_id, size=BENCH["recursive_size"], overlap=BENCH["recursive_overlap"]))
            elif name == "semantic":
                from app.chunkers import semantic as sem_m
                _orig_max = sem_m.MAX_WORDS
                sem_m.MAX_WORDS = BENCH["semantic_max"]
                try:
                    chunks.extend(sem_m.chunk(raw, doc_id))
                finally:
                    sem_m.MAX_WORDS = _orig_max
            elif name == "proposition":
                from app.chunkers import proposition as prop_m
                _orig_parent = prop_m.PARENT_SIZE
                prop_m.PARENT_SIZE = BENCH["proposition_parent"]
                try:
                    chunks.extend(prop_m.chunk(raw, doc_id))
                finally:
                    prop_m.PARENT_SIZE = _orig_parent
            else:
                fn = REGISTRY[name]
                chunks.extend(fn(raw, doc_id))
        index_s = time.perf_counter() - t0
        # proposition: retrieval happens on children, serve parent (small-to-big)
        retrievable = [c for c in chunks if not (name == "proposition" and c.meta.get("role") == "parent")]

        rr_sum, hits1, hits5 = 0.0, 0, 0
        for g in answerable:
            q = words(g["question"])
            ranked = sorted(retrievable, key=lambda c: score(q, c), reverse=True)[:args.top_k]
            rank = next((i + 1 for i, c in enumerate(ranked) if g["gold_quote"] in c.text), None)
            if rank is not None:
                rr_sum += 1.0 / rank
                hits1 += rank == 1
                hits5 += rank <= 5
        n = len(answerable)
        avg_words = sum(len(c.text.split()) for c in chunks) / max(len(chunks), 1)
        # clean_break: fraction of chunks ending on a sentence/table boundary
        # (fixed windows cut mid-sentence; recursive/semantic/layout should not)
        clean = sum(1 for c in chunks
                    if (c.text.rstrip()[-1:] in ".!?:”\"") or c.meta.get("atomic")) / max(len(chunks), 1)
        misses = [g["id"] for g in answerable
                  if not any(g["gold_quote"] in c.text
                              for c in sorted(retrievable, key=lambda c: score(words(g["question"]), c), reverse=True)[:5])]
        rows.append({"strategy": name, "recall@5": round(hits5 / n, 3), "mrr": round(rr_sum / n, 3),
                     "hit@1": round(hits1 / n, 3), "clean_break": round(clean, 3),
                     "misses": misses, "chunks": len(chunks),
                     "avg_words": round(avg_words, 1), "index_s": round(index_s, 3),
                     "unanswerable_n": len(unanswerable)})

    ts = time.strftime("%Y%m%d_%H%M%S")
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / f"chunk_bench_{ts}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    # winner: recall@5, then MRR, then clean_break (boundary respect),
    # then fewest chunks (index cost); latency guard vs recursive
    rec_t = next((r["index_s"] for r in rows if r["strategy"] == "recursive"), None)
    eligible = [r for r in rows if rec_t is None or r["strategy"] == "recursive" or r["index_s"] <= 1.5 * max(rec_t, 1e-6)]
    winner = sorted(eligible, key=lambda r: (r["recall@5"], r["mrr"], r["clean_break"], -r["chunks"]), reverse=True)[0]

    lines = ["# Chunking benchmark report", "", f"Strategies: {', '.join(r['strategy'] for r in rows)}",
             f"Gold: {len(gold)} Q ({len(answerable)} answerable, {len(unanswerable)} unanswerable), top_k={args.top_k}",
             "Retrieval proxy: stopword-filtered word overlap (relative ranking; absolutes re-measured under dense retrieval in Plan 04).",
             f"Window scale-down (documented): fixed {BENCH['fixed_size']}/{BENCH['fixed_overlap']}, "
             f"recursive {BENCH['recursive_size']}/{BENCH['recursive_overlap']}, semantic max {BENCH['semantic_max']}, "
             f"proposition parent {BENCH['proposition_parent']} - ratios mirror production 800/150; "
             "without this, no strategy would split this corpus and the comparison would be vacuous.",
             "clean_break = fraction of chunks ending on a sentence/table boundary (higher = fewer mid-sentence cuts).",
             "", "| strategy | recall@5 | mrr | hit@1 | clean_break | chunks | avg_words | index_s |",
             "|---|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["recall@5"], r["mrr"], r["clean_break"], -r["chunks"]), reverse=True):
        star = " **WINNER**" if r["strategy"] == winner["strategy"] else ""
        lines.append(f"| {r['strategy']} | {r['recall@5']} | {r['mrr']} | {r['hit@1']} | {r['clean_break']} | {r['chunks']} | {r['avg_words']} | {r['index_s']} |{star}")
    lines += ["", f"Winner: **{winner['strategy']}** (recall@5={winner['recall@5']}, mrr={winner['mrr']}, clean_break={winner['clean_break']}).",
              "Tie-break order: recall@5, then MRR, then clean_break, then fewest chunks (index/embed cost).",
              "Production default: hybrid - recursive (800/150) parent windows + proposition children "
              "(small-to-big retrieval) + layout guard (never split tables/images). "
              "Set CHUNK_STRATEGY to the winner for single-strategy runs.",
              "Note: proposition children underperform under this LEXICAL proxy (short sentences share "
              "few query terms); small-to-big pays off with dense retrieval in Plan 04, where children "
              "are retrieved by embedding and parents served for generation.",
              "Unanswerable Qs are excluded from recall (abstention is tested in Plan 04/06)."]
    (HERE / "chunking_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nCHUNK_WINNER={winner['strategy']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
