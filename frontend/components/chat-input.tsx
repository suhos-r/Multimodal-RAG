"use client";
import { useState } from "react";
import { ISend, IStop } from "./icons";

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
      <div className="composer-inner">
        <label className="label" htmlFor="composer-input" style={{ display: "block", marginBottom: 4 }}>
          Ask the knowledge base
        </label>
        <textarea
          id="composer-input"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Ask about your uploads… (Enter to send, Shift+Enter for a new line)"
          maxLength={2000}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send(false);
            }
          }}
        />
        <div className="row">
          <div className="mode-seg" role="group" aria-label="Retrieval mode">
            {(["fast", "agent"] as const).map((m) => (
              <button key={m} type="button" aria-pressed={mode === m} onClick={() => setMode(m)}
                title={m === "agent" ? "Self-reflective loop: grades, rewrites and critiques (slower)" : "Single retrieve-and-generate pass"}>
                {m === "fast" ? "Fast" : "Agent"}
              </button>
            ))}
          </div>
          {streaming
            ? <button className="btn" onClick={onStop}><IStop /> Stop</button>
            : <button className="btn btn-primary" onClick={() => send(false)} disabled={!q.trim()}><ISend /> Send</button>}
          <span className="char-count" aria-label={`${q.length} of 2000 characters`}>{q.length}/2000</span>
        </div>
      </div>
    </div>
  );
}
