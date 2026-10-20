"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
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
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">My leave</h1>
          <p className="text-sm text-muted-foreground">
            Requests for the signed-in employee only. View only.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          {loading ? "Loading…" : "Refresh"}
        </Button>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Could not load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {rows && rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No leave requests yet for this persona.
        </p>
      ) : null}

      {rows && rows.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Request</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Dates</TableHead>
              <TableHead>Days</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.request_id}>
                <TableCell className="font-mono text-xs">
                  {row.request_id}
                </TableCell>
                <TableCell>{row.leave_type}</TableCell>
                <TableCell>
                  {row.start_date} → {row.end_date}
                </TableCell>
                <TableCell>{row.business_days}</TableCell>
                <TableCell>{row.status}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </div>
  );
}
