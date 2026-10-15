"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { HelpCircle } from "lucide-react";
import { ConciergeChat } from "@/components/concierge/ConciergeChat";

export default function ChatPageWrapper() {
  return (
    <Suspense
      fallback={
        <div className="flex flex-col h-screen bg-background items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
        </div>
      }
    >
      <ChatPage />
    </Suspense>
  );
}

function ChatPage() {
  const searchParams = useSearchParams();
  const tenderId = searchParams.get("tender") ?? undefined;

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-background">
      <div className="border-b bg-card">
        <div className="container mx-auto px-3 md:px-4 py-3 md:py-4 max-w-4xl">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
              <HelpCircle className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-lg md:text-xl font-bold">Прашања за тендери</h1>
              <p className="text-xs md:text-sm text-muted-foreground">
                Кратки одговори од нашата база. За понуда, пишете ни.
              </p>
            </div>
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0">
        <div className="container mx-auto px-3 md:px-4 py-4 max-w-4xl h-full">
          <ConciergeChat variant="page" tenderId={tenderId} />
        </div>
      </div>
    </div>
  );
}
