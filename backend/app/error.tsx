"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { AlertTriangle, RefreshCcw, Home } from "lucide-react";
import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to console for debugging
    console.error("Page error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="max-w-md w-full">
        <CardContent className="p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mx-auto mb-6">
            <AlertTriangle className="h-8 w-8 text-destructive" />
          </div>

          <h1 className="text-2xl font-bold mb-2">Нешто тргна наопаку</h1>
          <p className="text-muted-foreground mb-6">
            Се извинуваме, се случи неочекувана грешка. Обидете се да ја освежите страницата.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button onClick={reset} className="gap-2">
              <RefreshCcw className="h-4 w-4" />
              Обиди се повторно
            </Button>
            <Button variant="outline" asChild>
              <Link href="/dashboard" className="gap-2">
                <Home className="h-4 w-4" />
                Почетна
              </Link>
            </Button>
          </div>

          {process.env.NODE_ENV === "development" && error.message && (
            <div className="mt-6 p-4 bg-muted rounded-lg text-left">
              <p className="text-xs font-mono text-muted-foreground break-all">
                {error.message}
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
