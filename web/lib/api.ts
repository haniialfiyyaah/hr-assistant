"use client";

/** Same-origin paths; Next rewrites proxy to FastAPI. */
export const API_PATHS = {
  chat: "/api/v1/chat",
  currentConversation: "/api/v1/conversations/current",
  conversations: "/api/v1/conversations",
  conversation: (conversationId: string) =>
    `/api/v1/conversations/${conversationId}`,
  confirm: (proposalId: string) =>
    `/api/v1/action-proposals/${proposalId}/confirm`,
  myRequests: "/api/v1/leave-requests/me",
  monitoringSummary: "/api/v1/monitoring/summary",
  monitoringAlerts: "/api/v1/monitoring/alerts",
} as const;

export const CONVERSATIONS_CHANGED_EVENT = "hr-conversations-changed";
export const NEW_CHAT_EVENT = "hr-new-chat";

export function notifyConversationsChanged(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(CONVERSATIONS_CHANGED_EVENT));
  }
}

export function notifyNewChat(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(NEW_CHAT_EVENT));
  }
}

const REQUEST_TIMEOUT_MS = 60_000;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function apiRequest<T>(
  method: string,
  path: string,
  token: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
  });

  if (!response.ok) {
    const raw = await response.text();
    let detail = raw || response.statusText;
    try {
      const payload = JSON.parse(raw) as { detail?: unknown };
      if (typeof payload.detail === "string" && payload.detail) {
        detail = payload.detail;
      } else if (payload.detail != null) {
        detail = JSON.stringify(payload.detail);
      }
    } catch {
      // keep raw text
    }
    throw new ApiError(response.status, detail || `API ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
