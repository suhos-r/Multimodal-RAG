"use client";
import { useState } from "react";
import { api } from "../lib/api";
import { ICopy, IDown, IFlag, IRefresh, IUp } from "./icons";

export default function FeedbackBar({ messageId, onRegenerate }: {
  messageId: string;
  onRegenerate: () => void;
}) {
  const [vote, setVote] = useState<1 | -1 | 0>(0);
  const [showReport, setShowReport] = useState(false);
  const [comment, setComment] = useState("");
  const [correction, setCorrection] = useState("");
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");

  async function rate(r: 1 | -1, extra?: { comment?: string; corrected_answer?: string }) {
    setErr("");
    try {
      await api("/api/feedback", {
        method: "POST",
        body: JSON.stringify({ message_id: messageId, rating: r, ...extra }),
      });
      setVote(r);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setErr("Couldn't save feedback — retry.");
    }
  }

  function copy() {
    navigator.clipboard?.writeText(document.getElementById(`m-${messageId}`)?.innerText ?? "");
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div>
      <div className="fbbar" role="toolbar" aria-label="Answer actions">
        <button className={`btn btn-sm${vote === 1 ? " on-up" : ""}`} onClick={() => rate(1)}
          title="Helpful" aria-label="Mark helpful" aria-pressed={vote === 1}><IUp /></button>
        <button className={`btn btn-sm${vote === -1 ? " on-down" : ""}`} onClick={() => rate(-1)}
          title="Not helpful" aria-label="Mark not helpful" aria-pressed={vote === -1}><IDown /></button>
        <button className="btn btn-sm" onClick={copy} title="Copy answer" aria-label="Copy answer"><ICopy /></button>
        <button className="btn btn-sm" onClick={onRegenerate} title="Regenerate (bypass cache)" aria-label="Regenerate answer"><IRefresh /></button>
        <button className="btn btn-sm" onClick={() => setShowReport(true)} title="Report or correct" aria-label="Report or correct answer"><IFlag /></button>
        {saved && <span className="saved" role="status">saved</span>}
      </div>
      {err && <p className="err">{err}</p>}
      {showReport && (
        <div className="modal-back" onClick={() => setShowReport(false)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Report answer" onClick={(e) => e.stopPropagation()}>
            <h3>Report / correct this answer</h3>
            <div className="field">
              <label htmlFor={`rep-c-${messageId}`}>What was wrong?</label>
              <textarea id={`rep-c-${messageId}`} value={comment} onChange={(e) => setComment(e.target.value)}
                placeholder="e.g. Cited the wrong quarter" style={{ width: "100%", minHeight: 60 }} />
            </div>
            <div className="field">
              <label htmlFor={`rep-a-${messageId}`}>Correct answer <span className="hint">(optional — feeds eval review)</span></label>
              <textarea id={`rep-a-${messageId}`} value={correction} onChange={(e) => setCorrection(e.target.value)}
                placeholder="What should it have said?" style={{ width: "100%", minHeight: 60 }} />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-primary" onClick={() => {
                rate(-1, { comment: comment || undefined, corrected_answer: correction || undefined });
                setShowReport(false);
              }}>Submit report</button>
              <button className="btn" onClick={() => setShowReport(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
