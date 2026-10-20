"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ArrowUp,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  LoaderCircle,
  Sparkles,
  Wrench,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { ChatMarkdown } from "@/components/chat-markdown";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  apiRequest,
  API_PATHS,
  ApiError,
  notifyConversationsChanged,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import {
  readConversationId,
  readThread,
  writeConversationId,
  writeThread,
  type ChatResponsePayload,
  type ConversationPayload,
  type ServerThreadMessage,
  type ThreadMessage,
} from "@/lib/session";

const EXAMPLES = [
  {
    label: "Annual leave policy",
    prompt: "How many annual leave days do permanent employees get?",
  },
  {
    label: "My balance",
    prompt: "What is my leave balance?",
  },
  {
    label: "Prepare leave",
    prompt: "Prepare annual leave from 2026-11-02 to 2026-11-03",
  },
] as const;

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function formatTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return "";
  }
}

function toThreadMessage(message: ServerThreadMessage): ThreadMessage {
  const hasExtras = Boolean(message.outcome || message.action_proposal);
  return {
    id: message.message_id,
    role: message.role,
    content: message.content,
    createdAt: message.created_at,
    response: hasExtras
      ? {
          answer: message.content,
          outcome: message.outcome ?? "answered",
          citations: [],
          tool_calls: [],
          action_proposal: message.action_proposal,
          trace_id: "",
        }
      : undefined,
  };
}

function outcomeTone(outcome: string): string {
  switch (outcome) {
    case "action_proposed":
      return "border-teal-600/20 bg-teal-50 text-teal-900";
    case "answered":
      return "border-sky-600/20 bg-sky-50 text-sky-900";
    case "escalated":
      return "border-amber-600/20 bg-amber-50 text-amber-950";
    case "abstained":
      return "border-stone-400/30 bg-stone-100 text-stone-700";
    default:
      return "border-border bg-muted text-muted-foreground";
  }
}

