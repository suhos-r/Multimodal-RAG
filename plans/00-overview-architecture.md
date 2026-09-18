# Plan 00 — Overview, Frozen Decisions, Contracts

## 0.1 Objective
Freeze every cross-cutting decision so Plans 01–10 are unambiguous and executable without revisiting stack, schema, or API shape.

## 0.2 Scope
IN: stack versions, repo layout, DB schema v1, API surface, vector collections, env contract, naming/coding conventions, definition of done.
OUT: any implementation code (starts in Plan 01).

## 0.3 Frozen stack (do not change without ADR)

| Layer | Choice | Version | Rationale / swap rule |
|---|---|---|---|
| API | FastAPI + SQLAlchemy 2.0 + Alembic + Pydantic v2 | py 3.11 | async, OpenAPI free |
| DB | Postgres 15 | 15.x | sessions/messages/feedback; use `pg_trgm` for BM25 fallback if Qdrant unavailable |
| Vectors | Qdrant | 1.9+ | payload filtering (`scope`, `doc_id`), HNSW; fallback: pgvector (decision log required) |
| Cache/Queue | Redis 7 + Celery 5 (or RQ) | 7.x / 5.3 | exact cache, semantic cache, ingest queue |
| Blobs | MinIO (S3-compat) local, S3 prod | — | presigned URLs, never proxy bytes via API |
| LLM router | LiteLLM | latest | single `llm.py` entry; providers: OpenAI gpt-4o-mini (default), Anthropic, Ollama (local fallback) |
| Embeddings | BGE-M3 (text, 1024d) | — | multilingual, dense+sparse in one; alt E5-large |
| Image embed | CLIP ViT-B/32 or SigLIP | — | image-native collection |
| Reranker | bge-reranker-v2-m3 or Cohere | — | top-20→5 |
| Parsers | PyMuPDF, unstructured, pandoc, faster-whisper, ffmpeg, BLIP-2, Tesseract | pinned in requirements | see Plan 02 |
| Frontend | Next.js 14 App Router + Tailwind + shadcn/ui + zustand | 14.x | SSE streaming |
| Obs | Langfuse + Prometheus + structlog JSON | — | per-message tokens/latency/hit-rate |

## 0.4 Canonical DB schema v1 (Postgres)

```sql
users(id UUID PK, email CITEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now());
sessions(id UUID PK, user_id UUID REFERENCES users ON DELETE CASCADE, title TEXT NOT NULL DEFAULT 'New chat',
  created_at TIMESTAMPTZ DEFAULT now(), updated_at TIMESTAMPTZ DEFAULT now());
messages(id UUID PK, session_id UUID REFERENCES sessions ON DELETE CASCADE, role TEXT CHECK (role IN ('user','assistant','system')),
  content TEXT NOT NULL, citations JSONB DEFAULT '[]', model TEXT, tokens_in INT, tokens_out INT, latency_ms INT,
  cached BOOLEAN DEFAULT FALSE, agent_trace JSONB DEFAULT '[]', created_at TIMESTAMPTZ DEFAULT now());
documents(id UUID PK, owner_id UUID REFERENCES users, scope TEXT CHECK (scope IN ('global','private')) NOT NULL,
  filename TEXT NOT NULL, mime TEXT NOT NULL, bytes BIGINT, blob_path TEXT NOT NULL,
  status TEXT CHECK (status IN ('queued','parsing','chunking','embedding','ready','failed')) DEFAULT 'queued',
  error TEXT, page_count INT, created_at TIMESTAMPTZ DEFAULT now());
chunks_registry(id UUID PK, doc_id UUID REFERENCES documents ON DELETE CASCADE, chunk_id TEXT UNIQUE NOT NULL,
  parent_id TEXT, page INT, bbox JSONB, modality TEXT, char_start INT, char_end INT, created_at TIMESTAMPTZ DEFAULT now());
query_cache(key TEXT PK, norm_query TEXT NOT NULL, embedding VECTOR(1024), response TEXT NOT NULL,
  citations JSONB, filters_hash TEXT, doc_ids TEXT[], hits INT DEFAULT 1, created_at TIMESTAMPTZ, expires_at TIMESTAMPTZ);
feedback(id UUID PK, message_id UUID REFERENCES messages ON DELETE CASCADE, user_id UUID REFERENCES users,
  rating INT CHECK (rating IN (-1,1)), comment TEXT, corrected_answer TEXT, created_at TIMESTAMPTZ DEFAULT now());
```

Indexes: `sessions(user_id, updated_at DESC)`, `messages(session_id, created_at)`, `documents(owner_id, status)`, `feedback(message_id)`, `query_cache(expires_at)`, `HNSW on query_cache.embedding` (or pgvector ext).

