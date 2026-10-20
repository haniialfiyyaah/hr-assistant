import { Suspense } from "react";

import { ChatThread } from "@/components/chat-thread";

export default function HomePage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full items-center justify-center text-sm text-stone-500">
          Loading chat…
        </div>
      }
    >
      <ChatThread />
    </Suspense>
  );
}
