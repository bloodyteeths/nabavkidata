"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { AlertTriangle, RefreshCcw, Home } from "lucide-react";
import Link from "next/link";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard error:", error);
  }, [error]);

  return (
    <div className="flex items-center justify-center h-full p-8">
      <Card className="max-w-md w-full">
        <CardContent className="p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mx-auto mb-6">
            <AlertTriangle className="h-8 w-8 text-destructive" />
          </div>

          <h1 className="text-xl font-bold mb-2">Грешка при вчитување</h1>
          <p className="text-muted-foreground mb-6 text-sm">
            Не можевме да ја вчитаме оваа страница. Проверете ја вашата интернет конекција и обидете се повторно.
          </p>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Button onClick={reset} size="sm" className="gap-2">
              <RefreshCcw className="h-4 w-4" />
              Обиди се повторно
            </Button>
            <Button variant="outline" size="sm" asChild>
              <Link href="/dashboard" className="gap-2">
                <Home className="h-4 w-4" />
                Табла
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
