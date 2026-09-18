"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { api } from "../lib/api";
import { useAuth } from "../lib/store";
import type { ChatSession } from "../lib/types";

export default function Sidebar() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const params = useParams();
  const router = useRouter();
  const logout = useAuth((s) => s.logout);
  const active = (params?.id as string | undefined) ?? null;

  const load = () => api<ChatSession[]>("/api/sessions").then(setSessions).catch(() => {});
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  async function newChat() {
    const s = await api<ChatSession>("/api/sessions", { method: "POST", body: JSON.stringify({}) });
    setSessions((p) => [s, ...p]);
    router.push(`/chat/${s.id}`);
  }

  async function del(id: string) {
    if (!confirm("Delete this chat?")) return;
    await api(`/api/sessions/${id}`, { method: "DELETE" });
    setSessions((p) => p.filter((s) => s.id !== id));
    if (active === id) router.push("/chat");
  }

  return (
    <aside className="sidebar">
      <button onClick={newChat}>+ New chat</button>
      <Link href="/knowledge"><button style={{ width: "100%" }}>Knowledge base</button></Link>
      <Link href="/admin"><button style={{ width: "100%" }}>Admin</button></Link>
      <div style={{ flex: 1 }}>
        {sessions.map((s) => (
          <div key={s.id} className={`sess ${active === s.id ? "active" : ""}`}>
            <Link href={`/chat/${s.id}`} style={{ textDecoration: "none", color: "inherit" }}>
              <div className="t">{s.title}</div>
              {s.preview && <div className="p">{s.preview}</div>}
            </Link>
            <button onClick={() => del(s.id)} style={{ marginTop: 4, padding: "2px 8px", fontSize: 12 }}>delete</button>
          </div>
        ))}
      </div>
      <button onClick={logout}>Logout</button>
    </aside>
  );
}
