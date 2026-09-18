"use client";
// Tiny typed API wrapper: attaches JWT, refreshes once on 401.
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function getAccess(): string | null {
  return typeof window === "undefined" ? null : sessionStorage.getItem("access_token");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const doFetch = (tok: string | null) =>
    fetch(`${API}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init.headers ?? {}), ...(tok ? { Authorization: `Bearer ${tok}` } : {}) },
    });
  let r = await doFetch(getAccess());
  if (r.status === 401) {
    const refresh = typeof window === "undefined" ? null : localStorage.getItem("refresh_token");
    if (refresh) {
      const rr = await fetch(`${API}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
      if (rr.ok) {
        const tok = await rr.json();
        sessionStorage.setItem("access_token", tok.access_token);
        localStorage.setItem("refresh_token", tok.refresh_token);
        r = await doFetch(tok.access_token);
      }
    }
  }
  if (!r.ok) {
    const body = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${r.status}`);
  }
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export function authHeader(): Record<string, string> {
  const t = getAccess();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export { API };
