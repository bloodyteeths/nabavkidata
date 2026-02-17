"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Calendar,
  ChevronRight,
  Loader2,
  Target,
  TrendingUp,
  History as HistoryIcon,
} from "lucide-react";
import { api, BriefingHistoryItem } from "@/lib/api";
import Link from "next/link";
import { formatDate as formatDateUtil, formatDateTime } from "@/lib/utils";

export function BriefingHistory() {
  const [history, setHistory] = useState<BriefingHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getBriefingHistory(1);
      setHistory(response.items || []);
    } catch (err: any) {
      setError(err.message || "Грешка при вчитување на историја");
      console.error("Failed to load briefing history:", err);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      // Use deterministic formatter from utils (timezone-safe)
      return formatDateUtil(dateStr, { month: 'short', day: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <HistoryIcon className="w-5 h-5" />
            Историја на Извештаи
          </CardTitle>
          {!loading && !error && (
            <Button variant="ghost" size="sm" onClick={loadHistory}>
              <Loader2 className="w-4 h-4 mr-2" />
              Освежи
            </Button>
          )}
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Преглед на претходни дневни извештаи
        </p>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="text-center py-8 text-muted-foreground">
            <p className="text-sm">{error}</p>
            <Button variant="outline" size="sm" onClick={loadHistory} className="mt-4">
              Обиди се повторно
            </Button>
          </div>
        ) : history.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <Calendar className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Нема достапна историја</p>
            <p className="text-sm mt-2">
              Извештаите ќе се појават овде откако ќе се генерираат.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {history.map((item) => (
              <HistoryItem key={item.date} item={item} formatDate={formatDate} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface HistoryItemProps {
  item: BriefingHistoryItem;
  formatDate: (date: string) => string;
}

function HistoryItem({ item, formatDate }: HistoryItemProps) {
  return (
    <Link
      href={`/briefings/${item.date}`}
      className="block border rounded-lg p-4 hover:bg-muted/50 transition-colors"
    >
      <div className="flex items-center justify-between">
        {/* Left Side - Date & Stats */}
        <div className="flex items-center gap-4">
          {/* Date */}
          <div className="flex items-center gap-2 min-w-[120px]">
            <Calendar className="w-4 h-4 text-muted-foreground" />
            <span className="font-medium">{formatDate(item.date)}</span>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-4 text-sm">
            {/* Total Matches */}
            <div className="flex items-center gap-1 text-muted-foreground">
              <Target className="w-4 h-4" />
              <span className="font-medium text-foreground">{item.total_matches}</span>
              <span>совпаѓања</span>
            </div>

            {/* High Priority Count */}
            {item.high_priority_count > 0 && (
              <Badge variant="secondary" className="text-xs">
                <TrendingUp className="w-3 h-3 mr-1" />
                {item.high_priority_count} висок приоритет
              </Badge>
            )}
          </div>
        </div>

        {/* Right Side - Arrow */}
        <ChevronRight className="w-5 h-5 text-muted-foreground" />
      </div>

      {/* Generation Time */}
      {item.generated_at && (
        <p className="text-xs text-muted-foreground mt-2">
          Генериран на {formatDateTime(item.generated_at, {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      )}
    </Link>
  );
}
