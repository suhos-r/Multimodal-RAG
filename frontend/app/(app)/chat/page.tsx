"use client";
import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../../lib/api";
import type { ChatSession } from "../../../lib/types";

export default function NewChatRedirect() {
  const router = useRouter();
  // Ref guard (not state): survives StrictMode remount, so exactly one
  // session is created no matter how many times the effect re-fires.
  const started = useRef(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    api<ChatSession>("/api/sessions", { method: "POST", body: JSON.stringify({}) })
      .then((s) => router.replace(`/chat/${s.id}`))
      .catch(() => router.replace("/login"));
  }, [router]);
  return (
    <main className="page" aria-busy="true" aria-label="Starting new chat">
      <div className="skel" style={{ height: 28, width: 200, marginBottom: 12 }} />
      <div className="skel" style={{ height: 14, width: "50%" }} />
    </main>
  );
}
