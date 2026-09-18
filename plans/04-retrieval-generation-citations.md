# Plan 04 — Hybrid Retrieval + Cited Generation

## 4.1 Objective
Turn indexed chunks into correct, cited, streamed answers. Every factual sentence traceable to a stored quote.

## 4.2 Prerequisites
Plans 02+03 done (vectors populated with winner chunker).

## 4.3 Steps

**Step 1 — Embed service (`backend/app/services/embed.py`):**
* `embed_texts(texts: list[str]) -> list[list[float]]` via BGE-M3 (batch 32, L2-normalize, truncate 8192). Cache model in memory; timeout 30s; retry 2×.
* `embed_image(path) -> vector` via CLIP (only for image-v1).

**Step 2 — Retrieval (`backend/app/services/retrieval.py`):**
```python
async def retrieve(query: str, user_id: str, scope: str='both', doc_ids: list|None, top_k: int=8) -> list[Hit]
# Hit{chunk_id, doc_id, filename, page, bbox, ts, text(parent window), child_text, dense_score, sparse_score, fused_score}
```
* Pipeline (exact order): (a) query rewrite (lowercase, strip; LLM rewrite ONLY if agent mode — else raw, to save cost); (b) dense Qdrant `search(text-v1, top 20, filter scope)` + sparse BM25 (`tantivy` local or `Qdrant sparse` — pick one, document); (c) RRF fuse `k=60`; (d) rerank top-20→`RERANK_TOP_N=5` with bge-reranker (cross-encoder, 512 tok cap); (e) small-to-big expand: if hit is child, fetch parent text for prompt but keep child id for citation; (f) scope enforce: `must scope in [global, user:{id}]` (+ `doc_ids` if provided).
* Return `fused_score`, never raw embedding distances to client.

**Step 3 — Generation (`backend/app/services/llm.py`, `generation.py`):**
* Single entry `acomplete(messages, model, stream, trace_id) -> (tokens, latency)` via LiteLLM; logs to Langfuse.
* System prompt (canonical, do not paraphrase without eval):
```text
You answer ONLY from CONTEXT. Each factual sentence ends with [n] matching SOURCES.
If CONTEXT lacks the answer, say exactly: "I don't know based on the knowledge base."
Never invent page numbers. Keep quotes verbatim under 40 words.
```
* User message: `QUESTION: {q}\n\nCONTEXT:\n[1] (doc={fn} p={page}) {text}\n...` + history (last 6 messages, truncated 3000 tok).
* Output contract: model returns markdown answer with `[1][2]` markers; backend maps to `citations[]`. Temperature 0.1, max_tokens 800.

**Step 4 — Citation verifier (`backend/app/services/citations.py`):**
* `verify(answer, hits) -> citations[]`: for each `[n]`, check quoted span (fuzzy ≥0.85) exists in hit text; drop sentences with no support (replace with `I don't know...` fragment if all dropped); enforce quote ≤40 words; attach `bbox/ts` from hit.
* Persist `messages.citations` JSONB + `tokens_in/out, latency_ms, model`.

**Step 5 — Chat API (`backend/app/routers/chat.py`):**
* `POST /api/chat {session_id, query (1..2000 chars), filters?, top_k?}`: auth → verify session ownership → write user message → `retrieve()` → `generate(stream)` → SSE `delta` events → final `done{answer,citations,model,latency}` → write assistant message → update `sessions.updated_at` + auto-title if first.
* Guards: rate limit 30/min/user (slowapi), empty retrieval → immediate `I don't know...` with `citations:[]` (no LLM call — cost save).
* Errors: retrieval fail → 503 `retrieval_unavailable`; LLM fail → 502 `llm_unavailable` with `trace_id`.

**Step 6 — Tests:** `test_retrieval.py` (scope isolation, RRF determinism, rerank cap), `test_citations.py` (hallucinated page rejected, fuzzy quote passes, all-unsupported → abstain), `test_chat.py` (SSE shape, ownership 404, empty-retrieval no-LLM).

## 4.4 Acceptance
* [ ] Gold 50 Q: faithfulness ≥0.80, citation precision ≥0.85 (RAGAS or judge).
* [ ] Every assistant message in DB has `citations[]` with resolvable `doc_id+page`; UI click-through works (Plan 08 stub).
* [ ] Unanswerable Q returns exact abstain string, 0 hallucinated citations.
* [ ] p50 chat latency (top_k=8, rerank 5) <6s uncached on CPU embeddings.

## 4.5 Effort / risks
3 days. Risk: reranker latency → make `RERANK_ENABLED` flag; BM25 complexity → start with Qdrant sparse, fallback `pg_trgm`.
