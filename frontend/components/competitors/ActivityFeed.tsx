"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Trophy, FileText, XCircle, RefreshCcw, ArrowRight } from "lucide-react";
import Link from "next/link";

interface Activity {
  type: "won" | "bid" | "lost";
  company_name: string;
  tender_id: string;
  tender_title: string;
  amount?: number;
  timestamp?: string;
  details?: {
    estimated_value?: number;
    discount_percent?: number;
    num_bidders?: number;
    rank?: number;
  };
}

interface ActivityFeedProps {
  companyNames: string[];
  limit?: number;
}

export default function ActivityFeed({ companyNames, limit = 50 }: ActivityFeedProps) {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [mounted, setMounted] = useState(false);
  const itemsPerPage = 20;

  useEffect(() => {
    setMounted(true);
    if (companyNames.length > 0) {
      loadActivities();
    } else {
      setActivities([]);
    }
  }, [companyNames]);

  async function loadActivities() {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getCompetitorActivity(companyNames, limit);
      setActivities(result.activities || []);
    } catch (err: any) {
      console.error("Failed to load competitor activity:", err);
      setError("Неуспешно вчитување на активност");
    } finally {
      setLoading(false);
    }
  }

  function getActivityIcon(type: string) {
    switch (type) {
      case "won":
        return <Trophy className="h-5 w-5 text-yellow-500" />;
      case "bid":
        return <FileText className="h-5 w-5 text-blue-500" />;
      case "lost":
        return <XCircle className="h-5 w-5 text-muted-foreground" />;
      default:
        return <FileText className="h-5 w-5 text-muted-foreground" />;
    }
  }

  function getActivityText(activity: Activity): string {
    switch (activity.type) {
      case "won":
        return "победи";
      case "bid":
        return "понуди на";
      case "lost":
        return "загуби";
      default:
        return "учествува во";
    }
  }

  function formatAmount(amount?: number): string {
    if (!amount) return "";
    return amount.toLocaleString("mk-MK");
  }

  function formatTimestamp(timestamp?: string): string {
    if (!timestamp) return "";
    try {
      const date = new Date(timestamp);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return "сега";
      if (diffMins < 60) return `пред ${diffMins} мин`;
      if (diffHours < 24) return `пред ${diffHours} час${diffHours > 1 ? 'а' : ''}`;
      if (diffDays < 7) return `пред ${diffDays} ден${diffDays > 1 ? 'а' : ''}`;
      return date.toLocaleDateString('mk-MK');
    } catch (e) {
      return "";
    }
  }

  // Pagination
  const displayedActivities = activities.slice(0, page * itemsPerPage);
  const hasMore = displayedActivities.length < activities.length;

  if (companyNames.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Активност на конкуренти
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p>Немате следени компании</p>
            <p className="text-sm mt-1">
              Додадете компании за следење за да ја видите нивната активност
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Активност на конкуренти
          </CardTitle>
          <Button
            variant="outline"
            size="sm"
            onClick={loadActivities}
            disabled={loading}
          >
            <RefreshCcw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
            Освежи
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {error && (
          <div className="text-sm text-destructive mb-4 p-3 bg-destructive/10 rounded-md">
            {error}
          </div>
        )}

        {loading && activities.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse border rounded-lg p-4">
                <div className="h-4 bg-muted rounded w-3/4 mb-2" />
                <div className="h-3 bg-muted rounded w-1/2" />
              </div>
            ))}
          </div>
        ) : activities.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-30" />
            <p>Нема активност за следените компании</p>
          </div>
        ) : (
          <>
            <div className="space-y-0 divide-y">
              {displayedActivities.map((activity, idx) => (
                <div
                  key={`${activity.tender_id}-${activity.company_name}-${idx}`}
                  className="flex items-start gap-4 py-4 first:pt-0 last:pb-0 hover:bg-accent/50 transition-colors rounded-lg px-3 -mx-3"
                >
                  {/* Icon */}
                  <div className="flex-shrink-0 mt-1">
                    <div className={`p-2 rounded-full ${
                      activity.type === "won"
                        ? "bg-yellow-100 dark:bg-yellow-900/30"
                        : activity.type === "bid"
                        ? "bg-blue-100 dark:bg-blue-900/30"
                        : "bg-gray-100 dark:bg-gray-800"
                    }`}>
                      {getActivityIcon(activity.type)}
                    </div>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="font-semibold">{activity.company_name}</span>
                      <span className="text-muted-foreground">
                        {getActivityText(activity)}
                      </span>
                      <Badge
                        variant={
                          activity.type === "won"
                            ? "default"
                            : activity.type === "bid"
                            ? "secondary"
                            : "outline"
                        }
                        className="text-xs"
                      >
                        {activity.type === "won"
                          ? "Победа"
                          : activity.type === "bid"
                          ? "Понуда"
                          : "Загуба"}
                      </Badge>
                    </div>

                    <Link
                      href={`/tenders/${activity.tender_id}`}
                      className="text-sm font-medium hover:underline line-clamp-2 block mb-2"
                    >
                      {activity.tender_title}
                    </Link>

                    {/* Details Row */}
                    <div className="flex items-center gap-3 text-xs text-muted-foreground flex-wrap">
                      {activity.amount && (
                        <span className="font-medium text-foreground">
                          {formatAmount(activity.amount)} МКД
                        </span>
                      )}
                      {activity.details?.discount_percent !== undefined &&
                        activity.type === "won" && (
                          <span className={activity.details.discount_percent > 0 ? "text-green-600" : ""}>
                            {activity.details.discount_percent > 0 ? "-" : ""}
                            {Math.abs(activity.details.discount_percent).toFixed(1)}% од проценка
                          </span>
                        )}
                      {activity.details?.num_bidders && (
                        <span>{activity.details.num_bidders} понудувачи</span>
                      )}
                      {activity.details?.rank && activity.details.rank > 1 && (
                        <span>#{activity.details.rank} место</span>
                      )}
                      {mounted && activity.timestamp && (
                        <span className="ml-auto">{formatTimestamp(activity.timestamp)}</span>
                      )}
                    </div>
                  </div>

                  {/* Arrow Link */}
                  <div className="flex-shrink-0">
                    <Link href={`/tenders/${activity.tender_id}`}>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <ArrowRight className="h-4 w-4" />
                      </Button>
                    </Link>
                  </div>
                </div>
              ))}
            </div>

            {/* Load More Button */}
            {hasMore && (
              <div className="flex justify-center mt-6">
                <Button
                  variant="outline"
                  onClick={() => setPage(page + 1)}
                  disabled={loading}
                >
                  Прикажи повеќе
                </Button>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
