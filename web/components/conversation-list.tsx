"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { MessageSquarePlus, Plus } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import {
  apiRequest,
  API_PATHS,
  CONVERSATIONS_CHANGED_EVENT,
  notifyNewChat,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ConversationSummaryItem {
  conversation_id: string;
  title: string;
  updated_at: string;
}

function formatUpdatedAt(iso: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return "";
  }
}

export function ConversationList({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const { user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const activeId = searchParams.get("c");
  const [items, setItems] = useState<ConversationSummaryItem[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!user) {
      return;
    }
    try {
      const rows = await apiRequest<ConversationSummaryItem[]>(
        "GET",
        API_PATHS.conversations,
        user.demoToken,
      );
      setItems(rows);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not load chat history.",
      );
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void refresh();
  }, [refresh, pathname]);

  useEffect(() => {
    function onChanged() {
      void refresh();
    }
    window.addEventListener(CONVERSATIONS_CHANGED_EVENT, onChanged);
    return () => {
      window.removeEventListener(CONVERSATIONS_CHANGED_EVENT, onChanged);
    };
  }, [refresh]);

  function startNewChat() {
    if (!user) {
      return;
    }
    onNavigate?.();
    notifyNewChat();
    if (pathname !== "/" || activeId) {
      router.push("/");
    }
  }

  if (!user) {
    return null;
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 px-1 pb-2">
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          title="New chat"
          onClick={startNewChat}
          className="text-stone-600 hover:bg-stone-100 hover:text-stone-900"
        >
          <Plus />
        </Button>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 border-t border-stone-200/80 px-2 pt-3 pb-2">
      <div className="flex items-center justify-between gap-2 px-1">
        <p className="text-[11px] font-medium tracking-wide text-stone-500 uppercase">
          Chats
        </p>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={startNewChat}
          className="h-7 rounded-full px-2 text-xs text-stone-600 hover:bg-stone-100 hover:text-stone-900"
        >
          <MessageSquarePlus data-icon="inline-start" />
          New
        </Button>
      </div>
      <div className="min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain pr-0.5">
        {loading ? (
          <p className="px-2 py-2 text-xs text-stone-400">Loading…</p>
        ) : null}
        {!loading && items.length === 0 ? (
          <p className="px-2 py-2 text-xs text-stone-400">No chats yet.</p>
        ) : null}
        {items.map((item) => {
          const href = `/?c=${item.conversation_id}`;
          const active = activeId === item.conversation_id;
          return (
            <Link
              key={item.conversation_id}
              href={href}
              onClick={onNavigate}
              className={cn(
                "block rounded-xl px-2.5 py-2 transition-[background-color,color,transform] duration-200 ease-out active:scale-[0.99]",
                active
                  ? "bg-teal-50 text-teal-950"
                  : "text-stone-600 hover:bg-stone-100 hover:text-stone-900",
              )}
            >
              <p className="line-clamp-2 text-sm leading-snug font-medium">
                {item.title}
              </p>
              <p className="mt-0.5 text-[11px] text-stone-400">
                {formatUpdatedAt(item.updated_at)}
              </p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
