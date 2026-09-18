# Plan 05 — Intelligent Repeat-Query Handling (Semantic Cache)

## 5.1 Objective
Serve repeated/paraphrased questions without repeat LLM/retrieval cost. Target 30–60% LLM call reduction on real usage.

## 5.2 Design (3 layers, exact thresholds)

| Layer | Key | Hit rule | Action | TTL |
|---|---|---|---|---|
| L1 Exact | `sha256(norm(query)+filters_hash+scope)` | exact Redis key | return cached answer+citations, `cached:true`, `hits++` | 24h |
| L2 Semantic | BGE-M3 embedding of norm query | `cosine ≥0.97` AND same `filters_hash` | same as L1, mark `semantic:true` | 24h |
| L3 Near-dup | `0.90 ≤ cosine < 0.97` | reuse `retrieved doc_ids` | skip rewrite+dense, run rerank+generate only (or ask `Did you mean "…"?` if UI flag) | — |

* `norm(q)`: lowercase, strip punct/extra ws, Unicode NFKC. `filters_hash = sha256(scope+sorted(doc_ids)+top_k+model)`.
* Store: Redis (hot, TTL) + Postgres `query_cache` (durable, `embedding`, `response`, `citations`, `doc_ids`, `hits`, `expires_at`). Write-through on every uncached answer.
* Invalidation (binding): on doc delete/re-index, `DELETE FROM query_cache WHERE doc_ids @> [doc_id]` + `DEL redis keys *{doc_id}*`; doc update bumps version. Scope change invalidates user rows.

## 5.3 Steps
1. `backend/app/services/cache.py`: `norm_query()`, `filters_hash()`, `exact_get/put`, `semantic_get/put` (Qdrant-adjacent cosine via pgvector `ORDER BY embedding <=> %s LIMIT 1` or in-Redis RediSearch — pick pgvector, simpler), `near_dup_reuse()`.
2. Wire into `routers/chat.py` BEFORE retrieval: L1→L2→(L3 flag)→proceed. AFTER generation: `put` both layers. Every hit logs `cached=true, saved_tokens`.
3. `GET /api/admin/stats`: `{cache_hit_rate_24h, exact_hits, semantic_hits, est_usd_saved (=tokens_saved × model_rate)}`.
4. Negative-cache: unanswerable (`I don't know...`) cached with shorter TTL 1h (prevents LLM hammer on gaps, still refreshes).
5. Tests: identical Q 2nd-hit <300ms no LLM (mock llm counter); paraphrase (≥0.97 fixture pair) hits L2; different `doc_ids` filter does NOT hit; delete doc invalidates.

## 5.4 Acceptance
* [ ] Re-ask same Q → `cached:true`, SSE completes <300ms, LLM call count unchanged.
* [ ] Paraphrase pair in `tests/fixtures/paraphrases.jsonl` → L2 hit.
* [ ] After doc delete, previously cached Q depending on it → miss (re-retrieves).
* [ ] Dashboard shows hit-rate + $ saved; 7-day load test shows ≥30% hit-rate on repeated-question workload.

## 5.5 Effort / risks
1–2 days. Risk: false-positive semantic hit (wrong answer reused) → mitigate with high 0.97 threshold + `filters_hash` equality + user-visible `cached` badge + `regenerate` bypass (`?fresh=true`).