## 0.5 Qdrant collections

```json
{
  "text-v1": {"vectors": {"size": 1024, "distance": "Cosine", "hnsw": {"m": 16, "ef_construct": 128}},
              "payload_schema": {"scope": "keyword", "user_id": "keyword", "doc_id": "keyword",
                                 "chunk_id": "keyword", "parent_id": "keyword", "page": "integer", "modality": "keyword"}},
  "image-v1": {"vectors": {"size": 512, "distance": "Cosine"}, "payload_schema": {"doc_id": "keyword", "scope": "keyword"}}
}
```

Rule: every point MUST set `scope` = `global` or `user:{uuid}`; queries MUST filter accordingly. No filter = reject.

## 0.6 API surface (OpenAPI canonical, prefix /api)

```text
POST /api/auth/signup {email,password} -> {access_token, refresh_token}
POST /api/auth/login {email,password} -> {access_token, refresh_token}
POST /api/auth/refresh {refresh_token} -> {access_token}
GET  /api/sessions -> [{id,title,updated_at,preview}]
POST /api/sessions {title?} -> {id}
GET  /api/sessions/{id}/messages?limit=50&before= -> [{...}]
PATCH /api/sessions/{id} {title} | DELETE /api/sessions/{id}
POST /api/documents/upload (multipart: file, scope) -> {doc_id,status}
GET  /api/documents -> [{doc_id,filename,mime,status,page_count}]
GET  /api/documents/{id}/status -> {status,progress,error?}
DELETE /api/documents/{id}
POST /api/chat {session_id, query, filters?{scope,doc_ids}, top_k?} -> SSE {token} ... {done:{answer,citations,cached,trace_id}}
POST /api/feedback {message_id, rating, comment?, corrected_answer?} -> {id}
GET  /api/admin/stats -> {cache_hit_rate, avg_latency, tokens_24h, helpfulness}
GET  /health -> {ok:true, deps:{db,qdrant,redis}}
```

SSE event for chat: `data: {"delta":"..."}` then `data: {"done": {...}, "citations":[...]}`. Errors: `{"detail":..., "code":..., "trace_id":...}` HTTP 4xx/5xx.

## 0.7 Env contract (.env.example canonical keys)

```text
DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5432/rag
QDRANT_URL=http://localhost:6333  QDRANT_API_KEY=
REDIS_URL=redis://localhost:6379/0
S3_ENDPOINT=http://localhost:9000  S3_BUCKET=rag-blobs  S3_ACCESS_KEY=...  S3_SECRET_KEY=...
JWT_SECRET=change-me  JWT_EXP_MIN=60  REFRESH_EXP_DAYS=14
LLM_PROVIDER=openai  LLM_MODEL=gpt-4o-mini  OPENAI_API_KEY=  ANTHROPIC_API_KEY=
EMBED_MODEL=BAAI/bge-m3  RERANK_MODEL=BAAI/bge-reranker-v2-m3
TOP_K=8  RERANK_TOP_N=5  CHUNK_SIZE=800  CHUNK_OVERLAP=150
SEM_CACHE_THRESHOLD=0.97  NEAR_DUP_LOW=0.90  CACHE_TTL_H=24
LANGFUSE_PUBLIC_KEY=  LANGFUSE_SECRET_KEY=
```

## 0.8 Conventions (binding)
1. All LLM calls via `backend/app/services/llm.py::acomplete()` — logs tokens, latency, trace_id; enforces cache hook.
2. All vector writes include `scope,user_id,doc_id,chunk_id,page`; deletes cascade to Qdrant + `query_cache` invalidation by `doc_ids`.
3. Time UTC; money in USD logged per message; PII redaction before logging (emails, phones).
4. Tests: `pytest -q` must pass before any Plan marked done; evals deterministic seed 42.
5. Frontend never calls Qdrant/Postgres directly; only backend `/api/*` with JWT from httpOnly cookie or memory.

## 0.9 Definition of done (global)
Each Plan has testable acceptance in its file; overall done = demo script (Plan 10 §4) passes end-to-end on fresh `docker compose up` + eval gates (faithfulness ≥0.80, citation precision ≥0.85, cache 2nd-hit <300ms).

## 0.10 Risks & mitigations
* Qdrant ops burden → allow pgvector fallback via `VECTOR_BACKEND` flag.
* Whisper/GPU cost → CPU `tiny/base` default, large only via flag; cap upload 100MB/30min media.
* LLM cost blowout → semantic cache + top_k cap + per-user rate limit (Plan 05/09).
