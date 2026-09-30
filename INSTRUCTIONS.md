# Demo / showcase run guide. Keep this file simple. Updated after every plan.

## You need running (separate terminals)

> After a reboot/sleep: containers auto-restart, but the host processes do not.
> Restart Ollama (`ollama serve`), the API (step 3) and the UI (step 4) — that
> fixes most "Failed to fetch" errors (curl `http://localhost:8000/health` first).

1. **Ollama** (local LLM, free) — serves `llama3.1:8b-instruct-q4_K_M`
   ```powershell
   ollama serve
   ollama list   # must show llama3.1:8b-instruct-q4_K_M  46e0c10c039e
   ```
   Keep running. API at `http://localhost:11434`.

2. **Docker infra** (free images: postgres, qdrant, redis, minio)
   ```powershell
   docker compose up -d postgres qdrant redis minio
   ```
   Check: `http://localhost:6333/dashboard` (Qdrant), `http://localhost:9001` (MinIO: minioadmin/minioadmin).
   First time only: `cd backend; python -m app.init_db` (creates Postgres tables; compose `api` runs it automatically).
   Note: inside compose, the API reaches host Ollama via `http://host.docker.internal:11434`
   (set `OLLAMA_BASE_URL` accordingly in `.env` when running the API in docker).

3. **Backend API** (terminal 2)
   ```powershell
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload --port 8000
   ```
   Check: `http://localhost:8000/health` and `http://localhost:8000/docs`.

4. **Frontend UI** (terminal 3)
   ```powershell
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:3000/login`.
   Routes: `/login` → `/chat` (sidebar: sessions/knowledge/admin) → `/chat/[id]` thread with
   streaming + clickable `[n]` citations + thumbs/copy/regenerate/report → `/knowledge` uploader
   → `/admin` hit-rate/latency/helpfulness. Typecheck: `npx tsc --noEmit`. Prod build: `npm run build`.

## Demo in order (2 min)

1. Signup at `/login` (any email, password min 8) → you land on chat.
2. Upload files at `/knowledge` (any `.txt/.pdf/.csv/.png/.mp3`, 100MB cap) → status polls to `ready`.
3. Ask in the thread → answer streams with clickable citations `[1]` → popover shows quote + file + page + Open source. Toggle `agent` mode for the self-reflective loop (node badges show progress).
4. Thumbs up/down, copy, regenerate (fresh), report/correct under every answer. Re-ask a question → `cached` badge, no LLM call.
5. `/admin` shows hit-rate, LLM calls avoided, latency, helpfulness.

## Full-stack demo (needs API + Postgres + Ollama)

```powershell
python scripts/seed_kb.py                 # 3 global docs -> seed_manifest.json
powershell -ExecutionPolicy Bypass -File scripts/demo.ps1   # 7 gates, must print DEMO 7/7 GREEN
# bash twin: bash scripts/demo.sh
```

## Evals (no servers needed)

```powershell
python evals/make_gold.py          # rebuild corpus.json + gold_qa.jsonl (56 Q, 10 docs)
python evals/run_chunk_bench.py    # benchmark 5 chunkers → evals/chunking_report.md
cd backend
python -m pytest tests -q          # full suite: auth + ingest + chunkers + chat/citations
```

Chunker choice at runtime: `CHUNK_STRATEGY` env (`fixed|recursive|semantic|proposition|layout`, default `recursive`).
Bench winner: **layout** — see `evals/chunking_report.md` for the full table and tie-break rule.

## Real-model smoke (needs ollama serve + pulls below)

```powershell
ollama pull llama3.1:8b-instruct-q4_K_M
ollama pull nomic-embed-text       # 768d embeddings for Qdrant dense retrieval
python scripts/smoke04.py          # signup → upload → ingest → cited chat, all real, no mocks
```
LLM answers take ~20s on CPU (8B Q4). Hash-embedding fallback engages only if Ollama is unreachable (watch stderr).
Repeat a question to see `cached:true` + tier (`exact`/`semantic`) and zero new LLM latency; `GET /api/admin/stats` shows hit-rate.
Regenerate fresh with `"fresh": true` in the chat body.
Agent mode: `"mode": "agent"` in the chat body → streams `node` events (RETRIEVE/GRADE/REWRITE/GENERATE/CRITIQUE/REFLECT) with full trace persisted per message.
Feedback: `POST /api/feedback {message_id, rating, comment?, corrected_answer?}` → nightly `python scripts/rollup_feedback.py [--write-candidates]`.

## Notes

- `.env` is local-only (copied from `.env.example`). LLM defaults to local Ollama — no cloud key needed.
- Uploads go to `data/uploads/` locally; Qdrant upsert is best-effort (works fully when docker infra is up).
- Current status: **Plans 01–10 complete** — full system verified: 44/44 pytest, bench gate PASS, `DEMO 7/7 GREEN` on Postgres+Qdrant+Ollama.
- UI: **Nocturne Console redesign** (tokens → skeleton → components → pages; `tsc` + `next build` green).

## Native Windows build (no Docker) — architecture mapping
Verified by code inspection against this repo; no functionality changes.

| Docker service | Native equivalent | Status |
|---|---|---|
| `postgres:15` | SQLite file (`DATABASE_URL=sqlite+aiosqlite:///./rag.db`) | Proven: full suite + `smoke04.py` run on sqlite |
| `qdrant` | Qdrant Windows binary on `localhost:6333` | Required for dense retrieval; all Qdrant call sites are best-effort with Postgres-lexical fallback |
| `redis` | Dropped (unused at runtime) | Only referenced as Celery broker default, health probe, and “swap point” comments; cache is Postgres + in-process memory |
| `minio` | Dropped (unused at runtime) | Config keys only — zero code references; blobs live in `data/uploads/` |
| `api` / `worker` / `ui` | `uvicorn` in venv / not started (inline `/process` covers it) / `npm run dev` | Identical behavior |

Native env overrides (vs `.env.example` docker defaults): `DATABASE_URL` → sqlite path above;
`OLLAMA_BASE_URL=http://localhost:11434` (no `host.docker.internal` natively);
`QDRANT_URL=http://localhost:6333` unchanged. `REDIS_URL`/S3 keys inert.

## Native quickstart (verified 2026-09-30, timings on this machine)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_prereqs.ps1  # all green required
python -m venv .venv; .\.venv\Scripts\pip install -r backend/requirements.txt  # ~14s + ~139s
$env:DATABASE_URL="sqlite+aiosqlite:///./rag.db"; cd backend; ..\.venv\Scripts\python -m app.init_db  # ~23s
..\.venv\Scripts\python -m pytest tests -q -p no:cacheprovider  # 44/44, ~105s
# qdrant: unzip tools/qdrant (v1.19.1) + run qdrant.exe  (~100s download once)
powershell -ExecutionPolicy Bypass -File scripts/run_native.ps1  # api+ui up, health-gated
python scripts/seed_kb.py                                        # 3 docs ready
powershell -ExecutionPolicy Bypass -File scripts/demo.ps1        # 7/7 (see health note)
```

Qdrant native binary: `qdrant-x86_64-pc-windows-msvc.zip` v1.19.1 from GitHub
releases, extracted to `tools/qdrant/` (gitignored — each machine downloads its own).
`/health` gates `ok` on db+qdrant; redis is reported but informational (nothing requires it).
