"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  BookOpen,
  LoaderCircle,
  Sparkles,
  Wrench,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { apiRequest, API_PATHS, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

interface TraceDocument {
  chunk_id?: string;
  document_id: string;
  title?: string;
  section?: string;
  excerpt?: string;
}

interface TraceStep {
  kind: "model" | "tool" | string;
  turn: number;
  input_tokens?: number;
  output_tokens?: number;
  tool_call_count?: number;
  answer_preview?: string;
  name?: string;
  status?: string;
  duration_ms?: number;
  arguments?: Record<string, string>;
}

export interface TracePayload {
  trace_id: string;
  employee_id: string;
  outcome: string;
  model_mode?: string;
  agent_model?: string;
  embedding_model?: string;
  turn_count?: number;
  steps?: TraceStep[];
  retrieved_document_ids: string[];
  retrieved_documents?: TraceDocument[];
  citations?: TraceDocument[];
  tool_calls: Array<{
    name: string;
    status: string;
    duration_ms: number;
  }>;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
}

function outcomeTone(outcome: string): string {
  switch (outcome) {
    case "answered":
    case "action_proposed":
      return "border-teal-800/20 bg-teal-50 text-teal-900";
    case "escalated":
      return "border-amber-500/30 bg-amber-50 text-amber-900";
    case "abstained":
      return "border-stone-400/30 bg-stone-100 text-stone-700";
    default:
      return "border-border bg-muted text-muted-foreground";
  }
}

function PolicyDocCard({ doc }: { doc: TraceDocument }) {
  return (
    <div className="rounded-xl border border-stone-200/80 bg-stone-50/90 p-3 text-xs">
      <p className="font-medium text-stone-800">
        {doc.document_id}
        {doc.section ? ` — ${doc.section}` : ""}
      </p>
      {doc.title && doc.title !== doc.document_id ? (
        <p className="mt-0.5 text-[11px] text-stone-500">{doc.title}</p>
      ) : null}
      {doc.excerpt ? (
        <p className="mt-1.5 leading-relaxed text-stone-500">{doc.excerpt}</p>
      ) : null}
    </div>
  );
}

function StepCard({ step }: { step: TraceStep }) {
  if (step.kind === "tool") {
    return (
      <div className="rounded-xl border border-stone-200/80 bg-white px-3 py-2.5">
        <div className="flex items-center gap-1.5">
          <Wrench className="size-3.5 text-stone-500" />
          <p className="text-[11px] font-medium tracking-wide text-stone-500 uppercase">
            Turn {step.turn} · Tool
          </p>
        </div>
        <p className="mt-1 font-mono text-xs font-medium text-stone-800">
          {step.name}
        </p>
        <p className="mt-0.5 text-[11px] text-stone-500">
          {step.status ?? "—"} · {step.duration_ms ?? 0} ms
        </p>
        {step.arguments && Object.keys(step.arguments).length ? (
          <dl className="mt-2 space-y-1 border-t border-stone-100 pt-2">
            {Object.entries(step.arguments).map(([key, value]) => (
              <div key={key} className="grid grid-cols-[5.5rem_1fr] gap-2 text-[11px]">
                <dt className="font-mono text-stone-400">{key}</dt>
                <dd className="break-words text-stone-600">{value}</dd>
              </div>
            ))}
          </dl>
        ) : null}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-stone-200/80 bg-stone-50/90 px-3 py-2.5">
      <div className="flex items-center gap-1.5">
        <Sparkles className="size-3.5 text-teal-800" />
        <p className="text-[11px] font-medium tracking-wide text-stone-500 uppercase">
          Turn {step.turn} · Model
        </p>
      </div>
      <p className="mt-1 text-[11px] text-stone-500">
        in {step.input_tokens ?? 0} · out {step.output_tokens ?? 0}
        {typeof step.tool_call_count === "number"
          ? ` · ${step.tool_call_count} tool call(s)`
          : ""}
      </p>
      {step.answer_preview ? (
        <p className="mt-1.5 text-xs leading-relaxed text-stone-600">
          {step.answer_preview}
        </p>
      ) : null}
    </div>
  );
}

export function TraceInspector({
  traceId,
  open,
  onOpenChange,
}: {
  traceId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { user } = useAuth();
  const [trace, setTrace] = useState<TracePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showRaw, setShowRaw] = useState(false);

  useEffect(() => {
    if (!open || !traceId || !user) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setTrace(null);
    setShowRaw(false);
    apiRequest<TracePayload>("GET", API_PATHS.trace(traceId), user.demoToken)
      .then((payload) => {
        if (!cancelled) {
          setTrace(payload);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError || err instanceof Error
              ? err.message
              : "Could not load this trace.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, traceId, user]);

  const citations = trace?.citations ?? [];
  const retrievedChunks: TraceDocument[] = trace?.retrieved_documents?.length
    ? trace.retrieved_documents
    : (trace?.retrieved_document_ids ?? []).map((document_id) => ({
        document_id,
      }));
  const steps = trace?.steps ?? [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full gap-0 overflow-y-auto sm:max-w-md"
        showCloseButton
      >
        <SheetHeader className="border-b border-stone-200/80">
          <SheetTitle className="flex items-center gap-2">
            <Activity className="size-4 text-teal-800" />
            Trace inspector
          </SheetTitle>
          <SheetDescription className="font-mono text-[11px] break-all">
            {traceId ?? "—"}
          </SheetDescription>
        </SheetHeader>

        <div className="flex flex-col gap-4 p-4">
          {loading ? (
            <p className="flex items-center gap-2 text-sm text-stone-500">
              <LoaderCircle className="size-4 animate-spin" />
              Loading trace…
            </p>
          ) : null}

          {error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {error}
            </div>
          ) : null}

          {trace ? (
            <>
              <section className="space-y-2">
                <p className="text-[11px] font-medium tracking-wide text-stone-500 uppercase">
                  Run
                </p>
                <div className="flex flex-wrap gap-2">
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium capitalize",
                      outcomeTone(trace.outcome),
                    )}
                  >
                    {trace.outcome.replaceAll("_", " ")}
                  </span>
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {trace.employee_id}
                  </Badge>
                  {typeof trace.turn_count === "number" ? (
                    <Badge variant="outline" className="text-[10px]">
                      {trace.turn_count} turn
                      {trace.turn_count === 1 ? "" : "s"}
                    </Badge>
                  ) : null}
                </div>
              </section>

              <section className="space-y-2">
                <p className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-stone-500 uppercase">
                  <Sparkles className="size-3.5" />
                  Models
                </p>
                <div className="rounded-xl border border-stone-200/80 bg-stone-50/90 px-3 py-2.5 text-xs text-stone-700">
                  <p>
                    <span className="text-stone-400">Mode · </span>
                    {trace.model_mode ?? "—"}
                  </p>
                  <p className="mt-1 font-mono">
                    <span className="font-sans text-stone-400">Agent · </span>
                    {trace.agent_model ?? "—"}
                  </p>
                  <p className="mt-1 font-mono">
                    <span className="font-sans text-stone-400">Embed · </span>
                    {trace.embedding_model ?? "—"}
                  </p>
                </div>
              </section>

              <section className="grid grid-cols-2 gap-2">
                {(
                  [
                    ["Latency", `${trace.latency_ms} ms`],
                    ["Input tokens", String(trace.input_tokens)],
                    ["Output tokens", String(trace.output_tokens)],
                    ["Tools", String(trace.tool_calls?.length ?? 0)],
                  ] as const
                ).map(([label, value]) => (
                  <div
                    key={label}
                    className="rounded-xl border border-stone-200/80 bg-stone-50/80 px-3 py-2"
                  >
                    <p className="text-[10px] tracking-wide text-stone-500 uppercase">
                      {label}
                    </p>
                    <p className="mt-1 text-sm font-medium text-stone-900">
                      {value}
                    </p>
                  </div>
                ))}
              </section>

              <section className="space-y-2">
                <p className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-stone-500 uppercase">
                  <Activity className="size-3.5" />
                  Steps
                </p>
                {steps.length ? (
                  <div className="flex flex-col gap-2">
                    {steps.map((step, index) => (
                      <StepCard
                        key={`${step.kind}-${step.turn}-${step.name ?? "model"}-${index}`}
                        step={step}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-stone-400">
                    No step timeline on this older trace.
                  </p>
                )}
              </section>

              <section className="space-y-2">
                <p className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-stone-500 uppercase">
                  <BookOpen className="size-3.5" />
                  Policy sources
                </p>
                {citations.length ? (
                  <div className="flex flex-col gap-2">
                    {citations.map((doc, index) => (
                      <PolicyDocCard
                        key={`${doc.document_id}-cite-${index}`}
                        doc={doc}
                      />
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-stone-400">No citations this run</p>
                )}
              </section>

              <section className="space-y-2">
                <p className="flex items-center gap-1.5 text-[11px] font-medium tracking-wide text-stone-500 uppercase">
                  <BookOpen className="size-3.5" />
                  Retrieved policies
                </p>
                <p className="text-[11px] leading-relaxed text-stone-400">
                  One row per chunk. The same document_id can appear more than
                  once with different sections.
                </p>
                {retrievedChunks.length ? (
                  <div className="flex flex-col gap-2">
                    {retrievedChunks.map((doc, index) => (
                      <div
                        key={doc.chunk_id ?? `${doc.document_id}-${doc.section ?? index}`}
                        className="rounded-xl border border-stone-200/80 bg-stone-50/90 p-3 text-xs"
                      >
                        <p className="font-medium text-stone-800">
                          {doc.document_id}
                          {doc.section ? ` — ${doc.section}` : ""}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-stone-400">None retrieved</p>
                )}
              </section>

              {trace.error ? (
                <section className="space-y-2">
                  <p className="text-[11px] font-medium tracking-wide text-stone-500 uppercase">
                    Error
                  </p>
                  <pre className="overflow-auto rounded-xl border border-amber-200/80 bg-amber-50/80 p-3 text-xs whitespace-pre-wrap text-amber-950">
                    {trace.error}
                  </pre>
                </section>
              ) : null}

              <section className="space-y-2 border-t border-stone-200/80 pt-3">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs text-stone-500"
                  onClick={() => setShowRaw((value) => !value)}
                >
                  {showRaw ? "Hide raw JSON" : "Show raw JSON"}
                </Button>
                {showRaw ? (
                  <pre className="overflow-auto rounded-xl border border-stone-200/80 bg-stone-50 p-3 text-[11px] text-stone-700">
                    {JSON.stringify(trace, null, 2)}
                  </pre>
                ) : null}
              </section>
            </>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
