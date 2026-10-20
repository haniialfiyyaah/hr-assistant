"use client";

import type { SessionUser } from "@/lib/demo-accounts";

const SESSION_KEY = "hr-assistant.session";
const THREAD_PREFIX = "hr-assistant.thread.";
const IDEM_PREFIX = "hr-assistant.idem.";

export function readSession(): SessionUser | null {
  if (typeof window === "undefined") {
    return null;
  }
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}

export function writeSession(user: SessionUser): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
}

/** Clears identity, visible thread, and confirm keys (persona switch / sign-out). */
export function clearSession(): void {
  const previous = readSession();
  sessionStorage.removeItem(SESSION_KEY);
  if (previous) {
    sessionStorage.removeItem(`${THREAD_PREFIX}${previous.employeeId}`);
  }
  for (const key of Object.keys(sessionStorage)) {
    if (key.startsWith(IDEM_PREFIX) || key.startsWith(THREAD_PREFIX)) {
      sessionStorage.removeItem(key);
    }
  }
}

export interface ChatCitation {
  document_id: string;
  title: string;
  section: string;
  excerpt: string;
}

export interface ChatToolCall {
  name: string;
  status: string;
  duration_ms: number;
}

export interface ChatProposal {
  proposal_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  business_days: number;
  reason?: string | null;
  validation_summary?: string[];
}

export interface ChatResponsePayload {
  answer: string;
  outcome: string;
  citations: ChatCitation[];
  tool_calls: ChatToolCall[];
  action_proposal: ChatProposal | null;
  trace_id: string;
}

export interface ThreadMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  response?: ChatResponsePayload;
}

export function readThread(employeeId: string): ThreadMessage[] {
  const raw = sessionStorage.getItem(`${THREAD_PREFIX}${employeeId}`);
  if (!raw) {
    return [];
  }
  try {
    return JSON.parse(raw) as ThreadMessage[];
  } catch {
    return [];
  }
}

export function writeThread(employeeId: string, messages: ThreadMessage[]): void {
  sessionStorage.setItem(`${THREAD_PREFIX}${employeeId}`, JSON.stringify(messages));
}

export function getIdempotencyKey(proposalId: string): string {
  const key = `${IDEM_PREFIX}${proposalId}`;
  const existing = sessionStorage.getItem(key);
  if (existing) {
    return existing;
  }
  const generated =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `idem-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  sessionStorage.setItem(key, generated);
  return generated;
}
