"use client";
import { useState } from "react";

export default function ChatInput({ onSend, streaming, onStop }: {
  onSend: (q: string, mode: "fast" | "agent", fresh: boolean) => void;
  streaming: boolean;
  onStop: () => void;
}) {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"fast" | "agent">("fast");

  function send(fresh: boolean) {
    if (!q.trim() || streaming) return;
    onSend(q.trim(), mode, fresh);
    setQ("");
  }

  return (
    <div className="composer">
      <textarea
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Ask about the knowledge base or your uploads… (Enter to send, Shift+Enter newline)"
        maxLength={2000}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send(false);
          }
        }}
      />
      <div className="row">
        <select value={mode} onChange={(e) => setMode(e.target.value as "fast" | "agent")} title="Retrieval mode">
          <option value="fast">fast</option>
          <option value="agent">agent (self-reflective)</option>
        </select>
        {streaming
          ? <button onClick={onStop}>Stop</button>
          : <><button onClick={() => send(false)} disabled={!q.trim()}>Send</button></>}
        <span style={{ fontSize: 12, color: "var(--muted)" }}>{q.length}/2000</span>
      </div>
    </div>
  );
}
