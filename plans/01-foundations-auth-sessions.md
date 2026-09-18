# Plan 01 — Foundations, Auth, Per-User Sessions

## 1.1 Objective
Scaffold monorepo + infra stubs + working auth + persistent per-user chat sessions. No RAG yet.

## 1.2 Prerequisites
Plan 00 accepted. Tools: Python 3.11, Node 20, Docker. Secrets in `.env` (never commit).

## 1.3 Steps (exact, in order)

**Step 1 — Scaffold (create these empty shells):**
```text
backend/requirements.txt, backend/app/{__init__.py,main.py,config.py,deps.py,db.py}
backend/app/{models.py,schemas.py}
backend/app/routers/{__init__.py,auth.py,sessions.py,health.py}
backend/alembic.ini + alembic/versions/0001_init.py
frontend/{package.json,app/layout.tsx,app/(auth)/login/page.tsx}
docker-compose.yml (postgres,qdrant,redis,minio stubs only)
.env.example (copy keys from Plan 00 §0.7)
```

**Step 2 — Deps (`backend/requirements.txt` pin):**
```text
fastapi uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic pydantic v2
python-jose[cryptography] passlib[bcrypt] python-multipart
structlog tenacity httpx boto3 redis celery
pytest pytest-asyncio httpx
```

**Step 3 — Config (`backend/app/config.py`):** `pydantic-settings BaseSettings`, fields = every key in §0.7; `DATABASE_URL`, `JWT_SECRET` required (fail fast if missing).

**Step 4 — Models (`backend/app/models.py`):** SQLAlchemy 2.0 mapped classes for `users,sessions,messages,documents,chunks_registry,query_cache,feedback` exactly per Plan 00 §0.4. `CITEXT` via `func` or `Text+unique lower index` if ext missing.

**Step 5 — Migration `0001_init.py`:** `alembic revision --autogenerate`; verify `alembic upgrade head` then `downgrade -1` then `upgrade head` on fresh Postgres.

**Step 6 — Auth (`routers/auth.py`):**
* `POST /api/auth/signup`: validate email, `bcrypt(pw,12)`, 409 if exists, return JWT pair.
* `POST /api/auth/login`: verify, 401 generic message (no user-enumeration), return pair.
* `POST /api/auth/refresh`: verify refresh, rotate.
* JWT: `sub=user_id, exp`, HS256, `JWT_SECRET`; access 60m, refresh 14d.
* `deps.py::get_current_user`: parse `Bearer`, 401 `{detail:"unauthorized", code:"auth_required"}` on fail; attach `request.state.user_id`, `trace_id` (uuid4 per request, returned in header `X-Trace-ID`).

**Step 7 — Sessions (`routers/sessions.py`, all require auth):**
* `POST /api/sessions {title?}` → 201 `{id,title}`; default title `New chat`.
* `GET /api/sessions` → ordered `updated_at DESC`, include `preview` = first 120 chars of last message.
* `GET /api/sessions/{id}/messages?limit&before` → verify `session.user_id == sub` else 404 (not 403, anti-enumeration); paginate.
* `PATCH /api/sessions/{id} {title: min1 max120}`; `DELETE` cascades messages.
* Auto-title rule (implemented in Plan 04, stub here): on first user message, `title = query[:60]`.
* Every write updates `sessions.updated_at=now()`.

**Step 8 — Health (`routers/health.py`):** `GET /health` checks `SELECT 1`, Qdrant `/readyz`, Redis `PING`; returns `{ok, deps}`; 503 if any down.

**Step 9 — Tests (`backend/tests/test_auth_sessions.py`):**
1. signup→login→refresh happy path; 2. duplicate signup 409; 3. wrong pw 401; 4. user A cannot GET user B session (404); 5. create 2 sessions, add messages, `GET /messages` order + pagination; 6. delete cascades.

**Step 10 — Frontend stub:** `login/page.tsx` (email/pw form → stores access_token in memory + refresh in httpOnly via API route), `chat` layout with sidebar calling `GET /api/sessions`. No streaming yet.

## 1.4 Acceptance (must all pass)
* [ ] `docker compose up -d postgres redis` + `alembic upgrade head` + `uvicorn app.main:app` boots with zero warnings.
* [ ] `pytest -q` 6/6 green.
* [ ] Manual: signup as A and B; A creates 2 sessions, reloads → both persist; B sees empty list; direct GET of A session as B → 404.
* [ ] `GET /health` reports all deps; missing `JWT_SECRET` refuses to boot with clear error.

## 1.5 Effort / risks
Effort: 1–2 days. Risk: CITEXT ext missing → fallback to `func.lower` unique index (documented in migration).
