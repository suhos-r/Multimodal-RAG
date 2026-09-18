"use client";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

interface Stats {
  cache_hit_rate_24h: number;
  exact_hits: number;
  semantic_hits: number;
  near_dup_hits: number;
  llm_calls_avoided: number;
  tokens_saved: number;
  est_usd_saved: number;
  avg_latency_ms_24h: number | null;
  tokens_24h: number;
  helpfulness_pct: number | null;
  feedback_up: number;
  feedback_down: number;
}

export default function AdminPage() {
  const [s, setS] = useState<Stats | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api<Stats>("/api/admin/stats").then(setS).catch((e: any) => setErr(String(e)));
  }, []);
  if (err) return <main className="page"><p className="err">{err}</p></main>;
  if (!s) return <main className="page">Loading…</main>;
  const cards: [string, string][] = [
    ["Cache hit-rate", `${(s.cache_hit_rate_24h * 100).toFixed(1)}%`],
    ["LLM calls avoided", String(s.llm_calls_avoided)],
    ["Tokens saved", String(s.tokens_saved)],
    ["Avg latency 24h", s.avg_latency_ms_24h != null ? `${s.avg_latency_ms_24h} ms` : "—"],
    ["Tokens 24h", String(s.tokens_24h)],
    ["Helpfulness", s.helpfulness_pct != null ? `${s.helpfulness_pct}% (👍${s.feedback_up}/👎${s.feedback_down})` : "no ratings yet"],
  ];
  return (
    <main className="page">
      <h2>Admin</h2>
      <div className="cards">
        {cards.map(([l, v]) => (
          <div key={l} className="card"><div className="v">{v}</div><div className="l">{l}</div></div>
        ))}
      </div>
      <p style={{ fontSize: 13, color: "var(--muted)" }}>
        exact {s.exact_hits} · semantic {s.semantic_hits} · near-dup {s.near_dup_hits} ·
        est. saved ${s.est_usd_saved} (local Ollama is $0 by construction)
      </p>
    </main>
  );
}
