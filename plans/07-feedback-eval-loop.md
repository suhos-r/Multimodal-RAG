# Plan 07 — Citations UX Contract + User Feedback Loop

## 7.1 Objective
Every response is verifiable (click → source) and ratable (thumbs/comment/correction feeds evals).

## 7.2 Citation payload contract (binding, backend→frontend)

```json
{"answer": "Revenue grew 12% [1] ...", "citations": [
  {"id": 1, "doc_id": "uuid", "filename": "q3.pdf", "page": 4,
   "bbox": {"x0":0.1,"y0":0.2,"x1":0.9,"y1":0.3}, "ts": null,
   "quote": "Revenue grew 12% YoY...", "score": 0.87}]}
```
Rules: `id` sequential from 1; `quote ≤40 words verbatim`; `page/bbox/ts` from index (never LLM-invented — verifier enforces); image/audio use `ts` or `image_ref`.

## 7.3 Feedback API (`backend/app/routers/feedback.py`)
* `POST /api/feedback {message_id, rating: 1|-1, comment?: max1000, corrected_answer?: max4000}` → auth, verify message belongs to user → upsert one row per (message,user) → 201 `{id}`.
* `GET /api/feedback?message_id=` → user's own feedback (for UI state).
* `GET /api/admin/stats` extended: `{helpfulness_pct, total_ratings, downvote_rate, top_failing_doc_ids[]}`.
* Nightly job `worker/jobs/rollup_feedback.py`: recompute helpfulness, append `rating==-1` cases to `evals/gold_qa.jsonl` candidates (manual review gate), flag docs with >30% downvote for re-chunk.

## 7.4 Steps
1. Backend: implement router + rollup job + admin aggregation SQL.
2. Frontend (full spec in Plan 08, contract here): under every assistant message — `thumbs-up/down (toggle), copy, regenerate, report→comment modal, corrected-answer textbox (optional)`; citation `[n]` → popover (quote + filename + page + `Open source` → viewer at page/bbox).
3. Tests: feedback ownership (B cannot rate A message → 404), upsert idempotent, rollup math, citation popover data present in SSE `done`.

## 7.5 Acceptance
* [ ] Rate any answer → row in `feedback`, dashboard helpfulness updates ≤5min.
* [ ] Click `[1]` → popover shows verbatim quote + `Open q3.pdf p.4` scrolls viewer to bbox.
* [ ] Corrected answers land in eval candidate queue; doc with mass downvotes flagged.

## 7.6 Effort
1 day backend + UI time in Plan 08. Risk: feedback spam → rate-limit 60/hr + one-row-per-user constraint.
