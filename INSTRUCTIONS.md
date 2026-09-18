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

## Demo in order (2 min)

1. Signup at `/login` (any email, password min 8) → you land on chat.
2. Upload a file: `POST /api/documents/upload` (use `/docs` → authorize with JWT) with any `.txt/.pdf/.csv/.png/.mp3` → trigger `POST /api/documents/{id}/process` (worker does this automatically in prod) → poll `GET /api/documents/{id}/status` until `ready`.
3. Chat (Plan 04+, not yet): ask a question → cited answer streams.
4. Re-ask same question → served from cache `<300ms` with `cached:true` badge.

## Evals (no servers needed)

```powershell
python evals/make_gold.py          # rebuild corpus.json + gold_qa.jsonl (56 Q, 10 docs)
python evals/run_chunk_bench.py    # benchmark 5 chunkers → evals/chunking_report.md
cd backend
python -m pytest tests -q          # full suite: auth + ingest + chunkers
```

Chunker choice at runtime: `CHUNK_STRATEGY` env (`fixed|recursive|semantic|proposition|layout`, default `recursive`).
Bench winner: **layout** — see `evals/chunking_report.md` for the full table and tie-break rule.

## Notes

- `.env` is local-only (copied from `.env.example`). LLM defaults to local Ollama — no cloud key needed.
- Uploads go to `data/uploads/` locally; Qdrant upsert is best-effort (works fully when docker infra is up).
- Current status: **Plan 03 done** (5 chunkers benchmarked, winner layout; ingestion uses `CHUNK_STRATEGY`). Chat/citations/cache/agent/UI-full arrive in Plans 04–08.
