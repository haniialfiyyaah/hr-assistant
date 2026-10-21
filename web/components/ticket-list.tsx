"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { PageFrame, SurfaceCard } from "@/components/page-frame";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Modal,
  ModalBody,
  ModalContent,
  ModalDescription,
  ModalHeader,
  ModalTitle,
} from "@/components/ui/modal";
import { apiRequest, API_PATHS, ApiError } from "@/lib/api";

const SUMMARY_PREVIEW_CHARS = 110;

interface TicketRow {
  ticket_id: string;
  category: string;
  summary: string;
  status: string;
  created_at: string;
}

function statusTone(status: string): string {
  if (status === "open") {
    return "bg-amber-50 text-amber-900 border-amber-200";
  }
  return "bg-stone-100 text-stone-700 border-stone-200";
}

function formatCategory(category: string): string {
  return category.replaceAll("_", " ");
}

function formatCreatedAt(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function truncateSummary(summary: string): {
  preview: string;
  truncated: boolean;
} {
  const normalized = summary.trim();
  if (normalized.length <= SUMMARY_PREVIEW_CHARS) {
    return { preview: normalized, truncated: false };
  }
  return {
    preview: `${normalized.slice(0, SUMMARY_PREVIEW_CHARS).trimEnd()}…`,
    truncated: true,
  };
}

export function TicketList() {
  const { user } = useAuth();
  const [rows, setRows] = useState<TicketRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<TicketRow | null>(null);

  async function load() {
    if (!user) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest<TicketRow[]>(
        "GET",
        API_PATHS.myTickets,
        user.demoToken,
      );
      setRows(data);
    } catch (err) {
      setRows(null);
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Failed to load HR tickets",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load on persona change
  }, [user?.employeeId]);

  if (!user) {
    return null;
  }

  return (
    <PageFrame
      eyebrow="Support"
      title="My tickets"
      description="HR tickets for the signed-in employee only. Opened after you confirm a ticket proposal in chat."
      actions={
        <Button
          variant="outline"
          onClick={() => void load()}
          disabled={loading}
          className="rounded-full border-stone-200 bg-white"
        >
          <RefreshCw
            data-icon="inline-start"
            className={loading ? "animate-spin" : undefined}
          />
          {loading ? "Loading…" : "Refresh"}
        </Button>
      }
    >
      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Could not load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {rows && rows.length === 0 ? (
        <SurfaceCard className="px-5 py-10 text-center">
          <p className="text-sm text-stone-500">
            No HR tickets yet for this persona.
          </p>
        </SurfaceCard>
      ) : null}

      {rows && rows.length > 0 ? (
        <div className="flex flex-col gap-3">
          {rows.map(row => {
            const { preview, truncated } = truncateSummary(row.summary);
            return (
              <SurfaceCard key={row.ticket_id} className="overflow-hidden p-0">
                <div className="flex flex-col gap-3 px-4 py-4 sm:px-5">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-mono text-xs text-stone-500">
                        {row.ticket_id}
                      </p>
                      <p className="mt-1 text-sm font-medium capitalize text-stone-900">
                        {formatCategory(row.category)}
                      </p>
                    </div>
                    <span
                      className={`inline-flex shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${statusTone(row.status)}`}
                    >
                      {row.status}
                    </span>
                  </div>

                  <div>
                    <p className="text-sm leading-relaxed text-stone-700">
                      {preview}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                      <button
                        type="button"
                        onClick={() => setSelected(row)}
                        className="text-[12px] font-medium text-teal-800 outline-none hover:underline focus-visible:underline"
                      >
                        {truncated ? "Show more" : "View detail"}
                      </button>
                      <span className="text-[11px] text-stone-400">
                        {formatCreatedAt(row.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              </SurfaceCard>
            );
          })}
        </div>
      ) : null}

      <Modal
        open={selected !== null}
        onOpenChange={open => {
          if (!open) {
            setSelected(null);
          }
        }}
      >
        <ModalContent>
          {selected ? (
            <>
              <ModalHeader>
                <ModalTitle className="font-mono text-sm">
                  {selected.ticket_id}
                </ModalTitle>
                <ModalDescription className="capitalize">
                  {formatCategory(selected.category)} · {selected.status}
                </ModalDescription>
              </ModalHeader>
              <ModalBody className="flex flex-col gap-4">
                <div>
                  <p className="text-[11px] tracking-wide text-stone-500 uppercase">
                    Created
                  </p>
                  <p className="mt-1 text-sm text-stone-800">
                    {formatCreatedAt(selected.created_at)}
                  </p>
                </div>
                <div>
                  <p className="text-[11px] tracking-wide text-stone-500 uppercase">
                    Summary
                  </p>
                  <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-stone-800">
                    {selected.summary}
                  </p>
                </div>
              </ModalBody>
            </>
          ) : null}
        </ModalContent>
      </Modal>
    </PageFrame>
  );
}