export function ChatThread() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedId = searchParams.get("c");
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [hydrating, setHydrating] = useState(true);
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const messagesRef = useRef(messages);
  const conversationIdRef = useRef(conversationId);
  const sendingRef = useRef(sending);
  const hydratingRef = useRef(hydrating);

  messagesRef.current = messages;
  conversationIdRef.current = conversationId;
  sendingRef.current = sending;
  hydratingRef.current = hydrating;

  useEffect(() => {
    if (!user) {
      return;
    }
    const employeeId = user.employeeId;
    const token = user.demoToken;
    let cancelled = false;
    setMessages(readThread(employeeId));
    setConversationId(requestedId ?? readConversationId(employeeId));
    setHydrating(true);
    const path = requestedId
      ? API_PATHS.conversation(requestedId)
      : API_PATHS.currentConversation;
    apiRequest<ConversationPayload>("GET", path, token)
      .then((payload) => {
        // Do not wipe an in-flight "confirm" bubble with a stale server snapshot.
        if (cancelled || sendingRef.current) {
          return;
        }
        const next = payload.messages.map(toThreadMessage);
        setMessages(next);
        setConversationId(payload.conversation_id);
        writeThread(employeeId, next);
        writeConversationId(employeeId, payload.conversation_id);
        if (!requestedId && payload.conversation_id) {
          router.replace(`/?c=${payload.conversation_id}`, { scroll: false });
        }
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }
        const detail = error instanceof Error ? error.message : "Could not load the saved conversation.";
        toast.error(detail);
      })
      .finally(() => {
        if (!cancelled) {
          setHydrating(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user, requestedId, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  if (!user) {
    return null;
  }

  const session = user;

  function persist(next: ThreadMessage[], nextConversationId: string | null) {
    messagesRef.current = next;
    conversationIdRef.current = nextConversationId;
    setMessages(next);
    setConversationId(nextConversationId);
    writeThread(session.employeeId, next);
    writeConversationId(session.employeeId, nextConversationId);
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sendingRef.current || hydratingRef.current) {
      return;
    }
    const activeConversationId = conversationIdRef.current;
    const userMessage: ThreadMessage = {
      id: newId(),
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
    };
    const withUser = [...messagesRef.current, userMessage];
    persist(withUser, activeConversationId);
    setDraft("");
    sendingRef.current = true;
    setSending(true);
    try {
      const result = await apiRequest<ChatResponsePayload>(
        "POST",
        API_PATHS.chat,
        session.demoToken,
        {
          message: trimmed,
          ...(activeConversationId
            ? { conversation_id: activeConversationId }
            : {}),
        },
      );
      const assistantMessage: ThreadMessage = {
        id: newId(),
        role: "assistant",
        content: result.answer,
        createdAt: new Date().toISOString(),
        response: result,
      };
      const nextConversationId = result.conversation_id ?? activeConversationId;
      persist([...withUser, assistantMessage], nextConversationId);
      notifyConversationsChanged();
      if (nextConversationId && nextConversationId !== requestedId) {
        router.replace(`/?c=${nextConversationId}`, { scroll: false });
      }
    } catch (error) {
      const detail =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "Request failed";
      toast.error(detail);
      const assistantMessage: ThreadMessage = {
        id: newId(),
        role: "assistant",
        content: `Could not complete that request: ${detail}`,
        createdAt: new Date().toISOString(),
      };
      persist([...withUser, assistantMessage], activeConversationId);
    } finally {
      sendingRef.current = false;
      setSending(false);
      composerRef.current?.focus();
    }
  }

  function confirmFromChat() {
    void sendMessage("confirm");
  }

  async function startNewChat() {
    if (sending || hydrating) {
      return;
    }
    try {
      const created = await apiRequest<ConversationPayload>(
        "POST",
        API_PATHS.conversations,
        session.demoToken,
      );
      persist([], created.conversation_id);
      setDraft("");
      notifyConversationsChanged();
      if (created.conversation_id) {
        router.push(`/?c=${created.conversation_id}`);
      }
      composerRef.current?.focus();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not start a new chat.");
    }
  }

  const canSend = Boolean(draft.trim()) && !sending && !hydrating;

  return (
    <div className="relative flex h-full min-h-0 flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-white/55 to-transparent" />

      <header className="relative z-10 flex items-end justify-between gap-3 border-b border-stone-200/70 px-4 py-3 backdrop-blur-sm sm:gap-4 sm:px-6 sm:py-4">
        <div className="min-w-0">
          <div className="mb-1 hidden items-center gap-2 md:flex">
            <span className="inline-flex size-7 items-center justify-center rounded-full bg-teal-800 text-white shadow-sm">
              <Sparkles className="size-3.5" />
            </span>
            <p className="text-xs font-medium tracking-[0.14em] text-teal-800/80 uppercase">
              Assistant
            </p>
          </div>
          <h1 className="text-lg font-semibold tracking-tight text-stone-900 sm:text-xl md:text-2xl">
            How can I help with leave or policy?
          </h1>
          <p className="mt-1 hidden max-w-xl text-sm text-stone-500 sm:block">
            Follow-ups stay on this account. You can say next week, or correct a
            typo. Leave is created only after Confirm.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="rounded-full"
            disabled={sending || hydrating}
            onClick={() => {
              void startNewChat();
            }}
          >
            New chat
          </Button>
          <div className="hidden rounded-full border border-stone-200 bg-white/80 px-3 py-1.5 text-xs text-stone-500 lg:block">
            Signed in as {session.displayName.split(" ")[0]}
          </div>
        </div>
      </header>

      <div className="relative z-10 min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 py-4 sm:px-6 sm:py-6">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-4 sm:gap-5">
          {messages.length === 0 ? (
            <div className="chat-rise flex flex-col items-center gap-5 py-8 text-center sm:gap-6 sm:py-12">
              <div className="flex size-12 items-center justify-center rounded-2xl border border-teal-700/15 bg-white/80 shadow-[0_12px_40px_-24px_oklch(0.4_0.08_200)] sm:size-14">
                <BookOpen className="size-5 text-teal-800 sm:size-6" />
              </div>
              <div className="max-w-md px-1">
                <p className="text-base font-medium tracking-tight text-stone-900 sm:text-lg">
                  Start a policy or leave conversation
                </p>
                <p className="mt-2 text-sm leading-relaxed text-stone-500">
                  Try a demo prompt below, or write your own. Leave proposals
                  still need an explicit Confirm.
                </p>
              </div>
              <div className="flex w-full max-w-lg flex-col gap-2 sm:flex-row sm:flex-wrap sm:justify-center">
                {EXAMPLES.map((example) => (
                  <button
                    key={example.label}
                    type="button"
                    onClick={() => {
                      setDraft(example.prompt);
                      composerRef.current?.focus();
                    }}
                    className="w-full rounded-2xl border border-stone-200/90 bg-white/85 px-4 py-3 text-left shadow-sm transition-[transform,opacity,background-color] duration-200 ease-out hover:bg-white active:scale-[0.98] sm:w-auto sm:max-w-[15rem]"
                  >
                    <p className="text-sm font-medium text-stone-800">
                      {example.label}
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-stone-500">
                      {example.prompt}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          {messages.map((message, index) => {
            const isUser = message.role === "user";
            return (
              <div
                key={message.id}
                className={cn(
                  "chat-rise flex gap-3",
                  isUser ? "justify-end" : "justify-start",
                )}
                style={{ animationDelay: `${Math.min(index, 6) * 20}ms` }}
              >
                {!isUser ? (
                  <div className="mt-1 hidden size-8 shrink-0 items-center justify-center rounded-full bg-teal-800 text-[11px] font-semibold text-white sm:flex">
                    HR
                  </div>
                ) : null}
                <div
                  className={cn(
                    "flex min-w-0 max-w-[min(100%,36rem)] flex-1 flex-col gap-1.5 sm:flex-none",
                    isUser && "items-end",
                  )}
                >
                  <div
                    className={cn(
                      "px-3.5 py-2.5 text-[15px] leading-relaxed shadow-sm sm:px-4 sm:py-3",
                      isUser
                        ? "rounded-[1.35rem] rounded-br-md bg-stone-900 text-stone-50"
                        : "rounded-[1.35rem] rounded-bl-md border border-stone-200/80 bg-white/90 text-stone-800",
                    )}
                  >
                    <ChatMarkdown
                      content={message.content}
                      tone={isUser ? "user" : "assistant"}
                    />
                    {message.response ? (
                      <AssistantExtras
                        response={message.response}
                        confirming={sending}
                        onConfirm={confirmFromChat}
                      />
                    ) : null}
                  </div>
                  <p className="px-1 text-[11px] text-stone-400">
                    {isUser ? "You" : "Assistant"} · {formatTime(message.createdAt)}
                  </p>
                </div>
                {isUser ? (
                  <div className="mt-1 hidden size-8 shrink-0 items-center justify-center rounded-full bg-stone-200 text-[11px] font-semibold text-stone-700 sm:flex">
                    {session.displayName.slice(0, 1).toUpperCase()}
                  </div>
                ) : null}
              </div>
            );
          })}

          {sending ? (
            <div className="chat-rise flex items-start gap-3">
              <div className="mt-1 hidden size-8 shrink-0 items-center justify-center rounded-full bg-teal-800 text-[11px] font-semibold text-white sm:flex">
                HR
              </div>
              <div className="rounded-[1.35rem] rounded-bl-md border border-stone-200/80 bg-white/90 px-4 py-3 shadow-sm">
                <div className="flex items-center gap-1.5">
                  <span className="chat-dot size-1.5 rounded-full bg-stone-400" />
                  <span className="chat-dot size-1.5 rounded-full bg-stone-400" />
                  <span className="chat-dot size-1.5 rounded-full bg-stone-400" />
                </div>
              </div>
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="relative z-10 border-t border-stone-200/70 bg-white/75 px-3 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] backdrop-blur-md sm:px-6 sm:py-4">
        <form
          className="mx-auto w-full max-w-3xl"
          onSubmit={(event) => {
            event.preventDefault();
            void sendMessage(draft);
          }}
        >
          <div className="rounded-[1.25rem] border border-stone-200 bg-white p-2 shadow-[0_18px_50px_-30px_oklch(0.35_0.04_220)] transition-[border-color,box-shadow] duration-200 ease-out focus-within:border-teal-700/30 focus-within:shadow-[0_18px_50px_-28px_oklch(0.45_0.06_190)] sm:rounded-[1.5rem]">
            <Textarea
              ref={composerRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Message the HR assistant…"
              rows={2}
              className="min-h-[3.75rem] resize-none border-0 bg-transparent px-3 py-2 text-[15px] shadow-none focus-visible:ring-0 sm:min-h-[4.5rem]"
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage(draft);
                }
              }}
            />
            <div className="flex items-center justify-between gap-2 px-1 pb-0.5 sm:gap-3 sm:px-2 sm:pb-1">
              <p className="hidden text-[11px] text-stone-400 sm:block">
                Enter to send · Shift+Enter for a new line
              </p>
              <p className="text-[11px] text-stone-400 sm:hidden">Enter to send</p>
              <Button
                type="submit"
                size="sm"
                disabled={!canSend}
                className="shrink-0 rounded-full bg-teal-800 text-white hover:bg-teal-700 active:scale-[0.97]"
              >
                {sending ? (
                  <LoaderCircle className="animate-spin" data-icon="inline-start" />
                ) : (
                  <ArrowUp data-icon="inline-start" />
                )}
                Send
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}

function AssistantExtras({
  response,
  confirming,
  onConfirm,
}: {
  response: ChatResponsePayload;
  confirming: boolean;
  onConfirm: () => void;
}) {
  const proposal = response.action_proposal;
  return (
    <div className="mt-4 flex flex-col gap-3 border-t border-stone-200/80 pt-3 text-stone-800">
      <div className="flex flex-wrap gap-2">
        <span
          className={cn(
            "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium capitalize",
            outcomeTone(response.outcome),
          )}
        >
          {response.outcome.replaceAll("_", " ")}
        </span>
        {response.trace_id ? (
          <Badge variant="outline" className="font-mono text-[10px]">
            {response.trace_id}
          </Badge>
        ) : null}
      </div>

      {response.citations?.length ? (
        <div className="flex flex-col gap-2">
          <p className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-stone-500 uppercase">
            <BookOpen className="size-3.5" />
            Policy sources
          </p>
          {response.citations.map((citation, index) => (
            <div
              key={`${citation.document_id}-${index}`}
              className="rounded-xl border border-stone-200/80 bg-stone-50/90 p-3 text-xs"
            >
              <p className="font-medium text-stone-800">
                {citation.document_id}
                {citation.section ? ` — ${citation.section}` : ""}
              </p>
              <p className="mt-1.5 leading-relaxed text-stone-500">
                {citation.excerpt}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      {response.tool_calls?.length ? (
        <div className="flex flex-col gap-1.5">
          <p className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-stone-500 uppercase">
            <Wrench className="size-3.5" />
            Tools
          </p>
          {response.tool_calls.map((tool, index) => (
            <p
              key={`${tool.name}-${index}`}
              className="font-mono text-[11px] text-stone-500"
            >
              {tool.name}
              <span className="text-stone-400">
                {" "}
                · {tool.status} · {tool.duration_ms} ms
              </span>
            </p>
          ))}
        </div>
      ) : null}

      {proposal ? (
        <div className="overflow-hidden rounded-2xl border border-teal-800/15 bg-gradient-to-br from-teal-50 to-white">
          <div className="flex items-start gap-2 border-b border-teal-800/10 px-4 py-3">
            <CalendarDays className="mt-0.5 size-4 text-teal-800" />
            <div>
              <p className="text-sm font-medium text-teal-950">
                Leave proposal ready
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-teal-900/70">
                Not created yet. Use the button or type confirm in chat.
              </p>
            </div>
          </div>
          <div className="grid gap-3 px-4 py-3 text-sm sm:grid-cols-3">
            <div>
              <p className="text-[11px] tracking-wide text-stone-500 uppercase">
                Type
              </p>
              <p className="mt-0.5 font-medium capitalize">{proposal.leave_type}</p>
            </div>
            <div>
              <p className="text-[11px] tracking-wide text-stone-500 uppercase">
                Dates
              </p>
              <p className="mt-0.5 font-medium">
                {proposal.start_date} → {proposal.end_date}
              </p>
            </div>
            <div>
              <p className="text-[11px] tracking-wide text-stone-500 uppercase">
                Business days
              </p>
              <p className="mt-0.5 font-medium">{proposal.business_days}</p>
            </div>
          </div>
          {proposal.reason ? (
            <p className="border-t border-teal-800/10 px-4 py-2 text-xs text-stone-500">
              Reason: {proposal.reason}
            </p>
          ) : null}
          <div className="px-4 pb-4">
            <Button
              type="button"
              className="w-full rounded-full bg-teal-800 text-white hover:bg-teal-700 active:scale-[0.98] sm:w-auto"
              size="sm"
              disabled={confirming}
              onClick={(event) => {
                event.preventDefault();
                event.stopPropagation();
                onConfirm();
              }}
            >
              {confirming ? (
                <LoaderCircle className="animate-spin" data-icon="inline-start" />
              ) : (
                <CheckCircle2 data-icon="inline-start" />
              )}
              {confirming ? "Confirming…" : "Confirm pending leave request"}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
