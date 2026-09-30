"use client";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "../../components/sidebar";
import { getAccess } from "../../lib/api";
import { useAuth } from "../../lib/store";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const ready = useAuth((s: { ready: boolean }) => s.ready);
  const setReady = useAuth((s: { setReady: () => void }) => s.setReady);

  useEffect(() => {
    if (!getAccess()) router.replace(`/login?next=${encodeURIComponent(pathname ?? "/chat")}`);
    else setReady();
  }, [router, pathname, setReady]);

  if (!ready) {
    return (
      <main className="page" aria-busy="true">
        <div className="skel" style={{ height: 28, width: 220, marginBottom: 16 }} />
        <div className="skel" style={{ height: 14, width: "60%", marginBottom: 8 }} />
        <div className="skel" style={{ height: 14, width: "40%" }} />
      </main>
    );
  }
  return (
    <div className="app">
      <Sidebar />
      <div className="main">{children}</div>
    </div>
  );
}
