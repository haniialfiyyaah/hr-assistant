"use client";

import type { SessionUser } from "@/lib/demo-accounts";

const SESSION_KEY = "hr-assistant.session";
const THREAD_PREFIX = "hr-assistant.thread.";
const CONVERSATION_PREFIX = "hr-assistant.conversation.";
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
    if (
      key.startsWith(IDEM_PREFIX) ||
      key.startsWith(THREAD_PREFIX) ||
      key.startsWith(CONVERSATION_PREFIX)
    ) {
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
  conversation_id?: string | null;
}

export interface ServerThreadMessage {
  message_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  outcome: string | null;
  action_proposal: ChatProposal | null;
}

export interface ConversationPayload {
  conversation_id: string | null;
  messages: ServerThreadMessage[];
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

export function readConversationId(employeeId: string): string | null {
  return sessionStorage.getItem(`${CONVERSATION_PREFIX}${employeeId}`);
}

export function writeConversationId(
  employeeId: string,
  conversationId: string | null,
): void {
  const key = `${CONVERSATION_PREFIX}${employeeId}`;
  if (!conversationId) {
    sessionStorage.removeItem(key);
    return;
  }
  sessionStorage.setItem(key, conversationId);
}

/** Stable across the Confirm button and chat "confirm" for the same proposal. */
export function getIdempotencyKey(proposalId: string, employeeId: string): string {
  return `confirm-${employeeId}-${proposalId}`;
}
