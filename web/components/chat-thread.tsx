"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import { apiRequest, API_PATHS, ApiError } from "@/lib/api";
import {
  getIdempotencyKey,
  readThread,
  writeThread,
  type ChatResponsePayload,
  type ThreadMessage,
} from "@/lib/session";

const EXAMPLES = [
  "How many annual leave days do I get?",
  "What is my leave balance?",
];

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function ChatThread() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!user) {
      return;
    }
    setMessages(readThread(user.employeeId));
  }, [user]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  if (!user) {
    return null;
  }

  const session = user;

  function persist(next: ThreadMessage[]) {
    setMessages(next);
    writeThread(session.employeeId, next);
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) {
      return;
    }
    const userMessage: ThreadMessage = {
      id: newId(),
      role: "user",
      content: trimmed,
      createdAt: new Date().toISOString(),
    };
    const withUser = [...messages, userMessage];
    persist(withUser);
    setDraft("");
    setSending(true);
    try {
      const result = await apiRequest<ChatResponsePayload>(
        "POST",
        API_PATHS.chat,
        session.demoToken,
        { message: trimmed },
      );
      const assistantMessage: ThreadMessage = {
        id: newId(),
        role: "assistant",
        content: result.answer,
        createdAt: new Date().toISOString(),
        response: result,
      };
      persist([...withUser, assistantMessage]);
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
      persist([...withUser, assistantMessage]);
    } finally {
      setSending(false);
    }
  }

  async function confirmProposal(proposalId: string) {
    setConfirming(proposalId);
    try {
      const result = await apiRequest<{
        request_id: string;
        status: string;
        idempotent_replay?: boolean;
      }>("POST", API_PATHS.confirm(proposalId), session.demoToken, {
        idempotency_key: getIdempotencyKey(proposalId),
      });
      toast.success(
        `Created ${result.request_id} (${result.status})${
          result.idempotent_replay ? " — idempotent replay" : ""
        }`,
      );
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Confirm failed",
      );
    } finally {
      setConfirming(null);
    }
  }

  return (
    <div className="mx-auto flex h-[calc(100vh-7rem)] w-full max-w-3xl flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Chat</h1>
        <p className="text-sm text-muted-foreground">
          History stays in this browser only. Each send posts the latest message
          alone to the API.
        </p>
      </div>

      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <ScrollArea className="flex-1 px-4 py-4">
          <div className="flex flex-col gap-4">
            {messages.length === 0 ? (
              <div className="flex flex-col gap-3 py-10 text-center">
                <p className="text-sm text-muted-foreground">
                  Ask a question or request. Examples:
                </p>
                <div className="flex flex-wrap justify-center gap-2">
                  {EXAMPLES.map((example) => (
                    <Button
                      key={example}
                      variant="outline"
                      size="sm"
                      onClick={() => setDraft(example)}
                    >
                      {example}
                    </Button>
                  ))}
                </div>
              </div>
            ) : null}

            {messages.map((message) => (
              <div
                key={message.id}
                className={
                  message.role === "user"
                    ? "ml-8 flex justify-end"
                    : "mr-8 flex justify-start"
                }
              >
                <div
                  className={
                    message.role === "user"
                      ? "max-w-[90%] rounded-2xl bg-primary px-4 py-3 text-sm text-primary-foreground"
                      : "max-w-[90%] rounded-2xl border border-border bg-card px-4 py-3 text-sm"
                  }
                >
                  <p className="whitespace-pre-wrap">{message.content}</p>
                  {message.response ? (
                    <AssistantExtras
                      response={message.response}
                      confirming={confirming}
                      onConfirm={confirmProposal}
                    />
                  ) : null}
                </div>
              </div>
            ))}
            {sending ? (
              <p className="text-sm text-muted-foreground">Working…</p>
            ) : null}
            <div ref={bottomRef} />
          </div>
        </ScrollArea>

        <div className="border-t border-border p-4">
          <form
            className="flex flex-col gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage(draft);
            }}
          >
            <Textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Message the assistant…"
              rows={3}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage(draft);
                }
              }}
            />
            <div className="flex justify-end">
              <Button type="submit" disabled={sending || !draft.trim()}>
                Send
              </Button>
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
}

function AssistantExtras({
  response,
  confirming,
  onConfirm,
}: {
  response: ChatResponsePayload;
  confirming: string | null;
  onConfirm: (proposalId: string) => void;
}) {
  const proposal = response.action_proposal;
  return (
    <div className="mt-3 flex flex-col gap-3 border-t border-border/60 pt-3 text-foreground">
      <div className="flex flex-wrap gap-2">
        <Badge variant="secondary">Outcome: {response.outcome}</Badge>
        <Badge variant="outline">Trace: {response.trace_id}</Badge>
      </div>

      {response.citations?.length ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium text-muted-foreground">
            Policy sources
          </p>
          {response.citations.map((citation, index) => (
            <div
              key={`${citation.document_id}-${index}`}
              className="rounded-lg bg-muted/50 p-2 text-xs"
            >
              <p className="font-medium">
                {citation.document_id}
                {citation.section ? ` — ${citation.section}` : ""}
              </p>
              <p className="mt-1 text-muted-foreground">{citation.excerpt}</p>
            </div>
          ))}
        </div>
      ) : null}

      {response.tool_calls?.length ? (
        <div className="flex flex-col gap-1">
          <p className="text-xs font-medium text-muted-foreground">Tools used</p>
          {response.tool_calls.map((tool, index) => (
            <p key={`${tool.name}-${index}`} className="text-xs text-muted-foreground">
              <code>{tool.name}</code> · {tool.status} · {tool.duration_ms} ms
            </p>
          ))}
        </div>
      ) : null}

      {proposal ? (
        <Alert>
          <AlertTitle>Leave proposal ready</AlertTitle>
          <AlertDescription>
            <p className="mb-2">
              A leave request has not been created yet. Review, then confirm to
              open pending manager review.
            </p>
            <div className="grid gap-2 text-sm sm:grid-cols-3">
              <div>
                <p className="text-xs text-muted-foreground">Type</p>
                <p>{proposal.leave_type}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Dates</p>
                <p>
                  {proposal.start_date} → {proposal.end_date}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Business days</p>
                <p>{proposal.business_days}</p>
              </div>
            </div>
            {proposal.reason ? (
              <p className="mt-2 text-xs text-muted-foreground">
                Reason: {proposal.reason}
              </p>
            ) : null}
            <Button
              className="mt-3"
              size="sm"
              disabled={confirming === proposal.proposal_id}
              onClick={() => onConfirm(proposal.proposal_id)}
            >
              {confirming === proposal.proposal_id
                ? "Confirming…"
                : "Confirm pending leave request"}
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}
    </div>
  );
}
