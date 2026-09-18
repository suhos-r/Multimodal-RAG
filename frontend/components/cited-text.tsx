"use client";
import { Fragment } from "react";
import type { Citation } from "../lib/types";

/** Render assistant text, turning [n] markers into clickable citation chips. */
export function CitedText({ text, citations, onCite }: {
  text: string;
  citations: Citation[];
  onCite: (c: Citation) => void;
}) {
  const parts = text.split(/(\[\d+\])/g);
  return (
    <span>
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/);
        if (!m) return <Fragment key={i}>{p}</Fragment>;
        const c = citations.find((c) => c.id === Number(m[1]));
        if (!c) return <Fragment key={i}>{p}</Fragment>;
        return (
          <button key={i} className="cite" onClick={() => onCite(c)} title={`${c.filename} p.${c.page ?? "?"}`}>
            [{c.id}]
          </button>
        );
      })}
    </span>
  );
}
