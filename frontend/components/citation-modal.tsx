"use client";
import type { Citation } from "../lib/types";
import { API, authHeader } from "../lib/api";

export default function CitationModal({ c, onClose }: { c: Citation; onClose: () => void }) {
  const dl = `${API}/api/documents/${c.doc_id}/download`;
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ marginTop: 0 }}>Source [{c.id}]</h3>
        <div style={{ fontSize: 13, color: "var(--muted)" }}>
          {c.filename} {c.page != null ? `· page ${c.page}` : ""} · {c.modality} · score {c.score}
        </div>
        <blockquote>{c.quote}</blockquote>
        <div style={{ display: "flex", gap: 8 }}>
          <a href={dl} onClick={(e) => {
            // attach auth via fetch->blob so JWT works (no cookies used)
            e.preventDefault();
            fetch(dl, { headers: authHeader() }).then(async (r) => {
              if (!r.ok) throw new Error("download failed");
              const b = await r.blob();
              const u = URL.createObjectURL(b);
              window.open(u, "_blank");
            }).catch((err) => alert(String(err)));
          }}>
            <button>Open source</button>
          </a>
          <button onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
