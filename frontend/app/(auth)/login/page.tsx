"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState({ email: false, password: false });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  const next = useSearchParams()?.get("next") || "/chat";

  const emailBad = touched.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const pwBad = touched.password && password.length < 8;
  const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && password.length >= 8;

  async function submit(mode: "login" | "signup") {
    setTouched({ email: true, password: true });
    setErr("");
    if (!valid) return; // validate on click, keep input intact
    setBusy(true);
    try {
      const r = await fetch(`${API}/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        setErr(body.detail ?? (r.status === 401 ? "Wrong email or password." : `Sign in failed (${r.status}). Retry.`));
        return;
      }
      const tok = await r.json();
      sessionStorage.setItem("access_token", tok.access_token);
      localStorage.setItem("refresh_token", tok.refresh_token);
      router.push(next);
    } catch {
      setErr("Can't reach the API — is the backend running on :8000?");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-wrap">
      <div className="login-panel">
        <div className="brand">
          <span className="brand-mark">R</span>
          <span className="brand-name">RAG Console</span>
        </div>
        <h1>Sign in</h1>
        <p className="sub">Private answers, cited sources. Your chats stay yours.</p>
        <div className="field">
          <label htmlFor="login-email">Email</label>
          <input id="login-email" type="email" autoComplete="email" value={email}
            onChange={(e) => setEmail(e.target.value)} onBlur={() => setTouched((t) => ({ ...t, email: true }))}
            aria-invalid={emailBad} aria-describedby={emailBad ? "login-email-err" : undefined} />
          {emailBad && <span className="error-text" id="login-email-err">Emails need an @ and a domain.</span>}
        </div>
        <div className="field">
          <label htmlFor="login-pw">Password</label>
          <input id="login-pw" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} onBlur={() => setTouched((t) => ({ ...t, password: true }))}
            aria-invalid={pwBad} aria-describedby={pwBad ? "login-pw-err" : undefined}
            onKeyDown={(e) => { if (e.key === "Enter") submit("login"); }} />
          {pwBad
            ? <span className="error-text" id="login-pw-err">8+ characters.</span>
            : <span className="hint">8+ characters.</span>}
        </div>
        {err && <p className="err" role="alert">{err}</p>}
        <div className="login-actions">
          <button className="btn btn-primary" onClick={() => submit("login")} disabled={busy} aria-busy={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <button className="btn" onClick={() => submit("signup")} disabled={busy}>Create account</button>
        </div>
      </div>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<main className="login-wrap"><p className="spin">Loading</p></main>}>
      <LoginForm />
    </Suspense>
  );
}
