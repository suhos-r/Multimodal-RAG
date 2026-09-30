"use client";
import { useEffect, useState } from "react";
import type { Citation } from "../lib/types";
import { API, authHeader } from "../lib/api";
import { IX } from "./icons";

export default function CitationModal({ c, onClose }: { c: Citation; onClose: () => void }) {
  const [failed, setFailed] = useState("");
  const dl = `${API}/api/documents/${c.doc_id}/download`;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function openSource() {
    setFailed("");
    try {
      const r = await fetch(dl, { headers: authHeader() });
      if (!r.ok) throw new Error(`Source unavailable (${r.status}). It may have been deleted.`);
      const b = await r.blob();
      window.open(URL.createObjectURL(b), "_blank", "noopener");
    } catch (e) {
      setFailed(String(e instanceof Error ? e.message : e));
    }
  }

  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={`Source ${c.id}`} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <h3 style={{ margin: 0, flex: 1 }}>Source [{c.id}]</h3>
          <button className="btn btn-sm btn-ghost" onClick={onClose} aria-label="Close source view"><IX /></button>
        </div>
        <div className="cite-meta" style={{ marginTop: 4 }}>
          {c.filename} {c.page != null ? `· page ${c.page}` : ""} · {c.modality} · score {c.score}
        </div>
        <blockquote>{c.quote}</blockquote>
        {failed && <p className="err">{failed}</p>}
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-primary" onClick={openSource}>Open source</button>
          <button className="btn" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
