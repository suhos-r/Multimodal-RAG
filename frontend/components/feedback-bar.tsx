"use client";
import { useState } from "react";
import { api } from "../lib/api";

export default function FeedbackBar({ messageId, onRegenerate }: {
  messageId: string;
  onRegenerate: () => void;
}) {
  const [vote, setVote] = useState<1 | -1 | 0>(0);
  const [showReport, setShowReport] = useState(false);
  const [comment, setComment] = useState("");
  const [correction, setCorrection] = useState("");
  const [saved, setSaved] = useState(false);

  async function rate(r: 1 | -1, extra?: { comment?: string; corrected_answer?: string }) {
    await api("/api/feedback", {
      method: "POST",
      body: JSON.stringify({ message_id: messageId, rating: r, ...extra }),
    });
    setVote(r);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function copy() {
    navigator.clipboard?.writeText(document.getElementById(`m-${messageId}`)?.innerText ?? "");
  }

  return (
    <div>
      <div className="fbbar">
        <button className={vote === 1 ? "on-up" : ""} onClick={() => rate(1)} title="Helpful">👍</button>
        <button className={vote === -1 ? "on-down" : ""} onClick={() => rate(-1)} title="Not helpful">👎</button>
        <button onClick={copy} title="Copy">⧉</button>
        <button onClick={onRegenerate} title="Regenerate (bypass cache)">↻</button>
        <button onClick={() => setShowReport(true)} title="Report / correct">⚑</button>
        {saved && <span style={{ fontSize: 12, color: "var(--accent-2)" }}>saved</span>}
      </div>
      {showReport && (
        <div className="modal-back" onClick={() => setShowReport(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h4 style={{ marginTop: 0 }}>Report / correct this answer</h4>
            <textarea value={comment} onChange={(e) => setComment(e.target.value)}
              placeholder="What was wrong?" style={{ width: "100%", minHeight: 60 }} />
            <textarea value={correction} onChange={(e) => setCorrection(e.target.value)}
              placeholder="Correct answer (optional — feeds eval review queue)"
              style={{ width: "100%", minHeight: 60, marginTop: 8 }} />
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button onClick={() => {
                rate(-1, { comment: comment || undefined, corrected_answer: correction || undefined });
                setShowReport(false);
              }}>Submit</button>
              <button onClick={() => setShowReport(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
