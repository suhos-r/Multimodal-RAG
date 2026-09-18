"use client";
import { useCallback, useEffect, useState } from "react";
import { API, api, authHeader } from "../../../lib/api";
import type { DocInfo } from "../../../lib/types";

export default function KnowledgePage() {
  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<DocInfo[]>("/api/documents").then(setDocs).catch((e: any) => setErr(String(e)));
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [load]);

  async function upload(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true);
    setErr("");
    try {
      for (const f of Array.from(files)) {
        const fd = new FormData();
        fd.append("file", f);
        fd.append("scope", "private");
        const r = await fetch(`${API}/api/documents/upload`, {
          method: "POST", headers: authHeader(), body: fd,
        });
        if (!r.ok) throw new Error(`upload ${f.name} failed: ${r.status} ${(await r.text()).slice(0, 200)}`);
        const { doc_id } = await r.json();
        // trigger ingestion (worker does this in prod; manual here for docker-less demo)
        await api(`/api/documents/${doc_id}/process`, { method: "POST" });
      }
      load();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function del(id: string) {
    if (!confirm("Delete document and its vectors?")) return;
    await api(`/api/documents/${id}`, { method: "DELETE" });
    load();
  }

  return (
    <main className="page">
      <h2>Knowledge base</h2>
      <p style={{ color: "var(--muted)", fontSize: 13 }}>
        PDF, DOCX, PPTX, TXT, MD, HTML, CSV, XLSX, images, audio, video — up to 100 MB each.
      </p>
      <input type="file" multiple onChange={(e) => upload(e.target.files)} disabled={busy}
        accept=".pdf,.docx,.pptx,.txt,.md,.html,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.webp,.mp3,.wav,.m4a,.ogg,.mp4,.mov" />
      {busy && <p className="spin">● uploading + ingesting…</p>}
      {err && <p className="err">{err}</p>}
      <table className="docs" style={{ marginTop: 16 }}>
        <thead><tr><th>File</th><th>Scope</th><th>Status</th><th>Pages</th><th></th></tr></thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.doc_id}>
              <td>{d.filename}<div style={{ fontSize: 11, color: "var(--muted)" }}>{d.mime}</div></td>
              <td>{d.scope}</td>
              <td>{d.status}{d.error ? ` — ${d.error}` : ""}</td>
              <td>{d.page_count ?? "—"}</td>
              <td><button onClick={() => del(d.doc_id)}>delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      {docs.length === 0 && <p style={{ color: "var(--muted)" }}>No documents yet.</p>}
    </main>
  );
}
