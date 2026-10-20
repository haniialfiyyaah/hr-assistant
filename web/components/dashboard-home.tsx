"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { useAuth } from "@/components/auth-provider";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { apiRequest, API_PATHS } from "@/lib/api";

const SHORTCUTS = [
  {
    href: "/",
    title: "Chat",
    description: "Ask about policy, balance, or leave.",
  },
  {
    href: "/leave",
    title: "Leave",
    description: "View your leave requests.",
  },
  {
    href: "/people",
    title: "People",
    description: "Synthetic employee directory.",
  },
  {
    href: "/policies",
    title: "Policies",
    description: "Browse policy documents.",
  },
  {
    href: "/monitoring",
    title: "Monitoring",
    description: "Ops summary and alerts.",
  },
] as const;

export function DashboardHome() {
  const { user } = useAuth();
  const [requestCount, setRequestCount] = useState<number | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const rows = await apiRequest<unknown[]>(
          "GET",
          API_PATHS.myRequests,
          user.demoToken,
        );
        if (!cancelled) {
          setRequestCount(rows.length);
          setRequestError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setRequestCount(null);
          setRequestError(
            error instanceof Error ? error.message : "Failed to load leave requests",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user]);

  if (!user) {
    return null;
  }

  const hasBalances = Object.keys(user.balances).length > 0;
  const shortcuts =
    user.role === "monitoring_admin"
      ? SHORTCUTS
      : SHORTCUTS.filter((item) => item.href !== "/monitoring");

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">{user.scenario}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Signed in</CardTitle>
          <CardDescription>Demo identity for this session</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3 text-sm">
          <Badge variant="secondary">{user.displayName}</Badge>
          <Badge variant="outline">{user.employeeId}</Badge>
          <Badge variant="outline">{user.role.replace("_", " ")}</Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Leave snapshot</CardTitle>
          <CardDescription>
            Profile balances come from synthetic employee data and do not change
            after confirm. Ask in chat for a live balance.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {hasBalances ? (
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-border p-3">
                <p className="text-xs text-muted-foreground">Annual</p>
                <p className="text-2xl font-semibold">{user.balances.annual ?? "—"}</p>
              </div>
              <div className="rounded-lg border border-border p-3">
                <p className="text-xs text-muted-foreground">Sick</p>
                <p className="text-2xl font-semibold">{user.balances.sick ?? "—"}</p>
              </div>
              <div className="rounded-lg border border-border p-3">
                <p className="text-xs text-muted-foreground">Parental</p>
                <p className="text-2xl font-semibold">
                  {user.balances.parental ?? "—"}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              This monitoring admin account has no leave balances.
            </p>
          )}
          <p className="mt-4 text-sm text-muted-foreground">
            Leave requests on file:{" "}
            {requestError
              ? `unavailable (${requestError})`
              : requestCount === null
                ? "loading…"
                : requestCount}
          </p>
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-3 text-lg font-medium">Shortcuts</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {shortcuts.map((item) => (
            <Link key={item.href} href={item.href} className="block">
              <Card className="h-full transition-colors hover:bg-muted/40">
                <CardHeader>
                  <CardTitle className="text-base">{item.title}</CardTitle>
                  <CardDescription>{item.description}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
