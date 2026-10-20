"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { PageFrame, SurfaceCard } from "@/components/page-frame";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { apiRequest, API_PATHS, ApiError } from "@/lib/api";

interface LeaveRow {
  request_id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  business_days: number;
  status: string;
  created_at: string;
}

function statusTone(status: string): string {
  if (status.includes("pending")) {
    return "bg-amber-50 text-amber-900 border-amber-200";
  }
  if (status.includes("approved")) {
    return "bg-teal-50 text-teal-900 border-teal-200";
  }
  return "bg-stone-100 text-stone-700 border-stone-200";
}

export function LeaveList() {
  const { user } = useAuth();
  const [rows, setRows] = useState<LeaveRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    if (!user) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await apiRequest<LeaveRow[]>(
        "GET",
        API_PATHS.myRequests,
        user.demoToken,
      );
      setRows(data);
    } catch (err) {
      setRows(null);
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Failed to load leave requests",
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
      eyebrow="Requests"
      title="My leave"
      description="Requests for the signed-in employee only. View only."
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
            No leave requests yet for this persona.
          </p>
        </SurfaceCard>
      ) : null}

      {rows && rows.length > 0 ? (
        <SurfaceCard className="overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="px-4">Request</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Dates</TableHead>
                <TableHead>Days</TableHead>
                <TableHead className="px-4">Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.request_id}>
                  <TableCell className="px-4 font-mono text-xs text-stone-600">
                    {row.request_id}
                  </TableCell>
                  <TableCell className="capitalize">{row.leave_type}</TableCell>
                  <TableCell>
                    {row.start_date} → {row.end_date}
                  </TableCell>
                  <TableCell>{row.business_days}</TableCell>
                  <TableCell className="px-4">
                    <span
                      className={`inline-flex rounded-full border px-2.5 py-0.5 text-[11px] font-medium ${statusTone(row.status)}`}
                    >
                      {row.status}
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </SurfaceCard>
      ) : null}
    </PageFrame>
  );
}
