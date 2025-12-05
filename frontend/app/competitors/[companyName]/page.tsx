"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  Building2,
  TrendingUp,
  Trophy,
  Target,
  Star,
  StarOff,
  Loader2,
  BarChart3,
  Calendar,
} from "lucide-react";
import Link from "next/link";

interface CompanyAnalysis {
  company_name: string;
  summary: string;
  tender_stats: {
    total_bids: number;
    total_wins: number;
    win_rate: number;
    avg_bid_value_mkd?: number;
    total_won_value_mkd?: number;
    first_bid_date?: string;
    last_bid_date?: string;
  };
  recent_wins: Array<{
    tender_id: string;
    title: string;
    procuring_entity: string;
    category: string;
    cpv_code: string;
    contract_value_mkd?: number;
    date?: string;
  }>;
  common_categories: Array<{
    category: string;
    bid_count: number;
    win_count: number;
    won_value_mkd: number;
  }>;
  frequent_institutions: Array<{
    institution: string;
    bid_count: number;
    win_count: number;
    avg_bid_mkd?: number;
  }>;
  ai_insights: string;
}

export default function CompetitorDetailPage() {
  const params = useParams();
  const router = useRouter();
  const companyName = decodeURIComponent(params.companyName as string);

  const [analysis, setAnalysis] = useState<CompanyAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isTracked, setIsTracked] = useState(false);
  const [trackingLoading, setTrackingLoading] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    loadCompanyAnalysis();
    checkIfTracked();
  }, [companyName]);

  const loadCompanyAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log("Loading company analysis for:", companyName);
      const data = await api.analyzeCompany(companyName);
      console.log("Company analysis loaded:", data);
      setAnalysis(data);
    } catch (err: any) {
      console.error("Failed to load company analysis:", err);
      // More detailed error message
      let errorMsg = "Грешка при вчитување на анализата";
      if (err.message) {
        if (err.message.includes("401")) {
          errorMsg = "Сесијата истече. Најавете се повторно.";
        } else if (err.message.includes("404")) {
          errorMsg = "Не се пронајдени податоци за оваа компанија.";
        } else if (err.message.includes("500")) {
          errorMsg = "Серверска грешка. Обидете се подоцна.";
        } else {
          errorMsg = err.message;
        }
      }
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const checkIfTracked = async () => {
    try {
      const data = await api.getTrackedCompetitors();
      setIsTracked(data.tracked_competitors.includes(companyName));
    } catch (err) {
      console.error("Failed to check tracked status:", err);
    }
  };

  const toggleTracking = async () => {
    try {
      setTrackingLoading(true);
      if (isTracked) {
        await api.removeTrackedCompetitor(companyName);
        setIsTracked(false);
      } else {
        await api.addTrackedCompetitor(companyName);
        setIsTracked(true);
      }
    } catch (err: any) {
      console.error("Failed to toggle tracking:", err);
    } finally {
      setTrackingLoading(false);
    }
  };

  const formatCurrency = (value?: number) => {
    if (!value) return "N/A";
    return new Intl.NumberFormat("mk-MK", {
      style: "decimal",
      maximumFractionDigits: 0,
    }).format(value) + " МКД";
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return "N/A";
    return new Date(dateStr).toLocaleDateString("mk-MK", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  if (loading) {
    return (
      <div className="container mx-auto py-6">
        <div className="flex items-center gap-4 mb-6">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="grid gap-6 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-64 mt-6" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-6">
        <div className="flex items-center gap-4 mb-6">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <h1 className="text-2xl font-bold">{companyName}</h1>
        </div>
        <Card className="border-red-200 bg-red-50 dark:bg-red-950/20">
          <CardContent className="pt-6">
            <p className="text-red-600 dark:text-red-400">{error}</p>
            <Button variant="outline" className="mt-4" onClick={loadCompanyAnalysis}>
              Обиди се повторно
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!analysis) return null;

  return (
    <div className="container mx-auto py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Building2 className="h-6 w-6 text-blue-600" />
              {analysis.company_name}
            </h1>
            <p className="text-muted-foreground text-sm mt-1">
              Детална анализа на конкурент
            </p>
          </div>
        </div>
        <Button
          variant={isTracked ? "default" : "outline"}
          onClick={toggleTracking}
          disabled={trackingLoading}
          className="gap-2"
        >
          {trackingLoading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : isTracked ? (
            <>
              <Star className="h-4 w-4 fill-current" />
              Следен
            </>
          ) : (
            <>
              <StarOff className="h-4 w-4" />
              Следи
            </>
          )}
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4 mb-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
              <Target className="h-4 w-4" />
              Вкупно понуди
            </div>
            <p className="text-3xl font-bold">{analysis.tender_stats.total_bids}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
              <Trophy className="h-4 w-4" />
              Победи
            </div>
            <p className="text-3xl font-bold text-green-600">{analysis.tender_stats.total_wins}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
              <TrendingUp className="h-4 w-4" />
              Успешност
            </div>
            <p className="text-3xl font-bold">{analysis.tender_stats.win_rate.toFixed(1)}%</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
              <BarChart3 className="h-4 w-4" />
              Вкупна вредност
            </div>
            <p className="text-xl font-bold truncate">
              {formatCurrency(analysis.tender_stats.total_won_value_mkd)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* AI Insights */}
      {analysis.ai_insights && (
        <Card className="mb-6 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span className="text-blue-600">AI</span> Анализа
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm whitespace-pre-wrap">{analysis.ai_insights}</p>
          </CardContent>
        </Card>
      )}

      {/* Two Column Layout */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Wins */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trophy className="h-5 w-5 text-yellow-500" />
              Последни победи
            </CardTitle>
          </CardHeader>
          <CardContent>
            {analysis.recent_wins.length === 0 ? (
              <p className="text-muted-foreground text-sm">Нема податоци за победи</p>
            ) : (
              <div className="space-y-3">
                {analysis.recent_wins.slice(0, 5).map((win, idx) => (
                  <Link
                    key={idx}
                    href={`/tenders/${encodeURIComponent(win.tender_id)}`}
                    className="block p-3 border rounded-lg hover:bg-accent transition-colors"
                  >
                    <p className="font-medium text-sm line-clamp-2">{win.title}</p>
                    <div className="flex items-center justify-between mt-2 text-xs text-muted-foreground">
                      <span>{win.procuring_entity}</span>
                      {win.contract_value_mkd && (
                        <Badge variant="secondary">
                          {formatCurrency(win.contract_value_mkd)}
                        </Badge>
                      )}
                    </div>
                    {mounted && win.date && (
                      <p className="text-xs text-muted-foreground mt-1">
                        <Calendar className="inline h-3 w-3 mr-1" />
                        {formatDate(win.date)}
                      </p>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Common Categories */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="h-5 w-5 text-blue-500" />
              Категории на активност
            </CardTitle>
          </CardHeader>
          <CardContent>
            {analysis.common_categories.length === 0 ? (
              <p className="text-muted-foreground text-sm">Нема податоци за категории</p>
            ) : (
              <div className="space-y-3">
                {analysis.common_categories.slice(0, 5).map((cat, idx) => (
                  <div key={idx} className="flex items-center justify-between p-2 border rounded">
                    <div>
                      <p className="font-medium text-sm">{cat.category}</p>
                      <p className="text-xs text-muted-foreground">
                        {cat.bid_count} понуди, {cat.win_count} победи
                      </p>
                    </div>
                    <Badge
                      variant={cat.win_count > 0 ? "default" : "secondary"}
                    >
                      {((cat.win_count / cat.bid_count) * 100).toFixed(0)}%
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Frequent Institutions */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-purple-500" />
              Чести институции
            </CardTitle>
          </CardHeader>
          <CardContent>
            {analysis.frequent_institutions.length === 0 ? (
              <p className="text-muted-foreground text-sm">Нема податоци за институции</p>
            ) : (
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {analysis.frequent_institutions.slice(0, 6).map((inst, idx) => (
                  <div key={idx} className="p-3 border rounded-lg">
                    <p className="font-medium text-sm line-clamp-2">{inst.institution}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                      <span>{inst.bid_count} понуди</span>
                      <span className="text-green-600">{inst.win_count} победи</span>
                    </div>
                    {inst.avg_bid_mkd && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Просечна понуда: {formatCurrency(inst.avg_bid_mkd)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
