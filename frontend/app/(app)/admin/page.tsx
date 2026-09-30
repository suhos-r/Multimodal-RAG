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

function Card({ label, value, sub, bar, donut }: {
  label: string; value: string; sub?: string; bar?: number; donut?: number;
}) {
  return (
    <div className="card">
      <div className="v numeric">{value}</div>
      <div className="l">{label}</div>
      {bar != null && (
        <div className="bar-track" role="img" aria-label={`${label}: ${Math.round(bar * 100)} percent`}>
          <div className="bar-fill" style={{ width: `${Math.min(100, Math.max(0, bar * 100))}%` }} />
        </div>
      )}
      {donut != null && (
        <div className="donut" role="img" aria-label={`${label}: ${donut} percent`}
          style={{ background: `conic-gradient(var(--positive) ${donut}%, var(--surface-3) 0)` }}>
          <span style={{ background: "var(--surface)", borderRadius: "50%", width: 60, height: 60,
            display: "flex", alignItems: "center", justifyContent: "center" }}>{donut}%</span>
        </div>
      )}
      {sub && <div className="l" style={{ marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

export default function AdminPage() {
  const [s, setS] = useState<Stats | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    api<Stats>("/api/admin/stats")
      .then(setS)
      .catch(() => setErr("Couldn't load stats — is the API running? Retry."));
  }, []);
  if (err) {
    return (
      <main className="page">
        <p className="err" role="alert">{err}</p>
        <button className="btn btn-sm btn-primary" onClick={() => window.location.reload()}>Retry</button>
      </main>
    );
  }
  if (!s) {
    return (
      <main className="page" aria-busy="true" aria-label="Loading stats">
        <div className="cards">{[0, 1, 2, 3, 4, 5].map((i) => <div key={i} className="skel" style={{ height: 108 }} />)}</div>
      </main>
    );
  }
  const totalVotes = s.feedback_up + s.feedback_down;
  return (
    <main className="page">
      <div className="page-head">
        <div className="label">Insights</div>
        <h2>Admin</h2>
        <p>Cache savings, latency and answer quality in the last 24 hours.</p>
      </div>
      <div className="cards">
        <Card label="Cache hit-rate" value={`${(s.cache_hit_rate_24h * 100).toFixed(1)}%`} bar={s.cache_hit_rate_24h} />
        <Card label="LLM calls avoided" value={String(s.llm_calls_avoided)}
          sub={`exact ${s.exact_hits} · semantic ${s.semantic_hits} · near-dup ${s.near_dup_hits}`} />
        <Card label="Tokens saved" value={String(s.tokens_saved)} sub={`$${s.est_usd_saved} — local Ollama is $0 by construction`} />
        <Card label="Avg latency 24h" value={s.avg_latency_ms_24h != null ? `${s.avg_latency_ms_24h} ms` : "—"} />
        <Card label="Tokens 24h" value={String(s.tokens_24h)} />
        {s.helpfulness_pct != null
          ? <Card label="Helpfulness" value={`${s.helpfulness_pct}%`} donut={s.helpfulness_pct}
              sub={`up ${s.feedback_up} · down ${s.feedback_down} of ${totalVotes} votes`} />
          : <Card label="Helpfulness" value="—" sub="No ratings yet — vote on any answer to start." />}
      </div>
    </main>
  );
}
