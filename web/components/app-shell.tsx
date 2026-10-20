"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BookOpen,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Sparkles,
  Users,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const SIDEBAR_KEY = "hr-assistant.sidebar-collapsed";

type NavRole = "employee" | "monitoring_admin";

const NAV: {
  href: string;
  label: string;
  icon: typeof MessageSquare;
  roles: NavRole[];
}[] = [
  {
    href: "/",
    label: "Chat",
    icon: MessageSquare,
    roles: ["employee", "monitoring_admin"],
  },
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    roles: ["employee", "monitoring_admin"],
  },
  {
    href: "/leave",
    label: "Leave",
    icon: CalendarDays,
    roles: ["employee", "monitoring_admin"],
  },
  {
    href: "/people",
    label: "People",
    icon: Users,
    roles: ["employee", "monitoring_admin"],
  },
  {
    href: "/policies",
    label: "Policies",
    icon: BookOpen,
    roles: ["employee", "monitoring_admin"],
  },
  {
    href: "/monitoring",
    label: "Monitoring",
    icon: Activity,
    roles: ["monitoring_admin"],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, ready, signOut } = useAuth();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const isChatHome = pathname === "/";

  useEffect(() => {
    setCollapsed(sessionStorage.getItem(SIDEBAR_KEY) === "1");
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      sessionStorage.setItem(SIDEBAR_KEY, next ? "1" : "0");
      return next;
    });
  }

  if (!ready || !user) {
    return (
      <div className="chat-surface flex min-h-screen items-center justify-center text-sm text-stone-500">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex h-svh min-h-0 chat-surface text-stone-900">
      <aside
        className={cn(
          "flex shrink-0 flex-col border-r border-stone-200/80 bg-white/70 text-stone-800 backdrop-blur-md transition-[width] duration-200 ease-out",
          collapsed ? "w-16" : "w-60",
        )}
      >
        <div
          className={cn(
            "flex gap-2 px-3 py-4",
            collapsed ? "flex-col items-center" : "items-start justify-between",
          )}
        >
          {!collapsed ? (
            <div className="min-w-0 flex-1 px-1">
              <div className="mb-2 flex items-center gap-2">
                <span className="inline-flex size-7 items-center justify-center rounded-full bg-teal-800 text-white">
                  <Sparkles className="size-3.5" />
                </span>
                <p className="text-xs font-medium tracking-[0.14em] text-teal-800/80 uppercase">
                  HR Assistant
                </p>
              </div>
              <p className="text-sm leading-snug font-semibold text-stone-900">
                Policy and Leave
              </p>
            </div>
          ) : (
            <span className="inline-flex size-8 items-center justify-center rounded-full bg-teal-800 text-white">
              <Sparkles className="size-3.5" />
            </span>
          )}
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="text-stone-500 hover:bg-stone-100 hover:text-stone-800"
          >
            {collapsed ? <ChevronRight /> : <ChevronLeft />}
          </Button>
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-2">
          {NAV.filter((item) => item.roles.includes(user.role)).map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname === item.href || pathname.startsWith(`${item.href}/`);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                title={item.label}
                className={cn(
                  "flex items-center gap-2 rounded-xl px-2.5 py-2 text-sm transition-[background-color,color,transform] duration-200 ease-out active:scale-[0.98]",
                  collapsed && "justify-center px-0",
                  active
                    ? "bg-teal-800 text-white shadow-sm"
                    : "text-stone-600 hover:bg-stone-100 hover:text-stone-900",
                )}
              >
                <Icon className="size-4 shrink-0" />
                {!collapsed ? <span>{item.label}</span> : null}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-stone-200/80 p-2">
          {!collapsed ? (
            <div className="mb-2 rounded-xl bg-stone-50 px-3 py-2">
              <p className="truncate text-sm font-medium text-stone-800">
                {user.displayName}
              </p>
              <p className="truncate text-[11px] text-stone-500">
                {user.employeeId} · {user.role.replace("_", " ")}
              </p>
            </div>
          ) : null}
          <Button
            variant="ghost"
            size={collapsed ? "icon-sm" : "sm"}
            onClick={signOut}
            className={cn(
              "w-full justify-start text-stone-600 hover:bg-stone-100 hover:text-stone-900",
              collapsed && "justify-center",
            )}
            title="Sign out"
          >
            <LogOut data-icon="inline-start" />
            {!collapsed ? "Sign out" : null}
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {!isChatHome ? (
          <header className="flex items-center justify-between gap-4 border-b border-stone-200/70 bg-white/55 px-6 py-3 backdrop-blur-sm">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-stone-900">
                {user.displayName}
              </p>
              <p className="truncate text-xs text-stone-500">
                {user.employeeId} · {user.role.replace("_", " ")}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={signOut}
              className="rounded-full border-stone-200 bg-white"
            >
              Sign out
            </Button>
          </header>
        ) : null}
        <main
          className={cn(
            "min-h-0 flex-1",
            isChatHome ? "flex flex-col overflow-hidden p-0" : "overflow-auto p-6",
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
