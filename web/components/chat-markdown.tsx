"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

/**
 * Renders chat message markdown (bold, italic, lists, links, code).
 * HTML is not executed — react-markdown escapes raw HTML by default.
 */
export function ChatMarkdown({
  content,
  tone = "assistant",
}: {
  content: string;
  tone?: "assistant" | "user";
}) {
  const isUser = tone === "user";

  return (
    <div
      className={cn(
        "chat-markdown text-[15px] leading-relaxed break-words",
        isUser ? "text-stone-50" : "text-stone-800",
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => (
            <ul className="mb-2 list-disc space-y-1 pl-5 last:mb-0">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 list-decimal space-y-1 pl-5 last:mb-0">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className={cn(
                "underline underline-offset-2",
                isUser
                  ? "text-teal-100 hover:text-white"
                  : "text-teal-800 hover:text-teal-700",
              )}
            >
              {children}
            </a>
          ),
          code: ({ className, children, ...props }) => {
            const isBlock = Boolean(className?.includes("language-"));
            if (isBlock) {
              return (
                <code className={cn("font-mono text-[13px]", className)} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className={cn(
                  "rounded-md px-1.5 py-0.5 font-mono text-[13px]",
                  isUser
                    ? "bg-white/15 text-stone-50"
                    : "bg-stone-100 text-stone-800",
                )}
                {...props}
              >
                {children}
              </code>
            );
          },
          pre: ({ children }) => (
            <pre
              className={cn(
                "mb-2 overflow-x-auto rounded-xl p-3 font-mono text-[13px] last:mb-0",
                isUser ? "bg-white/10 text-stone-50" : "bg-stone-100 text-stone-800",
              )}
            >
              {children}
            </pre>
          ),
          blockquote: ({ children }) => (
            <blockquote
              className={cn(
                "mb-2 border-l-2 pl-3 last:mb-0",
                isUser
                  ? "border-white/30 text-stone-200"
                  : "border-stone-300 text-stone-600",
              )}
            >
              {children}
            </blockquote>
          ),
          h1: ({ children }) => (
            <h1 className="mb-2 text-base font-semibold last:mb-0">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mb-2 text-base font-semibold last:mb-0">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="mb-2 text-sm font-semibold last:mb-0">{children}</h3>
          ),
          hr: () => (
            <hr
              className={cn(
                "my-3 border-0 border-t",
                isUser ? "border-white/20" : "border-stone-200",
              )}
            />
          ),
          table: ({ children }) => (
            <div className="mb-2 overflow-x-auto last:mb-0">
              <table className="w-full border-collapse text-left text-sm">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th
              className={cn(
                "border-b px-2 py-1 font-semibold",
                isUser ? "border-white/20" : "border-stone-200",
              )}
            >
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td
              className={cn(
                "border-b px-2 py-1",
                isUser ? "border-white/15" : "border-stone-100",
              )}
            >
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
