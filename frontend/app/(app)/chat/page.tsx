"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../../lib/api";
import type { ChatSession } from "../../../lib/types";

export default function NewChatRedirect() {
  const router = useRouter();
  useEffect(() => {
    api<ChatSession>("/api/sessions", { method: "POST", body: JSON.stringify({}) })
      .then((s) => router.replace(`/chat/${s.id}`))
      .catch(() => router.replace("/login"));
  }, [router]);
  return <main className="page">Starting chat…</main>;
}
