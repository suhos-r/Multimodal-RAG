"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "../lib/api";
import { useAuth } from "../lib/store";
import type { ChatSession } from "../lib/types";
import { IBook, IChat, IGauge, IPlus, ITrash } from "./icons";

function timeAgo(iso: string): string {
  const s = Math.max(1, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function Sidebar() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const params = useParams();
  const router = useRouter();
  const logout = useAuth((s) => s.logout);
  const navOpen = useAuth((s) => s.navOpen);
  const setNavOpen = useAuth((s) => s.setNavOpen);
  const active = (params?.id as string | undefined) ?? null;

  const load = () => api<ChatSession[]>("/api/sessions").then(setSessions).catch(() => {});
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => setNavOpen(false), [active, setNavOpen]);

  async function newChat() {
    const s = await api<ChatSession>("/api/sessions", { method: "POST", body: JSON.stringify({}) });
    setSessions((p) => [s, ...p]);
    router.push(`/chat/${s.id}`);
  }

  async function del(id: string, title: string) {
    await api(`/api/sessions/${id}`, { method: "DELETE" });
    setSessions((p) => p.filter((s) => s.id !== id));
    setConfirmId(null);
    if (active === id) router.push("/chat");
  }

  return (
    <>
      {navOpen && <button className="scrim" aria-label="Close navigation" onClick={() => setNavOpen(false)} />}
      <aside className={`sidebar${navOpen ? " open" : ""}`} aria-label="Workspace navigation">
        <div className="brand">
          <span className="brand-mark">R</span>
          <span className="brand-name">RAG Console</span>
        </div>
        <button className="btn btn-primary" onClick={newChat}><IPlus /> New chat</button>
        <div className="nav-section">
          <div className="label">Library</div>
          <Link href="/knowledge" style={{ display: "block", marginTop: 4 }}>
            <button className="btn btn-ghost" style={{ width: "100%", justifyContent: "flex-start" }}>
              <IBook /> Knowledge base
            </button>
          </Link>
        </div>
        <div className="nav-section">
          <div className="label">Insights</div>
          <Link href="/admin" style={{ display: "block", marginTop: 4 }}>
            <button className="btn btn-ghost" style={{ width: "100%", justifyContent: "flex-start" }}>
              <IGauge /> Admin
            </button>
          </Link>
        </div>
        <div className="nav-section" style={{ flex: 1 }}>
          <div className="label">Chats</div>
          {sessions.length === 0 && (
            <p style={{ fontSize: "var(--step--1)", color: "var(--ink-3)" }}>
              No chats yet — start one above. Each chat keeps its own history.
            </p>
          )}
          {sessions.map((s) => (
            <div key={s.id} className={`sess${active === s.id ? " active" : ""}`}>
              <Link href={`/chat/${s.id}`} style={{ textDecoration: "none", color: "inherit" }}>
                <div className="row">
                  <IChat />
                  <span className="grow" style={{ minWidth: 0 }}>
                    <div className="t">{s.title}</div>
                    <div className="p">{timeAgo(s.updated_at)}{s.preview ? ` · ${s.preview}` : ""}</div>
                  </span>
                </div>
              </Link>
              {confirmId === s.id ? (
                <div className="confirm-row" role="alertdialog" aria-label={`Delete ${s.title}?`}>
                  <span>Delete <strong>{s.title.length > 24 ? s.title.slice(0, 24) + "…" : s.title}</strong>?</span>
                  <button className="btn btn-sm btn-danger" onClick={() => del(s.id, s.title)}>Delete chat</button>
                  <button className="btn btn-sm btn-ghost" onClick={() => setConfirmId(null)}>Keep</button>
                </div>
              ) : (
                <button className="btn btn-sm btn-ghost" style={{ marginTop: 4 }} aria-label={`Delete ${s.title}`}
                  title="Delete chat" onClick={() => setConfirmId(s.id)}>
                  <ITrash />
                </button>
              )}
            </div>
          ))}
        </div>
        <div className="sidebar-foot">
          <button className="btn btn-ghost" style={{ width: "100%", justifyContent: "flex-start" }} onClick={logout}>
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
}
