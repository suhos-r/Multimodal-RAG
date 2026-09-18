"use client";
import { API, authHeader } from "./api";
import type { DonePayload } from "./types";

export interface StreamEvents {
  onDelta?: (d: string) => void;
  onNode?: (node: string, status: string) => void;
  onDone?: (done: DonePayload) => void;
}

/** POST SSE chat endpoint, parsing `data:` lines. Abort via signal. */
export async function postChatSSE(
  body: Record<string, unknown>,
  ev: StreamEvents,
  signal?: AbortSignal,
): Promise<void> {
  const r = await fetch(`${API}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok || !r.body) {
    const t = await r.text().catch(() => r.statusText);
    throw new Error(`chat failed: ${r.status} ${t.slice(0, 200)}`);
  }
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() ?? "";
    for (const ln of lines) {
      if (!ln.startsWith("data:")) continue;
      let e: Record<string, unknown>;
      try {
        e = JSON.parse(ln.slice(5).trim()) as Record<string, unknown>;
      } catch {
        continue;
      }
      if (typeof e.delta === "string") ev.onDelta?.(e.delta);
      else if (typeof e.node === "string") ev.onNode?.(e.node, String(e.status ?? ""));
      else if (e.done) ev.onDone?.(e.done as DonePayload);
    }
  }
}
