export interface Citation {
  id: number;
  doc_id: string;
  filename: string;
  page: number | null;
  modality: string;
  quote: string;
  score: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  model?: string | null;
  cached?: boolean;
  created_at?: string;
}

export interface ChatSession {
  id: string;
  title: string;
  updated_at: string;
  preview?: string | null;
}

export interface DocInfo {
  doc_id: string;
  filename: string;
  mime: string;
  scope: string;
  status: string;
  page_count: number | null;
  error?: string | null;
}

export interface DonePayload {
  answer: string;
  citations: Citation[];
  cached: boolean;
  tier?: string;
  mode?: string;
  iters?: number;
  model: string;
  latency_ms: number;
}
