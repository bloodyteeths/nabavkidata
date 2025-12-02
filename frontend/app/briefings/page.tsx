"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { BriefingSummary } from "@/components/briefings/BriefingSummary";
import { PriorityTenders } from "@/components/briefings/PriorityTenders";
import { AllMatches } from "@/components/briefings/AllMatches";
import { BriefingHistory } from "@/components/briefings/BriefingHistory";
import { Newspaper, RefreshCw, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, DailyBriefing } from "@/lib/api";

export default function BriefingsPage() {
  const [briefing, setBriefing] = useState<DailyBriefing | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTodayBriefing();
  }, []);

  const loadTodayBriefing = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getTodayBriefing();
      setBriefing(data);
    } catch (err: any) {
      setError(err.message || "Грешка при вчитување на извештајот");
      console.error("Failed to load today's briefing:", err);
    } finally {
      setLoading(false);
    }
  };

  const regenerate = async () => {
    try {
      setRegenerating(true);
      setError(null);
      const data = await api.regenerateBriefing();
      setBriefing(data);
    } catch (err: any) {
      setError(err.message || "Грешка при регенерирање на извештајот");
      console.error("Failed to regenerate briefing:", err);
    } finally {
      setRegenerating(false);
    }
  };

  // Format date in Macedonian
  const formatDate = (date: Date) => {
    return date.toLocaleDateString("mk-MK", {
      weekday: "long",
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  };

  if (loading) {
    return (
      <div className="container mx-auto py-6">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
            <p className="text-muted-foreground">Вчитување на дневен извештај...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Newspaper className="w-8 h-8 text-blue-600" />
            Дневен Извештај
          </h1>
          <p className="text-muted-foreground mt-1">{formatDate(new Date())}</p>
        </div>
        <Button
          variant="outline"
          onClick={regenerate}
          disabled={regenerating}
          className="gap-2"
        >
          {regenerating ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Регенерирање...
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4" />
              Освежи
            </>
          )}
        </Button>
      </div>

      {/* Error Message */}
      {error && (
        <Card className="mb-6 border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/20 p-4">
          <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
            <svg
              className="w-5 h-5"
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
            <p className="font-medium">{error}</p>
          </div>
        </Card>
      )}

      {/* AI Summary Card */}
      <BriefingSummary briefing={briefing} />

      {/* High Priority Tenders */}
      <PriorityTenders matches={briefing?.high_priority} />

      {/* All Matches */}
      <AllMatches matches={briefing?.all_matches} />

      {/* History */}
      <BriefingHistory />
    </div>
  );
}
