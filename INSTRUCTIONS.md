# Demo / showcase run guide. Keep this file simple. Updated after every plan.

## You need running (separate terminals)

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
- Current status: **Plans 01–08 complete** (auth/sessions, multimodal ingestion, chunking bench, cited chat, cache, agent, feedback, full UI). Remaining: Plan 09 hardening (rate-limit global, CI eval gate) + Plan 10 compose deploy — out of the requested 4–8 scope.
