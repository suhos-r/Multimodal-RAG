"use client";
import { useEffect, useRef } from "react";

// Amber particle field — canvas 2D, no dependencies.
// Full-page ambient layer: pointer-events none, form stays above and interactive.
const RGB = "233, 181, 81"; // #e9b451 — matches the logo mark
const DESKTOP_COUNT = 52;
const MOBILE_COUNT = 22;
const MOBILE_BREAKPOINT = 700;
const LINK_DIST = 130;
const MOUSE_RADIUS = 150;
const INNER_PUSH = 48; // inside this range the cursor gently repels instead of attracting
const MAX_DPR = 2;

interface P {
  x: number; y: number; vx: number; vy: number;
  r: number; a: number; tw: number; // base alpha + twinkle phase
}

function makeParticles(n: number, w: number, h: number): P[] {
  const out: P[] = [];
  for (let i = 0; i < n; i++) {
    const sp = 0.12 + Math.random() * 0.22; // px/frame @60fps — slow drift
    const ang = Math.random() * Math.PI * 2;
    out.push({
      x: Math.random() * w, y: Math.random() * h,
      vx: Math.cos(ang) * sp, vy: Math.sin(ang) * sp,
      r: 0.8 + Math.random() * 1.6,
      a: 0.22 + Math.random() * 0.28,
      tw: Math.random() * Math.PI * 2,
    });
  }
  return out;
}

export default function ParticleField() {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const mouse = { x: -9999, y: -9999 };
    let parts: P[] = [];
    let raf = 0;
    let running = false;
    let last = 0;

    const count = () => (window.innerWidth < MOBILE_BREAKPOINT ? MOBILE_COUNT : DESKTOP_COUNT);

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
      const w = canvas!.clientWidth, h = canvas!.clientHeight;
      canvas!.width = Math.max(1, Math.floor(w * dpr));
      canvas!.height = Math.max(1, Math.floor(h * dpr));
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      // keep existing particles if count matches, else reseed (preserves layout on orientation change)
      if (parts.length !== count()) {
        parts = makeParticles(count(), w, h);
      } else {
        for (const p of parts) { p.x = Math.min(p.x, w); p.y = Math.min(p.y, h); }
      }
      if (!running) draw(0); // static frame for reduced-motion / hidden tab
    }

    function draw(t: number) {
      const w = canvas!.clientWidth, h = canvas!.clientHeight;
      ctx!.clearRect(0, 0, w, h);
      // links first (under dots), very faint
      ctx!.lineWidth = 1;
      for (let i = 0; i < parts.length; i++) {
        for (let j = i + 1; j < parts.length; j++) {
          const dx = parts[i].x - parts[j].x, dy = parts[i].y - parts[j].y;
          const d2 = dx * dx + dy * dy;
          if (d2 < LINK_DIST * LINK_DIST) {
            ctx!.strokeStyle = `rgba(${RGB},${(0.07 * (1 - Math.sqrt(d2) / LINK_DIST)).toFixed(3)})`;
            ctx!.beginPath();
            ctx!.moveTo(parts[i].x, parts[i].y);
            ctx!.lineTo(parts[j].x, parts[j].y);
            ctx!.stroke();
          }
        }
      }
      for (const p of parts) {
        const twinkle = 0.75 + 0.25 * Math.sin(t / 1400 + p.tw);
        ctx!.fillStyle = `rgba(${RGB},${(p.a * twinkle).toFixed(3)})`;
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx!.fill();
      }
    }

    function step(t: number) {
      if (!running) return;
      const dt = Math.min((t - last) / 16.7, 3) || 1;
      last = t;
      const w = canvas!.clientWidth, h = canvas!.clientHeight;
      for (const p of parts) {
        // subtle cursor field: attract in outer band, softly repel up close
        const dx = mouse.x - p.x, dy = mouse.y - p.y;
        const d = Math.hypot(dx, dy);
        if (d > 0.5 && d < MOUSE_RADIUS) {
          const f = (1 - d / MOUSE_RADIUS) * 0.028 * dt;
          const s = d < INNER_PUSH ? -1 : 1;
          p.vx += (dx / d) * f * s;
          p.vy += (dy / d) * f * s;
        }
        // damp back toward drift so the cursor never captures particles
        p.vx *= 0.985; p.vy *= 0.985;
        const sp = Math.hypot(p.vx, p.vy);
        if (sp < 0.08) { // re-seed drift if nearly stopped
          const a = Math.random() * Math.PI * 2;
          p.vx += Math.cos(a) * 0.05; p.vy += Math.sin(a) * 0.05;
        }
        if (sp > 0.9) { p.vx *= 0.9 / sp; p.vy *= 0.9 / sp; } // speed cap
        p.x += p.vx * dt; p.y += p.vy * dt;
        if (p.x < -8) p.x = w + 8; if (p.x > w + 8) p.x = -8;
        if (p.y < -8) p.y = h + 8; if (p.y > h + 8) p.y = -8;
      }
      draw(t);
      raf = requestAnimationFrame(step);
    }

    function start() {
      if (running || reduced.matches) return;
      running = true;
      last = performance.now();
      raf = requestAnimationFrame(step);
    }
    function stop() {
      running = false;
      cancelAnimationFrame(raf);
    }
    const onMove = (e: PointerEvent) => {
      const r = canvas!.getBoundingClientRect();
      mouse.x = e.clientX - r.left;
      mouse.y = e.clientY - r.top;
    };
    const onLeave = () => { mouse.x = -9999; mouse.y = -9999; };
    const onVis = () => { if (document.hidden) { stop(); } else { resize(); start(); } };
    const onReduced = () => { if (reduced.matches) { stop(); resize(); } else { resize(); start(); } };

    resize();
    start();
    window.addEventListener("resize", resize);
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerleave", onLeave);
    document.addEventListener("visibilitychange", onVis);
    reduced.addEventListener("change", onReduced);
    return () => {
      stop();
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVis);
      reduced.removeEventListener("change", onReduced);
    };
  }, []);

  return <canvas ref={ref} className="particle-canvas" aria-hidden="true" />;
}
