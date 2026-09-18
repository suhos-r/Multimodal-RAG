"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "../../components/sidebar";
import { getAccess } from "../../lib/api";
import { useAuth } from "../../lib/store";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const ready = useAuth((s: { ready: boolean }) => s.ready);
  const setReady = useAuth((s: { setReady: () => void }) => s.setReady);

  useEffect(() => {
    if (!getAccess()) router.replace("/login");
    else setReady();
  }, [router, setReady]);

  if (!ready) return <main className="page">Loading…</main>;
  return (
    <div className="app">
      <Sidebar />
      <div className="main">{children}</div>
    </div>
  );
}
