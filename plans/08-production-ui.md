# Plan 08 — Production UI (Next.js + shadcn)

## 8.1 Objective
Production-style, responsive, accessible chat + knowledge + admin. Streaming-first, citation-first.

## 8.2 Routes & files (exact)

```text
frontend/app/layout.tsx (theme, font Inter, toaster)
frontend/app/(auth)/login/page.tsx + signup/page.tsx
frontend/app/(app)/layout.tsx (sidebar + header)
frontend/app/(app)/chat/page.tsx (empty state)  frontend/app/(app)/chat/[id]/page.tsx (thread)
frontend/app/(app)/knowledge/page.tsx (uploader + doc table + preview drawer)
frontend/app/(app)/admin/page.tsx (hit-rate, latency, helpfulness charts via recharts)
frontend/components/{sidebar.tsx, chat-input.tsx, message-list.tsx, message.tsx,
  citation-popover.tsx, feedback-bar.tsx, uploader.tsx, doc-viewer.tsx, mode-toggle.tsx}
frontend/lib/{api.ts (JWT fetch wrapper), sse.ts, store.ts (zustand), types.ts}
```

## 8.3 Specs per screen

* **Sidebar**: session list (`GET /sessions`), search filter, rename (inline), delete (confirm), `New chat`, user email + logout. Active id highlighted. Mobile drawer.
* **Thread `[id]`**: `message-list` (user right / assistant left, `react-markdown + remark-gfm`), streaming dots + `stop` button (AbortController), citation `[n]` chips → `citation-popover` (quote, file, page, Open source), `feedback-bar` (Plan 07) under each assistant msg, `cached` + `agent` badges, `mode toggle fast|agent`, `fresh` (bypass cache) on regenerate, auto-scroll + `scroll to bottom`, empty-state prompts (`Try: "Summarize q3.pdf p.4"`).
* **Chat input**: autosize textarea, Enter-send/Shift-Enter-newline, file attach shortcut → knowledge, char count 2000, disabled while streaming.
* **Knowledge**: drag-drop (react-dropzone, 100MB cap, type icons), progress bars polling `status`, scope toggle private/global, table (name, scope, status, pages, actions view/delete), preview drawer (`pdf-viewer`/text/image/audio player at cited page/bbox/ts).
* **Admin**: cards (hit-rate, p50 latency, tokens 24h, helpfulness %), line/bar charts, failing-docs table, trace viewer (JSON `agent_trace`).
* **A11y/perf**: keyboard navigable, `aria-labels`, focus rings, dark/light, `Lighthouse >85`, `TTFB stream <1s` (cached <300ms), bundle <350KB initial (dynamic import viewer/charts).

## 8.4 API/SSE wiring
* `lib/api.ts`: `api(path, {method, body, auth})` attaches `Bearer`, refreshes on 401 once, throws `{detail,code}`.
* `lib/sse.ts`: `postSSE('/api/chat', body, {onDelta, onNode, onDone, signal})` parses `data:` lines; `onNode` shows agent step spinner (Plan 06).
* `store.ts`: `{sessions, activeId, messagesBySession, streamingId, mode}`; optimistic user msg, patch on done; persist mode in localStorage.

## 8.5 Steps
1. Scaffold + shadcn init + theme. 2. Auth pages → session sidebar. 3. Thread + SSE + markdown + citations. 4. Feedback bar. 5. Knowledge uploader + viewer. 6. Admin charts. 7. Perf/a11y pass + Playwright smoke.

## 8.6 Acceptance
* [ ] Login→new chat→ask→stream→cite-click→feedback→reload→history intact (E2E Playwright).
* [ ] Upload 3 types with progress; delete works; Lighthouse perf/a11y >85; mobile 360px usable.

## 8.7 Effort
3–4 days. Risk: SSE proxy buffering → set `X-Accel-Buffering: no`, Next rewrites with `compress:false` for `/api/*`.
