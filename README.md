# Multimodal Self-Reflective RAG — Production Build

> Answers questions from a curated knowledge base + user-uploaded multimodal documents of any format.
> Per-user login with persistent sessions, semantic repeat-query cache to cut LLM cost,
> benchmarked chunking, self-reflective agent, citations + feedback, production-grade UI.

## 1. What this builds

| Capability | Requirement |
|---|---|
| KB Q&A | Ask over pre-seeded knowledge base |
| Multimodal upload Q&A | PDF, DOCX, PPTX, TXT, MD, HTML, CSV, XLSX, images (PNG/JPG), audio (MP3/WAV), video (MP4) — ask on top |
| Per-user sessions | Login, session list, persistent history, resume, rename/delete, isolation |
| Repeat-query intelligence | Exact + semantic cache, near-duplicate reuse, invalidation, savings dashboard |
| Chunking analysis | Implement 5 strategies, benchmark, pick winner (default: hybrid recursive + small-to-big + layout) |
| Self-reflective agent | Retrieve → Grade → Rewrite → Generate → Critique → Reflect loop (max 2), with traces |
| Citations + feedback | Every claim cited to `[doc:page:chunk/quote]`; thumbs/comment/correction per response |
| Production UI | Next.js + shadcn, streaming, citation popovers, uploader, admin |

## 2. Architecture (target)

```text
                    +------------------+
                    |  Next.js 14 UI   |  /login /chat/[id] /knowledge /admin
                    +--------+---------+
                             | HTTPS/SSE (JWT)
                    +--------v---------+
                    |  FastAPI backend |  auth, sessions, docs, chat, cache, feedback
                    +--+---+---+---+---+
                       |   |   |   |
        +--------------+   |   |   +--------------+
        |                  |   |                  |
 +------v-----+   +--------v---v--------+   +-----v------+
 | Postgres 15|   | Qdrant 1.x + BM25   |   | Redis 7    |
 | users,     |   | text-v1, image-v1   |   | exact +    |
 | sessions,  |   | payload: user/scope |   | semantic   |
 | messages,  |   | doc/page/bbox/parent|   | cache, queue|
 | docs, cache|   +----------+----------+   +-----+------+
 | feedback   |              |                    |
 +------------+   +----------v----------+   +-----v------+
                  | Celery/RQ worker    |   | MinIO/S3   |
                  | parse→chunk→embed→  |   | raw blobs  |
                  | index               |   |            |
                  +---------------------+   +------------+
                  | LiteLLM router: OpenAI/Anthropic/Ollama |
                  | Embed: BGE-M3/E5  Rerank: bge-reranker  |
                  | Observability: Langfuse + Prometheus    |
                  +-----------------------------------------+
```

Collection strategy: `text-v1` (dense 1024d, HNSW m=16, ef=128) + sparse BM25 sidecar; `image-v1` (CLIP 512d) for image-native search, linked by `parent_id`.

## 3. Repository layout (to be built)

```text
/ (this dir)
  README.md                  <- you are here (orchestration)
  docker-compose.yml         <- Plan 10 (postgres, qdrant, redis, minio, api, worker, ui)
  .env.example               <- Plan 10
  backend/
    app/{main,config,deps,routers/{auth,sessions,documents,chat,feedback,admin},models,schemas,services/{retrieval,generation,cache,agent,citations},chunkers,parsers,workers}
    tests/
  frontend/
    app/(auth)/login  app/(app)/chat/[id]  app/(app)/knowledge  app/(app)/admin
    components/{chat,uploader,citations,feedback,sidebar}
  worker/  (or backend/app/workers)
  evals/{datasets,gold_qa.jsonl,run_chunk_bench.py,ragas_eval.py,results/}
  plans/00..10               <- detailed step-by-step suites (start here)
```

Nothing under `backend/`, `frontend/`, `evals/` exists yet — intentional. Plans define exact files to create.

## 4. Orchestration — build order (DAG)

```text
P01 Foundations/Auth/Sessions ──┐
                                ├─→ P04 Retrieval/Gen/Citations ─→ P08 UI MVP ─→ P05 Cache ─→ P06 Agent ─→ P07 Feedback ─→ P09 Harden
P02 Multimodal Ingestion ───────┤
P03 Chunking Benchmark ─────────┘         P10 Orchestration/Deploy runs in parallel from P04 onward
```

