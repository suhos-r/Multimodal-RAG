# Plan 10 — Orchestration Runbook (Compose, Env, Demo, Troubleshooting)

## 10.1 Objective
Single source of truth to bring the whole stack up, seed it, demo it, and fix it. If it's not here, it's not supported.

## 10.2 Files to create (on execution, not now)
* `docker-compose.yml` (services + volumes + healthchecks per Plan 09 §9.5).
* `.env.example` (keys = Plan 00 §0.7, values placeholders).
* `backend/alembic/` migrations + `scripts/seed_kb.py` (uploads 5 sample KB docs as `global`).
* `scripts/demo.sh` (the acceptance demo below), `scripts/backup.sh/restore.sh`.

## 10.3 Bring-up (canonical order, PowerShell)

```powershell
cp .env.example .env   # fill JWT_SECRET, OPENAI_API_KEY, S3 keys
docker compose up -d postgres qdrant redis minio
docker compose up -d api worker ui
docker compose exec api alembic upgrade head
python scripts/seed_kb.py --scope global --dir ./seed_kb
docker compose ps   # all healthy
curl http://localhost:8000/health
```

Port map: `8000 api, 3000 ui, 6333 qdrant, 5432 pg, 6379 redis, 9000 minio`. Data volumes: `pgdata, qdrant_storage, redis-data, minio-data` (gitignored).

## 10.4 Demo script (definition of done, `scripts/demo.sh` steps)
1. Signup `demo@x.com` → login → create session `Demo`. 2. Upload `sample.pdf + sample.png + sample.mp3` (private) → poll to `ready`. 3. Ask KB Q → assert `citations≥1` + click-through. 4. Re-ask same Q → assert `cached:true` + `<300ms`. 5. Toggle `agent` → ask unanswerable → assert exact abstain + `agent_trace` non-empty. 6. Thumbs-down + comment → assert row in feedback + admin helpfulness moves. 7. Second user sees isolated sessions. Any step fails → release blocked.

## 10.5 Seed KB (`scripts/seed_kb.py`)
Args: `--scope global --dir ./seed_kb --recreate`. Behavior: for each file → upload as service user → wait `ready` → log `doc_id`; writes `seed_manifest.json {filename: doc_id}` for evals to reference `gold_chunk_ids`.

## 10.6 Backup/restore
* Backup: `pg_dump $DATABASE_URL > backup.sql` + `curl POST qdrant/snapshots` + `mc mirror minio/rag-blobs s3://backups/` (cron nightly, 7-day retention).
* Restore drill: fresh compose → `psql < backup.sql` → restore snapshot → `seed_manifest` re-verify → demo.sh green. Document output in `ops/restore_log.md`.

## 10.7 Troubleshooting matrix

| Symptom | Check | Fix |
|---|---|---|
| `ingest stuck queued` | `celery -A ... inspect active`, Redis `PING` | restart worker, `task_time_limit` logs |
| `Qdrant 404 collection` | `GET :6333/collections` | rerun `init_collections.py` (Plan 04 Step 1) |
| `SSE no stream` | nginx `proxy_buffering`, Next rewrite | set `X-Accel-Buffering: no`, curl `--no-buffer` test |
| `cache never hits` | `SEM_CACHE_THRESHOLD` too high, filters differ | lower to 0.95 for test, log `filters_hash` |
| `agent loops 45s` | Langfuse trace, `MAX_ITERS` | set `AGENT_ENABLED=false` fallback, cap `top_k=5` |
| `upload 413` | nginx vs FastAPI limit | align `client_max_body_size 100M` both |

## 10.8 Acceptance
* [ ] New machine, fresh clone, follow §10.3 only → demo.sh 7/7 green, no tribal knowledge.
* [ ] Restore drill succeeds and is logged.
