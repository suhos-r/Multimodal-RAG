# Plan 03 — Chunking Strategy Analysis (Benchmark → Winner)

## 3.1 Objective
Implement 5 chunkers behind one interface, benchmark on a gold set, and freeze the production default with evidence. No guessing.

## 3.2 Interface (binding, `backend/app/chunkers/base.py`)

```python
class Chunk(BaseModel):
    chunk_id: str  # f"{doc_id}:{ordinal:04d}"
    parent_id: str | None
    text: str
    page: int | None; bbox: dict | None; ts: list | None
    modality: str; token_count: int
    meta: dict = {}
class Chunker(Protocol):
    name: str
    def chunk(self, blocks: list[CanonicalBlock], doc_id: str) -> list[Chunk]: ...
```

All chunkers input `CanonicalBlock[]` (Plan 02), output `Chunk[]` with `token_count` via `tiktoken cl100k`.

## 3.3 Strategies to implement (`backend/app/chunkers/*.py`)

1. **fixed.py** — `FIXED_SIZE=500, OVERLAP=100` tokens, sentence-safe (never cut mid-sentence unless >500).
2. **recursive.py** — LangChain-style `RecursiveCharacterTextSplitter(chunk_size=800, overlap=150, separators=["\n\n","\n",". ","? ","! "," ",""])`, carries `page/bbox` by majority overlap.
3. **semantic.py** — embed sentences (BGE-M3), greedy breakpoint where `cosine < 0.75` or `max 1000 tok`; `SEM_BREAKPOINT=0.75, SEM_MAX=1000`.
4. **proposition.py (small-to-big)** — LLM or rule splits blocks into atomic propositions (child ≤120 tok, `parent_id` = 800-tok window); index BOTH, retrieve child but serve parent. `PROP_MAX=120`.
5. **layout.py** — one chunk per `page/section/slide/table`; tables never split (markdown kept whole, cap 2000 tok, overflow by rows with header repeat); images/audio segments are atomic.

## 3.4 Benchmark harness (binding)

* Dataset `evals/gold_qa.jsonl` — 50 items minimum: `{id, question, doc_ids, gold_answer, gold_chunk_ids[], answerable:bool}` covering PDFs w/ tables, slides, image Q, audio Q, unanswerable (5).
* Runner `evals/run_chunk_bench.py --strategies fixed,recursive,semantic,proposition,layout --top_k 8`: for each Q, chunk corpus with that strategy → embed → retrieve top-8 → compute:
  * `Recall@5`, `MRR`, `citation_precision` (gold_chunk overlap), `faithfulness` (RAGAS or LLM-judge 0-1), `avg_tokens/chunk`, `index_time`.
* Output `evals/results/chunk_bench_{ts}.json` + `evals/chunking_report.md` with table + winner rule: **highest Recall@5; tie-break faithfulness; must not exceed 1.5× p50 latency of recursive**.
* Deterministic: seed 42, same embed model, same top_k.

## 3.5 Steps
1. Implement `base.py + 5 chunkers + __init__.py registry {name: class}` with unit tests on synthetic blocks (overlap math, table atomicity, parent linkage).
2. Build 50-Q gold set (curate from fixtures + KB seeds; include 5 unanswerable).
3. Run matrix, generate report.
4. Freeze default in `config.py`: `CHUNKER_DEFAULT=<winner>`; code path `worker/tasks.py` calls registry.
5. Keep all chunkers (flag-switchable `CHUNK_STRATEGY` env) for future A/B.

## 3.6 Expected outcome & pre-registered recommendation
Ship **hybrid default**: `recursive (800/150) as parent + proposition children (small-to-big retrieval) + layout guard (never split tables/images)` — historically best Recall+faithfulness/cost tradeoff. If bench contradicts, bench wins (update this file with ADR + numbers). Semantic alone rarely wins on cost; keep as opt-in for wiki-style KB.

## 3.7 Acceptance
* [ ] 5 chunkers pass unit tests (overlap, parent_id integrity, table atomicity).
* [ ] `run_chunk_bench.py` completes, `chunking_report.md` committed with full table + winner + latency.
* [ ] Default set in config; re-ingest of fixtures uses default; retrieval Recall@5 ≥ baseline fixed +10% or documented why not.

## 3.8 Effort
2–3 days (1 day gold-set curation). Risk: gold-set bias → mitigate with doc-type stratification (≥10 table Q, ≥5 image/audio Q).
