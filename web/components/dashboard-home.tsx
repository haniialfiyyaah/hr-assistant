"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  MessageSquare,
  Users,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { PageFrame, SurfaceCard } from "@/components/page-frame";
import { apiRequest, API_PATHS } from "@/lib/api";

const SHORTCUTS = [
  {
    href: "/",
    title: "Chat",
    description: "Ask about policy, balance, or leave.",
    icon: MessageSquare,
  },
  {
    href: "/leave",
    title: "Leave",
    description: "View your leave requests.",
    icon: CalendarDays,
  },
  {
    href: "/people",
    title: "People",
    description: "Synthetic employee directory.",
    icon: Users,
  },
  {
    href: "/policies",
    title: "Policies",
    description: "Browse policy documents.",
    icon: BookOpen,
  },
  {
    href: "/monitoring",
    title: "Monitoring",
    description: "Ops summary and alerts.",
    icon: Activity,
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
            error instanceof Error
              ? error.message
              : "Failed to load leave requests",
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
    <PageFrame
      eyebrow="Overview"
      title="Dashboard"
      description={user.scenario}
    >
      <SurfaceCard className="p-5">
        <p className="text-xs font-medium tracking-wide text-stone-500 uppercase">
          Signed in
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <span className="rounded-full bg-teal-800 px-3 py-1 text-xs font-medium text-white">
            {user.displayName}
          </span>
          <span className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs text-stone-600">
            {user.employeeId}
          </span>
          <span className="rounded-full border border-stone-200 bg-stone-50 px-3 py-1 text-xs capitalize text-stone-600">
            {user.role.replace("_", " ")}
          </span>
        </div>
      </SurfaceCard>

      <SurfaceCard className="p-5">
        <p className="text-xs font-medium tracking-wide text-stone-500 uppercase">
          Leave snapshot
        </p>
        <p className="mt-1 text-sm text-stone-500">
          Profile balances come from synthetic employee data and do not change
          after confirm. Ask in chat for a live balance.
        </p>
        {hasBalances ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            {(
              [
                ["Annual", user.balances.annual],
                ["Sick", user.balances.sick],
                ["Parental", user.balances.parental],
              ] as const
            ).map(([label, value]) => (
              <div
                key={label}
                className="rounded-2xl border border-stone-200/80 bg-stone-50/80 p-4"
              >
                <p className="text-xs text-stone-500">{label}</p>
                <p className="mt-1 text-3xl font-semibold tracking-tight text-stone-900">
                  {value ?? "—"}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p className="mt-4 text-sm text-stone-500">
            This monitoring admin account has no leave balances.
          </p>
        )}
        <p className="mt-4 text-sm text-stone-500">
          Leave requests on file:{" "}
          <span className="font-medium text-stone-800">
            {requestError
              ? `unavailable (${requestError})`
              : requestCount === null
                ? "loading…"
                : requestCount}
          </span>
        </p>
      </SurfaceCard>

      <div>
        <h2 className="mb-3 text-sm font-medium tracking-wide text-stone-500 uppercase">
          Shortcuts
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {shortcuts.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} className="group block">
                <SurfaceCard className="h-full p-4 transition-[transform,background-color] duration-200 ease-out group-hover:bg-white group-active:scale-[0.99]">
                  <div className="flex items-start justify-between gap-3">
                    <span className="inline-flex size-9 items-center justify-center rounded-xl bg-teal-800/10 text-teal-900">
                      <Icon className="size-4" />
                    </span>
                    <ArrowUpRight className="size-4 text-stone-300 transition-colors group-hover:text-teal-800" />
                  </div>
                  <p className="mt-3 text-base font-medium text-stone-900">
                    {item.title}
                  </p>
                  <p className="mt-1 text-sm text-stone-500">{item.description}</p>
                </SurfaceCard>
              </Link>
            );
          })}
        </div>
      </div>
    </PageFrame>
  );
}
