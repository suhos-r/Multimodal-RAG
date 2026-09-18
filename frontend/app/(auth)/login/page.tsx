"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const router = useRouter();

  async function submit(mode: "login" | "signup") {
    setErr("");
    const r = await fetch(`${API}/api/auth/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) {
      setErr((await r.json()).detail ?? "failed");
      return;
    }
    const tok = await r.json();
    sessionStorage.setItem("access_token", tok.access_token);
    localStorage.setItem("refresh_token", tok.refresh_token);
    router.push("/chat");
  }

  return (
    <main style={{ maxWidth: 360, margin: "10vh auto" }}>
      <h1>RAG Login</h1>
      <input placeholder="email" value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
      <input placeholder="password (min 8)" type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={{ width: "100%", marginBottom: 8 }} />
      {err && <p style={{ color: "red" }}>{err}</p>}
      <button onClick={() => submit("login")}>Login</button>{" "}
      <button onClick={() => submit("signup")}>Signup</button>
    </main>
  );
}
