"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "../../../../lib/api";
import { postChatSSE } from "../../../../lib/sse";
import type { ChatMessage, Citation, DonePayload } from "../../../../lib/types";
import ChatInput from "../../../../components/chat-input";
import CitationModal from "../../../../components/citation-modal";
import { CitedText } from "../../../../components/cited-text";
import FeedbackBar from "../../../../components/feedback-bar";

export default function ThreadPage() {
  const params = useParams();
  const id = params?.id as string;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [nodes, setNodes] = useState<string[]>([]);
  const [activeCite, setActiveCite] = useState<Citation | null>(null);
  const [err, setErr] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const load = useCallback(() => {
    api<ChatMessage[]>(`/api/sessions/${id}/messages?limit=200`).then(setMessages).catch((e: any) => setErr(String(e)));
  }, [id]);
  useEffect(load, [load]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function send(q: string, mode: "fast" | "agent", fresh: boolean) {
    setErr("");
    setStreaming(true);
    setNodes([]);
    const userMsg: ChatMessage = { id: `local-u-${Date.now()}`, role: "user", content: q };
    const aiId = `local-a-${Date.now()}`;
    setMessages((p) => [...p, userMsg, { id: aiId, role: "assistant", content: "" }]);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    let acc = "";
    try {
      await postChatSSE(
        { session_id: id, query: q, mode, fresh },
        {
          onDelta: (d: string) => {
            acc += d;
            setMessages((p) => p.map((m) => (m.id === aiId ? { ...m, content: acc } : m)));
          },
          onNode: (n: string, s: string) => setNodes((p) => [...p, `${n}:${s}`]),
          onDone: (done: DonePayload) => {
            setMessages((p) => p.map((m) => (m.id === aiId
              ? { ...m, content: done.answer, citations: done.citations, cached: done.cached, model: done.model }
              : m)));
          },
        },
        ctrl.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") setErr(String(e));
    } finally {
      setStreaming(false);
      abortRef.current = null;
      load(); // reconcile ids/citations with server truth
    }
  }

  return (
    <>
      <div className="topbar">
        <span style={{ fontSize: 13, color: "var(--muted)" }}>Chat {id.slice(0, 8)}…</span>
        <a href="/knowledge" style={{ fontSize: 13 }}>+ add documents</a>
      </div>
      <div className="thread">
        {messages.length === 0 && (
          <p style={{ color: "var(--muted)" }}>
            Try: “What was Q3 revenue growth?” — answers stream with clickable citations [1][2].
          </p>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`msg ${m.role}`}>
            <div className="bubble" id={`m-${m.id}`}>
              {m.role === "assistant" && m.content === "" ? (
                <span className="spin">● thinking…</span>
              ) : m.role === "assistant" ? (
                <CitedText text={m.content} citations={m.citations ?? []} onCite={setActiveCite} />
              ) : (
                m.content
              )}
            </div>
            {m.role === "assistant" && m.id && !m.id.startsWith("local-") && (
              <FeedbackBar messageId={m.id} onRegenerate={() => {
                const lastUser = [...messages].reverse().find((x) => x.role === "user");
                if (lastUser) send(lastUser.content, "fast", true);
              }} />
            )}
            {m.role === "assistant" && (m.cached || m.model) && (
              <div className="meta">
                {m.cached && <span className="badge cached">cached</span>}
                {m.model && <span className="badge">{m.model}</span>}
              </div>
            )}
          </div>
        ))}
        {nodes.length > 0 && (
          <div className="meta">{nodes.map((n, i) => <span key={i} className="badge agent">{n}</span>)}</div>
        )}
        {err && <p className="err">{err}</p>}
        <div ref={bottomRef} />
      </div>
      <ChatInput onSend={send} streaming={streaming} onStop={() => abortRef.current?.abort()} />
      {activeCite && <CitationModal c={activeCite} onClose={() => setActiveCite(null)} />}
    </>
  );
}
