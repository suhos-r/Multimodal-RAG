# Plan 06 — Self-Reflective RAG Agent (LangGraph)

## 6.1 Objective
Replace single-shot retrieve→generate with a reflecting loop that grades, rewrites, and critiques itself (max 2 retries), with full traces. Reduces hallucinations on poor retrieval.

## 6.2 State machine (canonical, implement exactly)

```text
START → RETRIEVE → GRADE_DOCS ──all irrelevant──→ REWRITE_QUERY → RETRIEVE (retry ≤1)
              │ relevant (≥1 score≥0.6)
              v
          GENERATE → CRITIQUE {faithful 1-5, complete 1-5, cited bool}
              │ score≥4 and cited → CITE → END
              │ else → REFLECT (produce fix plan) → REGENERATE (≤2) → CRITIQUE ...
              │ exhausted → ABSTAIN ("I don't know based on the knowledge base.")
```

State (`AgentState` TypedDict): `{query, rewritten_query, hits[], draft, critique{...}, reflections[], iters, citations[], trace[]}`. Every node appends `{node, at, in_tokens, out_tokens, ms}` to `trace[]`, persisted to `messages.agent_trace`.

## 6.3 Node specs

* **RETRIEVE**: calls Plan 04 `retrieve()` (top_k=10 in agent mode for headroom). Log hit count.
* **GRADE_DOCS** (LLM classifier, temp 0, 1 call for all hits batched): prompt `Score each SOURCE 0-1 for relevance to QUESTION. Return JSON [{id,score,reason}].` Keep `score≥0.5`; if none ≥0.5 → rewrite path.
* **REWRITE_QUERY** (LLM, temp 0.3): `Original Q + grader reasons → 2 alternative queries (keywords, synonyms, split multi-hop into sub-Q).` Try alt-1, then alt-2 if still empty.
* **GENERATE**: Plan 04 prompt + `PREVIOUS CRITIQUE + REFLECTION` appended on retry (so it fixes, not repeats).
* **CRITIQUE** (LLM judge, temp 0): rubric `faithful: every sentence entailed by cited quote? complete: all sub-Q answered? cited: every claim has [n]?` → `{faithful, complete, cited, issues[]}`. Fail if `faithful<4 or complete<4 or !cited`.
* **REFLECT**: rule+LLM: map issues → actions (`drop hit 3 (off-topic)`, `need table from p.4`, `split answer into bullets`). Max 2 reflections.
* **CITE**: Plan 04 verifier (binding — agent cannot bypass).
* Guards: `MAX_ITERS=2`, total LLM calls ≤6, total time ≤45s; exceed → abstain + trace.

## 6.4 Steps
1. `backend/app/services/agent/{graph.py,nodes.py,prompts.py,state.py}` with LangGraph `StateGraph`; feature flag `AGENT_ENABLED` + per-request `mode: 'fast'|'agent'` (default fast; UI toggle + auto-escalate: fast faithfulness <threshold → agent retry).
2. Wire `routers/chat.py`: `if mode==agent or ?agent=true → run graph`, stream `node_status` events over SSE (`{"node":"GRADE_DOCS","status":"..."}`) then token deltas.
3. Tests: (a) good retrieval → 1 pass, no rewrite; (b) poisoned retrieval (inject irrelevant) → rewrite triggered; (c) unanswerable → abstain after ≤2 iters; (d) trace length + token accounting correct; (e) agent never returns uncited claims (verifier).

## 6.5 Acceptance
* [ ] Adversarial suite (10 poor-retrieval Q): agent abstains or corrects ≥8/10 vs fast baseline ≤5/10.
* [ ] Every agent answer stores `agent_trace[]` viewable in admin/debug drawer.
* [ ] Cost guard: p95 agent calls ≤6 LLM, ≤45s; flag-off returns to fast path with zero regression.

## 6.6 Effort / risks
2–3 days. Risk: latency/cost doubling → default fast, agent opt-in + auto-escalate only; cache (Plan 05) applies to final agent answers too.
