"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Sparkles, TrendingUp, Target, Users } from "lucide-react";
import { DailyBriefing } from "@/lib/api";
import { formatDateTime } from "@/lib/utils";

interface BriefingSummaryProps {
  briefing: DailyBriefing | null;
}

export function BriefingSummary({ briefing }: BriefingSummaryProps) {
  if (!briefing) {
    return (
      <Card className="mb-6 bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-blue-950/20 dark:via-indigo-950/20 dark:to-purple-950/20 border-blue-200 dark:border-blue-800">
        <CardContent className="py-12">
          <div className="text-center text-muted-foreground">
            <Sparkles className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Нема достапен дневен извештај. Притиснете Refresh за да генерирате.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const stats = briefing.stats || {
    total_new: briefing.total_new_tenders || 0,
    matches: briefing.total_matches || 0,
    high_priority: briefing.high_priority_count || 0,
    competitors_active: 0,
  };

  return (
    <Card className="mb-6 bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-blue-950/20 dark:via-indigo-950/20 dark:to-purple-950/20 border-blue-200 dark:border-blue-800 overflow-hidden relative">
      {/* Decorative gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-transparent via-white/30 to-transparent pointer-events-none" />

      <CardHeader className="relative">
        <div className="flex items-center gap-2 mb-2">
          <Badge variant="secondary" className="bg-white/80 dark:bg-gray-800/80">
            <Sparkles className="w-3 h-3 mr-1 text-yellow-500" />
            AI Преглед
          </Badge>
        </div>
        <CardTitle className="text-2xl">Дневен Преглед на Тендери</CardTitle>
      </CardHeader>

      <CardContent className="space-y-6 relative">
        {/* AI Summary */}
        {briefing.ai_summary && (
          <div className="bg-white/60 dark:bg-gray-800/60 backdrop-blur-sm rounded-lg p-4 border border-blue-100 dark:border-blue-900">
            <p className="text-sm leading-relaxed text-foreground dark:text-muted-foreground">
              {briefing.ai_summary}
            </p>
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {/* Total New Tenders */}
          <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-lg p-4 border border-blue-100 dark:border-blue-900">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
              <TrendingUp className="h-4 w-4" />
              <span>Нови Тендери</span>
            </div>
            <p className="text-3xl font-bold text-blue-600 dark:text-blue-400">
              {stats.total_new}
            </p>
          </div>

          {/* Your Matches */}
          <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-lg p-4 border border-green-100 dark:border-green-900">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
              <Target className="h-4 w-4" />
              <span>Ваши Совпаѓања</span>
            </div>
            <p className="text-3xl font-bold text-green-600 dark:text-green-400">
              {stats.matches}
            </p>
          </div>

          {/* High Priority */}
          <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-lg p-4 border border-orange-100 dark:border-orange-900">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
              <Sparkles className="h-4 w-4" />
              <span>Висок Приоритет</span>
            </div>
            <p className="text-3xl font-bold text-orange-600 dark:text-orange-400">
              {stats.high_priority}
            </p>
          </div>

          {/* Competitors Active */}
          <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur-sm rounded-lg p-4 border border-purple-100 dark:border-purple-900">
            <div className="flex items-center gap-2 text-muted-foreground text-xs mb-2">
              <Users className="h-4 w-4" />
              <span>Активни Конкуренти</span>
            </div>
            <p className="text-3xl font-bold text-purple-600 dark:text-purple-400">
              {stats.competitors_active || 0}
            </p>
          </div>
        </div>

        {/* Generation timestamp */}
        {briefing.generated_at && (
          <p className="text-xs text-muted-foreground text-center">
            Генериран на {formatDateTime(briefing.generated_at, {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
