"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { API, api, authHeader } from "../../../lib/api";
import type { DocInfo } from "../../../lib/types";
import { ITrash, IUpload } from "../../../components/icons";

const ACCEPT = ".pdf,.docx,.pptx,.txt,.md,.html,.csv,.xlsx,.xls,.png,.jpg,.jpeg,.webp,.mp3,.wav,.m4a,.ogg,.mp4,.mov";

export default function KnowledgePage() {
  const [docs, setDocs] = useState<DocInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(() => {
    api<DocInfo[]>("/api/documents")
      .then((d) => { setDocs(d); setErr(""); })
      .catch((e: any) => setErr(`Couldn't load documents — ${String(e)}.`))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, [load]);

  async function upload(list: FileList | File[] | null) {
    const files = list ? Array.from(list) : [];
    if (files.length === 0) return;
    setBusy(true);
    setErr("");
    setDrag(false);
    try {
      for (const f of files) {
        if (f.size > 100 * 1024 * 1024) throw new Error(`${f.name} is over the 100 MB limit.`);
        const fd = new FormData();
        fd.append("file", f);
        fd.append("scope", "private");
        const r = await fetch(`${API}/api/documents/upload`, {
          method: "POST", headers: authHeader(), body: fd,
        });
        if (!r.ok) throw new Error(`${f.name}: upload failed (${r.status}) — ${(await r.text()).slice(0, 160)}`);
        const { doc_id } = await r.json();
        // trigger ingestion (worker does this in prod; manual here for docker-less demo)
        await api(`/api/documents/${doc_id}/process`, { method: "POST" });
      }
      load();
    } catch (e) {
      setErr(String(e instanceof Error ? e.message : e));
    } finally {
      setBusy(false);
    }
  }

  async function del(id: string) {
    await api(`/api/documents/${id}`, { method: "DELETE" });
    setConfirmId(null);
    load();
  }

  return (
    <main className="page">
      <div className="page-head">
        <div className="label">Library</div>
        <h2>Knowledge base</h2>
        <p>Your uploads become searchable alongside the shared base. Processing runs per file — status updates live.</p>
      </div>
      <div
        className={`dropzone${drag ? " over" : ""}`}
        role="button" tabIndex={0} aria-label="Upload documents"
        onClick={() => fileRef.current?.click()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fileRef.current?.click(); }}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); upload(e.dataTransfer.files); }}
      >
        <IUpload />
        <p style={{ margin: "8px 0 4px" }}>{busy ? "Uploading + ingesting…" : "Drop files here or browse"}</p>
        <p className="hint" style={{ margin: 0, fontSize: "var(--step--1)", color: "var(--ink-3)" }}>
          PDF · DOCX · PPTX · TXT · MD · HTML · CSV · XLSX · images · audio · video — 100 MB each
        </p>
        <input ref={fileRef} type="file" multiple hidden accept={ACCEPT}
          onChange={(e) => { upload(e.target.files); e.target.value = ""; }} disabled={busy} />
      </div>
      {busy && <p className="spin" role="status">Uploading + ingesting</p>}
      {err && <p className="err" role="alert">{err}</p>}

      {loading ? (
        <div style={{ marginTop: 16 }} aria-busy="true" aria-label="Loading documents">
          {[0, 1, 2].map((i) => <div key={i} className="skel" style={{ height: 44, marginBottom: 8 }} />)}
        </div>
      ) : docs.length === 0 ? (
        <div className="empty">
          <h3>No documents yet.</h3>
          <p>Upload your first file above — it will be parsed, chunked and indexed, then ready for questions.</p>
        </div>
      ) : (
        <table className="docs" style={{ marginTop: 16 }}>
          <thead><tr><th>File</th><th>Scope</th><th>Status</th><th style={{ textAlign: "right" }}>Pages</th><th><span className="label">Actions</span></th></tr></thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.doc_id}>
                <td data-th="File">{d.filename}<div style={{ fontSize: "var(--step--1)", color: "var(--ink-3)", fontFamily: "var(--font-mono)" }}>{d.mime}</div></td>
                <td data-th="Scope">{d.scope}</td>
                <td data-th="Status">
                  <span className={`status ${d.status === "ready" ? "ready" : d.status === "failed" ? "failed" : "working"}`}>
                    <span className="dot" aria-hidden="true" />{d.status}
                  </span>
                  {d.error && <div style={{ fontSize: "var(--step--1)", color: "var(--negative)" }}>{d.error}</div>}
                </td>
                <td data-th="Pages" className="num">{d.page_count ?? "—"}</td>
                <td data-th="Actions">
                  {confirmId === d.doc_id ? (
                    <span className="confirm-row" role="alertdialog" aria-label={`Delete ${d.filename}?`}>
                      <span>Delete <strong>{d.filename}</strong> + vectors?</span>
                      <button className="btn btn-sm btn-danger" onClick={() => del(d.doc_id)}>Delete file</button>
                      <button className="btn btn-sm btn-ghost" onClick={() => setConfirmId(null)}>Keep</button>
                    </span>
                  ) : (
                    <button className="btn btn-sm btn-ghost" onClick={() => setConfirmId(d.doc_id)}
                      aria-label={`Delete ${d.filename}`} title="Delete document"><ITrash /></button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  );
}
