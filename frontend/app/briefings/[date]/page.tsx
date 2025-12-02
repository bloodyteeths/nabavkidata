"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card } from "@/components/ui/card";
import { BriefingSummary } from "@/components/briefings/BriefingSummary";
import { PriorityTenders } from "@/components/briefings/PriorityTenders";
import { AllMatches } from "@/components/briefings/AllMatches";
import { ArrowLeft, Calendar, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, DailyBriefing } from "@/lib/api";
import Link from "next/link";

export default function BriefingByDatePage() {
  const params = useParams();
  const router = useRouter();
  const date = params.date as string;

  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (date) {
      loadBriefing();
    }
  }, [date]);

  const loadBriefing = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getBriefingByDate(date);
      setBriefing(data);
    } catch (err: any) {
      setError(err.message || "Грешка при вчитување на извештајот");
      console.error("Failed to load briefing:", err);
    } finally {
      setLoading(false);
    }
  };

  // Format date in Macedonian
  const formatDate = (dateStr: string) => {
    try {
      const dateObj = new Date(dateStr);
      return dateObj.toLocaleDateString("mk-MK", {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto py-6">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
            <p className="text-muted-foreground">Вчитување на извештај...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-6">
        <div className="mb-6">
          <Link href="/briefings">
            <Button variant="ghost" className="gap-2">
              <ArrowLeft className="w-4 h-4" />
              Назад кон извештаи
            </Button>
          </Link>
        </div>
        <Card className="border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-8">
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 text-red-600 dark:text-red-400 mb-4">
              <svg
                className="w-8 h-8"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <p className="font-medium text-lg mb-2">{error}</p>
            <p className="text-sm text-muted-foreground mb-4">
              Извештајот за {formatDate(date)} не е достапен.
            </p>
            <Button onClick={loadBriefing} variant="outline">
              Обиди се повторно
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6">
      {/* Header */}
      <div className="mb-6">
        <Link href="/briefings">
          <Button variant="ghost" className="gap-2 mb-4">
            <ArrowLeft className="w-4 h-4" />
            Назад кон извештаи
          </Button>
        </Link>

        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Calendar className="w-8 h-8 text-blue-600" />
              Извештај за {formatDate(date)}
            </h1>
            {briefing?.generated_at && (
              <p className="text-sm text-muted-foreground mt-1">
                Генериран на {new Date(briefing.generated_at).toLocaleString('mk-MK', {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* AI Summary Card */}
      <BriefingSummary briefing={briefing} />

      {/* High Priority Tenders */}
      <PriorityTenders matches={briefing?.high_priority} />

      {/* All Matches */}
      <AllMatches matches={briefing?.all_matches} />
    </div>
  );
}
