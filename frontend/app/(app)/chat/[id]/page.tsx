"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "../../../../lib/api";
import { postChatSSE } from "../../../../lib/sse";
import { useAuth } from "../../../../lib/store";
import type { ChatMessage, Citation, DonePayload } from "../../../../lib/types";
import ChatInput from "../../../../components/chat-input";
import CitationModal from "../../../../components/citation-modal";
import { CitedText } from "../../../../components/cited-text";
import FeedbackBar from "../../../../components/feedback-bar";
import { IMenu } from "../../../../components/icons";

const SUGGESTIONS = [
  "What was Q3 revenue growth?",
  "How long are digital goods refundable?",
  "Summarize the refund policy in two sentences.",
];

export default function ThreadPage() {
  const params = useParams();
  const id = params?.id as string;
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [streaming, setStreaming] = useState(false);
  const [nodes, setNodes] = useState<string[]>([]);
  const [activeCite, setActiveCite] = useState<Citation | null>(null);
  const [err, setErr] = useState("");
  const [lastQuery, setLastQuery] = useState<{ q: string; mode: "fast" | "agent" } | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const setNavOpen = useAuth((s: { setNavOpen: (v: boolean) => void }) => s.setNavOpen);

  const load = useCallback(() => {
    setLoading(true);
    api<ChatMessage[]>(`/api/sessions/${id}/messages?limit=200`)
      .then((m) => { setMessages(m); setErr(""); })
      .catch((e: any) => setErr(`Couldn't load this chat — ${String(e)}. `))
      .finally(() => setLoading(false));
  }, [id]);
  useEffect(load, [load]);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  async function send(q: string, mode: "fast" | "agent", fresh: boolean) {
    setErr("");
    setStreaming(true);
    setNodes([]);
    setLastQuery({ q, mode });
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
      if ((e as Error).name !== "AbortError") {
        setErr(`Answer failed — ${String(e)}. Nothing was lost; retry below.`);
        setMessages((p) => p.filter((m) => m.id !== aiId));
      }
    } finally {
      setStreaming(false);
      abortRef.current = null;
      load(); // reconcile ids/citations with server truth
    }
  }

  return (
    <>
      <div className="topbar">
        <button className="btn btn-sm btn-ghost menu-btn" onClick={() => setNavOpen(true)} aria-label="Open navigation">
          <IMenu />
        </button>
        <span className="label">Chat · {id.slice(0, 8)}</span>
        <span style={{ flex: 1 }} />
        <a href="/knowledge" style={{ fontSize: "var(--step--1)" }}>Add documents</a>
      </div>
      <div className="thread">
        <div className="thread-inner">
          {loading ? (
            <div aria-busy="true" aria-label="Loading messages">
              <div className="skel" style={{ height: 18, width: "70%", marginBottom: 12 }} />
              <div className="skel" style={{ height: 60, marginBottom: 24 }} />
              <div className="skel" style={{ height: 18, width: "45%", marginBottom: 12 }} />
              <div className="skel" style={{ height: 90 }} />
            </div>
          ) : messages.length === 0 ? (
            <div className="empty">
              <div className="label">New chat</div>
              <h3>Ask anything your documents know.</h3>
              <p>Answers stream with clickable source lamps. Try one:</p>
              <div className="actions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="btn btn-sm" onClick={() => send(s, "fast", false)}>{s}</button>
                ))}
              </div>
            </div>
          ) : messages.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              <div className="bubble" id={`m-${m.id}`}>
                {m.role === "assistant" && m.content === "" ? (
                  <span className="spin">Composing</span>
                ) : m.role === "assistant" ? (
                  <>
                    <CitedText text={m.content} citations={m.citations ?? []} onCite={setActiveCite} pulseKey={m.id} />
                    {streaming && m.id.startsWith("local-") && <span className="caret" aria-hidden="true" />}
                  </>
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
            <div className="meta" role="status" aria-label="Agent progress">
              {nodes.map((n, i) => <span key={i} className="badge agent">{n}</span>)}
            </div>
          )}
          {err && (
            <div style={{ marginTop: 8 }}>
              <p className="err" role="alert">{err}</p>
              <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                {lastQuery
                  ? <button className="btn btn-sm btn-primary" onClick={() => send(lastQuery.q, lastQuery.mode, false)}>Retry</button>
                  : <button className="btn btn-sm btn-primary" onClick={load}>Retry</button>}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <ChatInput onSend={send} streaming={streaming} onStop={() => abortRef.current?.abort()} />
      {activeCite && <CitationModal c={activeCite} onClose={() => setActiveCite(null)} />}
    </>
  );
}