| Phase | Plan file | Depends | Exit gate (must pass before next) |
|---|---|---|---|
| 0 | `plans/00-overview-architecture.md` | — | Stack frozen (Qdrant vs pgvector, LLM provider) |
| 1 | `plans/01-foundations-auth-sessions.md` | 0 | Login + 2 sessions persist + isolation test green |
| 2 | `plans/02-multimodal-ingestion.md` | 1 | 1× PDF/DOCX/IMG/MP3 ingested, status API, payload filter |
| 3 | `plans/03-chunking-strategy-analysis.md` | 1,2 | `evals/chunking_report.md` with Recall@5 winner |
| 4 | `plans/04-retrieval-generation-citations.md` | 2,3 | Every answer has ≥1 verified quote, SSE works |
| 5 | `plans/08-production-ui.md` (MVP slice) | 1,4 | Chat + upload + citations clickable, Lighthouse >85 |
| 6 | `plans/05-repeat-query-cache.md` | 4 | 2nd identical query <300ms, no LLM call, hit-rate logged |
| 7 | `plans/06-self-reflective-agent.md` | 4,5 | Unanswerable triggers rewrite, trace saved |
| 8 | `plans/07-feedback-eval-loop.md` | 4,6 | Thumbs/comment stored, dashboard shows helpfulness |
| 9 | `plans/09-hardening-deploy.md` | all | Docker up, CI eval gate, rate-limit + redaction on |
| 10 | `plans/10-orchestration-runbook.md` | 0+ | `docker compose up` brings full stack, demo script passes |

**Commands (after execution begins — DO NOT run yet):**

```powershell
# 1. infra
docker compose up -d postgres qdrant redis minio
# 2. backend
cd backend; python -m venv .venv; .\.venv\Scripts\Activate; pip install -r requirements.txt
alembic upgrade head; uvicorn app.main:app --reload
# 3. worker (second terminal)
celery -A app.workers.celery_app worker --loglevel=info -Q ingest,eval
# 4. frontend (third terminal)
cd frontend; npm install; npm run dev
# 5. evals
python evals/run_chunk_bench.py --strategies all --dataset evals/gold_qa.jsonl
```

## 5. Plan index — read in this order

1. `plans/00-overview-architecture.md` — frozen decisions, schemas, API surface, conventions.
2. `plans/01-foundations-auth-sessions.md` — DB, JWT, session APIs.
3. `plans/02-multimodal-ingestion.md` — parser router, normalizer, worker, storage.
4. `plans/03-chunking-strategy-analysis.md` — 5 chunkers, harness, metrics, winner rule.
5. `plans/04-retrieval-generation-citations.md` — hybrid retrieval, rerank, cited generation, verifier.
6. `plans/05-repeat-query-cache.md` — exact/semantic/near-dup, invalidation, savings.
7. `plans/06-self-reflective-agent.md` — LangGraph nodes, prompts, loop guards, traces.
8. `plans/07-feedback-eval-loop.md` — feedback API, dashboard, active learning.
9. `plans/08-production-ui.md` — routes, components, streaming, a11y/perf budgets.
10. `plans/09-hardening-deploy.md` — security, observability, tests, deploy.
11. `plans/10-orchestration-runbook.md` — compose, env, seeds, demo script, troubleshooting.

## 6. Global conventions (binding on all plans)

* IDs: `uuid7`/`uuid4`; time UTC ISO-8601; money/tokens logged per message.
* Auth: `Authorization: Bearer <JWT>`; all `/api/*` except `/health`, `/auth/login`, `/auth/signup` require JWT; vector queries MUST filter `scope in ('global', 'user:{sub}')`.
* Citations: `[{id, doc_id, filename, page, bbox?, ts?, quote, score}]`; UI renders `[1]`.
* Errors: `{detail, code, trace_id}`; worker retries 3× exponential.
* Config: everything via env (`.env.example` canonical); no secrets in code.
* LLM access ONLY via `backend/app/services/llm.py` (LiteLLM wrapper) so cache/eval/cost hooks apply.

## 7. Status

* [x] Repo initialized (`main`), `.gitignore`, `README.md`, `plans/00..10` written.
* [ ] Execution NOT started — awaiting your approval to begin Plan 01.
* Next action on your approval: scaffold `docker-compose.yml`, `.env.example`, backend skeleton per Plan 01 Step 1.
