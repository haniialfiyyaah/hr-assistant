"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { PageFrame, SurfaceCard } from "@/components/page-frame";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
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
      <div className="flex min-h-[40vh] items-center justify-center text-sm text-stone-500">
        Redirecting…
      </div>
    );
  }

  return (
    <PageFrame
      eyebrow="Operations"
      title="Monitoring"
      description="Aggregate metrics and alerts for the monitoring admin."
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
      {loading && !summary && !error ? (
        <p className="text-sm text-stone-500">Loading monitoring…</p>
      ) : null}

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Could not load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      {summary ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(
            [
              ["Runs", String(summary.run_count)],
              ["Error rate", `${(summary.error_rate * 100).toFixed(1)}%`],
              ["p95 latency", `${Math.round(summary.p95_latency_ms)} ms`],
              ["Tool calls", String(summary.tool_calls)],
            ] as const
          ).map(([label, value]) => (
            <SurfaceCard key={label} className="p-4">
              <p className="text-xs tracking-wide text-stone-500 uppercase">
                {label}
              </p>
              <p className="mt-2 text-3xl font-semibold tracking-tight text-stone-900">
                {value}
              </p>
            </SurfaceCard>
          ))}
        </div>
      ) : null}

      {alerts ? (
        <SurfaceCard className="overflow-hidden">
          <div className="border-b border-stone-200/80 px-5 py-4">
            <p className="text-base font-medium text-stone-900">Active alerts</p>
            <p className="mt-1 text-sm text-stone-500">
              {alerts.length
                ? `${alerts.length} alert(s)`
                : "No alerts are currently triggered."}
            </p>
          </div>
          {alerts.length ? (
            <pre className="overflow-auto bg-stone-50/80 p-5 text-xs text-stone-700">
              {JSON.stringify(alerts, null, 2)}
            </pre>
          ) : null}
        </SurfaceCard>
      ) : null}
    </PageFrame>
  );
}
