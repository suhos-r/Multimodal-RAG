"use client";
import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function ChatIndex() {
  const [sessions, setSessions] = useState<any[]>([]);
  useEffect(() => {
    const tok = sessionStorage.getItem("access_token");
    if (!tok) return;
    fetch(`${API}/api/sessions`, { headers: { Authorization: `Bearer ${tok}` } })
      .then((r) => r.json())
      .then(setSessions)
      .catch(() => {});
  }, []);
  return (
    <main style={{ maxWidth: 720, margin: "5vh auto" }}>
      <h1>Chats (Plan 01 stub — full UI in Plan 08)</h1>
      <ul>
        {sessions.map((s) => (
          <li key={s.id}>{s.title}</li>
        ))}
      </ul>
    </main>
  );
}
