"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiRequest, API_PATHS, ApiError } from "@/lib/api";

interface MonitoringSummary {
  run_count: number;
  error_rate: number;
  p95_latency_ms: number;
  tool_calls: number;
}

export function MonitoringPanel() {
  const { user } = useAuth();
  const router = useRouter();
  const [summary, setSummary] = useState<MonitoringSummary | null>(null);
  const [alerts, setAlerts] = useState<unknown[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    if (!user) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const nextSummary = await apiRequest<MonitoringSummary>(
        "GET",
        API_PATHS.monitoringSummary,
        user.demoToken,
      );
      const nextAlerts = await apiRequest<unknown[]>(
        "GET",
        API_PATHS.monitoringAlerts,
        user.demoToken,
      );
      setSummary(nextSummary);
      setAlerts(nextAlerts);
    } catch (err) {
      setSummary(null);
      setAlerts(null);
      setError(
        err instanceof ApiError || err instanceof Error
          ? err.message
          : "Failed to load monitoring",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!user) {
      return;
    }
    if (user.role !== "monitoring_admin") {
      router.replace("/");
      return;
    }
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- load on admin session
  }, [user?.employeeId, user?.role]);

  if (!user) {
    return null;
  }

  if (user.role !== "monitoring_admin") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-muted-foreground">
        Redirecting…
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Monitoring</h1>
          <p className="text-sm text-muted-foreground">
            Aggregate metrics and alerts for the monitoring admin.
          </p>
        </div>
        <Button
          variant="outline"
          onClick={() => void load()}
          disabled={loading}
        >
          {loading ? "Loading…" : "Refresh"}
        </Button>
      </div>

      {loading && !summary && !error ? (
        <p className="text-sm text-muted-foreground">Loading monitoring…</p>
      ) : null}

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Could not load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {summary ? (
        <div className="grid gap-3 sm:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Runs</CardDescription>
              <CardTitle className="text-2xl">{summary.run_count}</CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Error rate</CardDescription>
              <CardTitle className="text-2xl">
                {(summary.error_rate * 100).toFixed(1)}%
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>p95 latency</CardDescription>
              <CardTitle className="text-2xl">
                {Math.round(summary.p95_latency_ms)} ms
              </CardTitle>
            </CardHeader>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardDescription>Tool calls</CardDescription>
              <CardTitle className="text-2xl">{summary.tool_calls}</CardTitle>
            </CardHeader>
          </Card>
        </div>
      ) : null}

      {alerts ? (
        <Card>
          <CardHeader>
            <CardTitle>Active alerts</CardTitle>
            <CardDescription>
              {alerts.length
                ? `${alerts.length} alert(s)`
                : "No alerts are currently triggered."}
            </CardDescription>
          </CardHeader>
          {alerts.length ? (
            <CardContent>
              <pre className="overflow-auto rounded-lg bg-muted/40 p-3 text-xs">
                {JSON.stringify(alerts, null, 2)}
              </pre>
            </CardContent>
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
