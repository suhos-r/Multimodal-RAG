"use client";
import { Fragment, useEffect, useRef } from "react";
import type { Citation } from "../lib/types";

/** Render assistant text, turning [n] markers into lamp citation chips.
 * Chips pulse once when they first appear (keyed by message id + citation). */
export function CitedText({ text, citations, onCite, pulseKey }: {
  text: string;
  citations: Citation[];
  onCite: (c: Citation) => void;
  pulseKey?: string;
}) {
  const seen = useRef<Set<string>>(new Set());
  useEffect(() => { seen.current = new Set(); }, [pulseKey]);
  const parts = text.split(/(\[\d+\])/g);
  return (
    <span>
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        if (!m) return <Fragment key={i}>{p}</Fragment>;
        const c = citations.find((c) => c.id === Number(m[1]));
        if (!c) return <Fragment key={i}>{p}</Fragment>;
        const k = `${pulseKey}:${c.id}`;
        const lit = pulseKey != null && !seen.current.has(k);
        seen.current.add(k);
        return (
          <button key={i} className={`cite${lit ? " lit" : ""}`} onClick={() => onCite(c)}
            title={`${c.filename} p.${c.page ?? "?"}`} aria-label={`Open source ${c.id}: ${c.filename}`}>
            [{c.id}]
          </button>
        );
      })}
    </span>
  );
}
