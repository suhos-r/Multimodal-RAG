# Plan 09 — Hardening, Eval Gates, Deploy

## 9.1 Objective
Secure, observable, tested, deployable with one command. No demo-day surprises.

## 9.2 Security (binding checklist)
* JWT: `JWT_SECRET ≥32B`, rotate procedure documented; refresh rotation; logout clears server allowlist if used.
* Isolation: every vector query filters `scope`; every session/doc/message access checks `user_id` (tests in 01/02/04 must stay green).
* Uploads: 100MB cap (nginx + FastAPI), mime-sniff reject, filename sanitize, presigned URLs 15min expiry, never serve blobs via API process.
* PII: `services/pii.py` regex (email/phone/Aadhaar-ish) redacts logs/traces; raw PII never in Langfuse.
* Abuse: slowapi `30 chat/min, 10 uploads/hr, 60 feedback/hr` per user; frontend shows 429 + retry-after.
* Secrets: `.env` gitignored; `.env.example` only placeholders; CI fails if `OPENAI_API_KEY` in diff.

## 9.3 Observability
* `structlog` JSON `{ts,trace_id,user_id,route,ms}`; `X-Trace-ID` on every response; Langfuse traces per chat (tokens, cost, cache/agent flags); Prometheus `/metrics` `{http_lat, llm_tokens, cache_hits, agent_iters, ingest_jobs}` + Grafana stub.

## 9.4 Tests & gates (all must pass)
```text
pytest -q (auth, ingest, chunkers, retrieval, citations, cache, agent, feedback)
python evals/run_chunk_bench.py (winner matches Plan 03 default or ADR filed)
python evals/ragas_eval.py --min_faithfulness 0.80 --min_citation_precision 0.85
npx playwright test (login→chat→cite→feedback→upload)
```
CI (`.github/workflows/ci.yml`): lint (ruff), typecheck (mypy strict on services), pytest, eval gate (blocks merge on faithfulness drop >3pts).

## 9.5 Deploy (`docker-compose.yml` canonical services: postgres:15, qdrant, redis:7, minio, api, worker, ui)
* `api`: `uvicorn app.main:app --host 0.0.0.0:8000 --workers 2`; `worker`: celery ingest+eval; `ui`: `next start`; nginx (prod) `client_max_body_size 100M`, SSE `proxy_buffering off`.
* Backups: nightly `pg_dump` + Qdrant snapshots to S3; restore procedure in runbook (Plan 10 §6).
* Rollout: `docker compose pull && up -d api worker ui`, health-gated (`/health` ok before routing).

## 9.6 Acceptance
* [ ] Fresh clone → `cp .env.example .env` → `docker compose up -d` → demo script (Plan 10) green.
* [ ] CI red on injected hallucination regression (eval gate proven).
* [ ] Rate-limit + PII + isolation probes all blocked/logged; backup/restore dry-run documented.

## 9.7 Effort
2 days + 0.5 day backup drill. Risk: GPU/CPU cost → document `OLLAMA` local fallback + `RERANK_ENABLED=false` degraded mode.
