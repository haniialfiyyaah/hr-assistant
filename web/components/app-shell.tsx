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
  MessageSquare,
  Users,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
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
      <div className="flex min-h-screen items-center justify-center text-sm text-muted-foreground">
        Loading…
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <aside
        className={cn(
          "flex shrink-0 flex-col border-r border-border bg-sidebar text-sidebar-foreground transition-[width] duration-200",
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
            <div className="min-w-0 flex-1 flex-col gap-1 px-1">
              <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                HR Assistant
              </p>
              <p className="text-sm leading-snug font-semibold">
                Policy and Leave Assistant
              </p>
            </div>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight /> : <ChevronLeft />}
          </Button>
        </div>
        <Separator />
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
                  "flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm transition-colors",
                  collapsed && "justify-center px-0",
                  active
                    ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
                )}
              >
                <Icon className="size-4 shrink-0" />
                {!collapsed ? <span>{item.label}</span> : null}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between gap-4 border-b border-border px-6 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">{user.displayName}</p>
            <p className="truncate text-xs text-muted-foreground">
              {user.employeeId} · {user.role.replace("_", " ")}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={signOut}>
            Sign out
          </Button>
        </header>
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
