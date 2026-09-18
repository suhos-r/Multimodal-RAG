import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "RAG Console", description: "Multimodal self-reflective RAG" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
