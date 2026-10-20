import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";

export default function SignedInLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Suspense
      fallback={
        <div className="chat-surface flex min-h-screen items-center justify-center text-sm text-stone-500">
          Loading…
        </div>
      }
    >
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
