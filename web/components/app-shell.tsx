"use client";

import { Suspense, useEffect, useState } from "react";
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
  Menu,
  MessageSquare,
  Ticket,
  Users,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { BrandMark } from "@/components/brand-mark";
import { ConversationList } from "@/components/conversation-list";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
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
    label: "New Chat",
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
    href: "/tickets",
    label: "Tickets",
    icon: Ticket,
    roles: ["employee", "monitoring_admin"],
  },
  {
    href: "/people",
    label: "People",
    icon: Users,
    roles: ["monitoring_admin"],
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

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, ready, signOut } = useAuth();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const isChatHome = pathname === "/";

  useEffect(() => {
    setCollapsed(sessionStorage.getItem(SIDEBAR_KEY) === "1");
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      sessionStorage.setItem(SIDEBAR_KEY, next ? "1" : "0");
      return next;
    });
  }

  if (!ready || !user) {
    return (
      <div className="chat-surface flex min-h-svh items-center justify-center text-sm text-stone-500">
        Loading…
      </div>
    );
  }

  const navItems = NAV.filter((item) => item.roles.includes(user.role));

  function renderNav(options: { collapsed?: boolean; onNavigate?: () => void }) {
    return navItems.map((item) => {
      const active = isActivePath(pathname, item.href);
      const Icon = item.icon;
      return (
        <Link
          key={item.href}
          href={item.href}
          title={item.label}
          onClick={options.onNavigate}
          className={cn(
            "flex items-center gap-2 rounded-xl px-2.5 py-2.5 text-sm transition-[background-color,color,transform] duration-200 ease-out active:scale-[0.98] md:py-2",
            options.collapsed && "justify-center px-0",
            active
              ? "bg-teal-800 text-white shadow-sm"
              : "text-stone-600 hover:bg-stone-100 hover:text-stone-900",
          )}
        >
          <Icon className="size-4 shrink-0" />
          {!options.collapsed ? <span>{item.label}</span> : null}
        </Link>
      );
    });
  }

  return (
    <div className="flex h-svh min-h-0 chat-surface text-stone-900">
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden h-svh min-h-0 shrink-0 flex-col border-r border-stone-200/80 bg-white/70 text-stone-800 backdrop-blur-md transition-[width] duration-200 ease-out md:flex",
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
                <BrandMark size="sm" />
                <p className="text-xs font-medium tracking-[0.14em] text-teal-800/80 uppercase">
                  HR Assistant
                </p>
              </div>
              <p className="text-sm leading-snug font-semibold text-stone-900">
                Policy and Leave
              </p>
            </div>
          ) : (
            <BrandMark size="md" />
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

        <nav className="flex flex-col gap-1 p-2">
          {renderNav({ collapsed })}
        </nav>

        <Suspense fallback={null}>
          <ConversationList collapsed={collapsed} />
        </Suspense>

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

      {/* Mobile nav drawer */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent
          side="left"
          className="flex h-full w-[min(100%,20rem)] flex-col gap-0 bg-white/95 p-0 backdrop-blur-md"
          showCloseButton
        >
          <SheetHeader className="border-b border-stone-200/80 pr-12">
            <div className="flex items-center gap-2">
              <BrandMark size="md" />
              <div className="min-w-0 text-left">
                <SheetTitle className="text-sm font-semibold text-stone-900">
                  HR Assistant
                </SheetTitle>
                <SheetDescription className="text-xs text-stone-500">
                  Policy and Leave
                </SheetDescription>
              </div>
            </div>
          </SheetHeader>
          <nav className="flex flex-col gap-1 p-3">
            {renderNav({ onNavigate: () => setMobileOpen(false) })}
          </nav>
          <Suspense fallback={null}>
            <ConversationList onNavigate={() => setMobileOpen(false)} />
          </Suspense>
          <div className="mt-auto border-t border-stone-200/80 p-3">
            <div className="mb-2 rounded-xl bg-stone-50 px-3 py-2">
              <p className="truncate text-sm font-medium text-stone-800">
                {user.displayName}
              </p>
              <p className="truncate text-[11px] text-stone-500">
                {user.employeeId} · {user.role.replace("_", " ")}
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={signOut}
              className="w-full justify-start text-stone-600 hover:bg-stone-100 hover:text-stone-900"
            >
              <LogOut data-icon="inline-start" />
              Sign out
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="flex items-center gap-3 border-b border-stone-200/70 bg-white/70 px-3 py-2.5 backdrop-blur-sm md:hidden">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
            className="shrink-0 text-stone-600 hover:bg-stone-100 hover:text-stone-900"
          >
            <Menu />
          </Button>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-stone-900">
              {isChatHome ? "Assistant" : "HR Assistant"}
            </p>
            <p className="truncate text-[11px] text-stone-500">
              {user.displayName.split(" ")[0]} · {user.role.replace("_", " ")}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={signOut}
            className="shrink-0 rounded-full border-stone-200 bg-white"
          >
            Sign out
          </Button>
        </header>

        {/* Desktop page header (non-chat) */}
        {!isChatHome ? (
          <header className="hidden items-center justify-between gap-4 border-b border-stone-200/70 bg-white/55 px-4 py-3 backdrop-blur-sm sm:px-6 md:flex">
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
            isChatHome
              ? "flex flex-col overflow-hidden p-0"
              : "overflow-auto p-4 sm:p-6",
          )}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
