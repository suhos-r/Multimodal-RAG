"use client";
// Single inline-SVG icon set. 1.5px stroke, 16px box, currentColor.
// Recognizable shapes only; every icon-only button also gets title + aria-label.
import type { SVGProps } from "react";

function Base({ children, ...p }: SVGProps<SVGSVGElement>) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor"
      strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...p}>
      {children}
    </svg>
  );
}

export const IPlus = () => <Base><path d="M8 3v10M3 8h10" /></Base>;
export const ITrash = () => <Base><path d="M2.5 4h11M6.5 4V2.5h3V4M4 4l.7 9.5h6.6L12 4M6.5 7v4M9.5 7v4" /></Base>;
export const ICopy = () => <Base><rect x="5.5" y="5.5" width="8" height="8" rx="1.5" /><path d="M10.5 5.5v-2a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2" /></Base>;
export const IRefresh = () => <Base><path d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2.5v3h-3" /></Base>;
export const IFlag = () => <Base><path d="M4 13.5v-11M4 3h8.5L10 5.5 12.5 8H4" /></Base>;
export const IX = () => <Base><path d="M4 4l8 8M12 4l-8 8" /></Base>;
export const IUp = () => <Base><path d="M8 13.5v-11M4.5 6 8 2.5 11.5 6" /></Base>;
export const IDown = () => <Base><path d="M8 2.5v11M4.5 10 8 13.5 11.5 10" /></Base>;
export const IUpload = () => <Base><path d="M8 11V2.5M4.5 6 8 2.5 11.5 6M2.5 11v2.5h11V11" /></Base>;
export const IMenu = () => <Base><path d="M2.5 4.5h11M2.5 8h11M2.5 11.5h11" /></Base>;
export const IChat = () => <Base><path d="M2.5 3.5h11v7h-6l-3 2.5v-2.5h-2v-7z" /></Base>;
export const IBook = () => <Base><path d="M3 2.5h8.5A1.5 1.5 0 0 1 13 4v9.5H4.5A1.5 1.5 0 0 1 3 12V2.5zM3 10.5h10" /></Base>;
export const IGauge = () => <Base><path d="M2.5 12.5a6 6 0 1 1 11 0M8 12.5 11 8" /></Base>;
export const IStop = () => <Base><rect x="4" y="4" width="8" height="8" rx="1.5" fill="currentColor" stroke="none" /></Base>;
export const ISend = () => <Base><path d="M13.5 2.5 7.5 8.5M13.5 2.5 9.5 13.5l-2-5-5-2 11-4z" /></Base>;
