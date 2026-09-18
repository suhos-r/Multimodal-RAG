# Plan 02 — Multimodal Ingestion (Any Format)

## 2.1 Objective
Any file a user uploads becomes searchable with page/bbox/timestamp-preserving citations. Async, resumable, observable.

## 2.2 Scope
IN: upload API, blob store, parser router, canonical normalizer, Celery worker, status API, scope filtering, deletion cascade.
OUT: chunking variants (Plan 03), retrieval (Plan 04). Chunking here = single default (recursive 800/150) so pipeline is end-to-end; Plan 03 swaps it.

## 2.3 Prerequisites
Plan 01 done. Docker services: minio, redis. System bins: `ffmpeg, tesseract-ocr, pandoc, libmagic`.

## 2.4 Detailed steps

**Step 1 — Upload API (`backend/app/routers/documents.py`):**
* `POST /api/documents/upload`: `multipart(file, scope: global|private=default private)`. Validate: size ≤100MB, media duration ≤30min (probe via ffprobe), mime sniff with `python-magic` (reject on mismatch with extension).
* Flow: `uuid doc_id` → `blob_path = {scope}/{user_id}/{doc_id}/{filename}` → `boto3 upload to MinIO` → insert `documents(status='queued')` → `celery.send_task('ingest_doc', [doc_id])` → 202 `{doc_id,status:'queued'}`.
* `GET /api/documents`, `GET /api/documents/{id}/status {status,progress 0-100,error?}`, `DELETE /api/documents/{id}` (delete blob + Qdrant points with `doc_id` + `chunks_registry` + invalidate `query_cache` rows whose `doc_ids` contains id — Plan 05 hook, stub now).

**Step 2 — Parser router (`backend/app/parsers/{__init__.py,router.py,pdf.py,office.py,media.py,image.py}`):**
* `router.parse(blob_path, mime) -> list[RawBlock{modality,text,page,bbox,ts,image_ref}]`.
* Dispatch table (exact):
  * `application/pdf` → `pdf.py`: PyMuPDF `page.get_text('blocks')` + `page.get_drawings` for bbox; tables via `camelot/pdfplumber`; if extracted chars/page <50 → OCR `ocrmypdf+Tesseract`.
  * `docx/pptx/xlsx/csv/md/html/txt` → `office.py`: `unstructured.partition` + `pandoc` fallback; xlsx/csv → row→sentence `Row {sheet} col=val`; pptx → slide=page.
  * `png/jpg/webp` → `image.py`: `BLIP-2 caption + Tesseract OCR`; emit one block `page=1, bbox=full, text="IMAGE {filename}: {caption} OCR:{ocr}"`, keep `image_ref` for UI + `image-v1` embedding.
  * `mp3/wav/m4a` → `media.py`: `faster-whisper base` → segments `{ts_start,ts_end,text}`; page = segment index.
  * `mp4/mov` → `media.py`: `ffmpeg -vf fps=1/5` keyframes → BLIP caption each + Whisper transcript; merge by timestamp.
* All parsers: never throw raw; on fail return `PartialResult(blocks_so_far, warning)` + set `documents.error`.

**Step 3 — Normalizer (`backend/app/parsers/normalize.py`):**
* Input `RawBlock[]` → output `CanonicalDoc{doc_id, blocks[{text (strip, collapse ws, keep table markdown), page, bbox{x0,y0,x1,y1}|null, ts| null, modality, image_ref| null}]}`.
* Rules: drop blocks <10 chars (unless table), cap block 4000 chars (split on sentence), language detect (`fasttext` or skip + tag `unknown`), PII flag pass-through (redaction happens at serve time, not here).

**Step 4 — Worker (`backend/app/workers/celery_app.py`, `tasks.py`):**
* `celery_app`: broker+backend `REDIS_URL`, queues `ingest,eval`, `acks_late=True`, retry `3× exp backoff`, `task_track_started`.
* `ingest_doc(doc_id)`: `queued→parsing (10%)` → `router.parse` → `parsing→chunking (50%)` → default chunk (Plan 03 interface stub) → `chunking→embedding (75%)` → embed BGE-M3 + upsert Qdrant `text-v1` (batch 64) + `image-v1` if images → insert `chunks_registry` → `ready (100%)`. On exception: `failed + error (first 500 chars)` + structured log with `trace_id`.
* Idempotent: re-run with same `doc_id` deletes existing Qdrant points first.

**Step 5 — Config & limits:** `MAX_UPLOAD_MB=100`, `MAX_MEDIA_MIN=30`, `WHISPER_MODEL=base`, `OCR_LANGS=eng`, Celery `worker_concurrency=2`, `task_time_limit=900`.

**Step 6 — Tests (`tests/test_ingest.py` + fixtures `tests/fixtures/{sample.pdf,sample.docx,sample.png,sample.mp3}`):**
1. Upload each → status reaches `ready` ≤120s (mp3 ≤300s). 2. Qdrant has points with correct `scope/page`. 3. Private doc invisible to other user (retrieval filter test stub). 4. Corrupt file → `failed` + clean error, no crash. 5. Re-ingest idempotent (point count stable).

## 2.5 Acceptance
* [ ] 4 fixture types → `ready`, page/ts metadata present, `chunks_registry` rows match Qdrant count.
* [ ] 100MB+1 byte rejected 413; 31-min audio rejected 413 with message.
* [ ] Delete doc → blob + vectors + registry gone; second delete → 404.
* [ ] Worker kill mid-task → retry succeeds, no dup points.

## 2.6 Effort / risks
Effort: 3–4 days (media models heaviest). Risk: Whisper CPU slow → default `tiny` for tests, `base` prod, document GPU flag `WHISPER_DEVICE=cuda`.
