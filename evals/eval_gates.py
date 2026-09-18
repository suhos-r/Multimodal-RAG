"""CI eval gate (no LLM, no servers): re-runs the chunking bench and asserts
quality floors. Exit non-zero -> CI merge blocked.

Gates:
1. winner recall@5 >= 0.90 (retrieval must actually work)
2. fixed.clean_break < recursive.clean_break (boundary-respect regression guard)
3. every strategy indexes > 0 chunks (pipeline integrity)
Run:  python evals/eval_gates.py
"""
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
MIN_RECALL = 0.90


def main() -> int:
    before = set(glob.glob(str(HERE / "results" / "chunk_bench_*.json")))
    r = subprocess.run([sys.executable, str(HERE / "run_chunk_bench.py")], capture_output=True, text=True)
    print(r.stdout[-2000:])
    if r.returncode != 0:
        print("GATE FAIL: bench crashed\n", r.stderr[-2000:])
        return 1
    after = sorted(set(glob.glob(str(HERE / "results" / "chunk_bench_*.json"))) - before)
    if not after:
        print("GATE FAIL: no results file produced")
        return 1
    rows = json.loads(Path(sorted(after)[-1]).read_text(encoding="utf-8"))
    by = {row["strategy"]: row for row in rows}
    failures = []
    # same winner rule as run_chunk_bench: recall@5 -> MRR -> clean_break -> fewest chunks
    winner = max(rows, key=lambda row: (row["recall@5"], row["mrr"], row["clean_break"], -row["chunks"]))
    if winner["recall@5"] < MIN_RECALL:
        failures.append(f"winner recall@5 {winner['recall@5']} < {MIN_RECALL}")
    if not (by["fixed"]["clean_break"] < by["recursive"]["clean_break"]):
        failures.append("boundary guard: fixed.clean_break should be < recursive.clean_break")
    for row in rows:
        if row["chunks"] <= 0:
            failures.append(f"{row['strategy']} indexed 0 chunks")
    if failures:
        print("GATE FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print(f"GATE PASS: winner={winner['strategy']} recall@5={winner['recall@5']} mrr={winner['mrr']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
