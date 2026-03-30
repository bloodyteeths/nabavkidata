"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  RefreshCcw,
  TrendingUp,
  TrendingDown,
  Minus,
  Trophy,
  Banknote,
  BarChart3,
  Activity,
  Medal,
} from "lucide-react";
import Link from "next/link";
import { formatCurrency, formatDate, tenderUrl } from "@/lib/utils";

interface StrengthData {
  supplier_id: string;
  company_name: string;
  strength_score: number;
  metrics: {
    win_rate: number;
    total_wins: number;
    total_bids: number;
    total_value_mkd: number;
    market_share: number | null;
    category_diversity: number;
    entity_relationships: number;
    value_tier: string;
  };
  rankings: {
    overall: number;
    in_city: number | null;
  };
  trends: {
    win_rate_6m: number;
    win_rate_12m: number;
    win_rate_trend: string;
    activity_trend: string;
  };
  recent_activity: {
    tender_id: string;
    title: string;
    bid_amount: number | null;
    won: boolean;
    date: string | null;
  }[];
  generated_at: string;
}

function getScoreLabel(score: number): { label: string; color: string; bgColor: string; ringColor: string } {
  if (score <= 30) return { label: "Слаб", color: "text-red-600", bgColor: "bg-red-500", ringColor: "text-red-500" };
  if (score <= 60) return { label: "Среден", color: "text-yellow-600", bgColor: "bg-yellow-500", ringColor: "text-yellow-500" };
  if (score <= 80) return { label: "Добар", color: "text-green-600", bgColor: "bg-green-500", ringColor: "text-green-500" };
  return { label: "Одличен", color: "text-purple-600", bgColor: "bg-purple-500", ringColor: "text-purple-500" };
}

function getWinRateInterpretation(rate: number): string {
  if (rate > 70) return "врвен";
  if (rate > 50) return "над просекот";
  if (rate >= 30) return "просечно";
  return "под просекот";
}

function getTrendInfo(trend: string): { icon: React.ReactNode; text: string; color: string } {
  switch (trend) {
    case "improving":
    case "increasing":
      return { icon: <TrendingUp className="h-4 w-4" />, text: "Во подем", color: "text-green-600" };
    case "declining":
    case "decreasing":
      return { icon: <TrendingDown className="h-4 w-4" />, text: "Во опаѓање", color: "text-red-600" };
    default:
      return { icon: <Minus className="h-4 w-4" />, text: "Стабилен", color: "text-muted-foreground" };
  }
}

function getValueTierLabel(tier: string): string {
  switch (tier) {
    case "small": return "Мали договори (< 1М МКД)";
    case "medium": return "Средни договори (1М - 10М МКД)";
    case "large": return "Големи договори (10М - 50М МКД)";
    case "enterprise": return "Ентерпрајз договори (> 50М МКД)";
    default: return tier;
  }
}

function ScoreGauge({ score }: { score: number }) {
  const { label, color, bgColor } = getScoreLabel(score);
  const circumference = 2 * Math.PI * 54;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative w-36 h-36">
        <svg className="w-36 h-36 -rotate-90" viewBox="0 0 120 120">
          <circle
            cx="60" cy="60" r="54"
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            className="text-muted/30"
          />
          <circle
            cx="60" cy="60" r="54"
            fill="none"
            stroke="currentColor"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            className={getScoreLabel(score).ringColor}
            style={{ transition: "stroke-dashoffset 1s ease-out" }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-3xl font-bold">{Math.round(score)}</span>
          <span className="text-xs text-muted-foreground">/ 100</span>
        </div>
      </div>
      <Badge className={`${bgColor} text-white text-sm px-3 py-1`}>{label}</Badge>
    </div>
  );
}

export default function SupplierStrengthPage() {
  const { id } = useParams();
  const router = useRouter();
  const supplierId = decodeURIComponent(id as string);
  const [data, setData] = useState<StrengthData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tier, setTier] = useState<string>("unknown");
  const [gated, setGated] = useState(false);

  useEffect(() => {
    loadTier();
  }, [supplierId]);

  useEffect(() => {
    if (!gated) load();
  }, [gated, supplierId]);

  async function loadTier() {
    try {
      const status = await api.getSubscriptionStatus();
      setTier(status.tier || "free");
      setGated(status.tier === "free");
    } catch {
      setTier("free");
      setGated(true);
    }
  }

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getSupplierStrength(supplierId);
      setData(result as unknown as StrengthData);
    } catch (err) {
      console.error("Failed to load supplier strength:", err);
      setError("Статистиките за добавувачот не се достапни.");
    } finally {
      setLoading(false);
    }
  }

  const m = data?.metrics;
  const r = data?.rankings;
  const t = data?.trends;

  return (
    <div className="container mx-auto py-8 px-4 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            Назад
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Анализа на сила</h1>
            {data && (
              <p className="text-sm text-muted-foreground">{data.company_name}</p>
            )}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading || gated}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Освежи
        </Button>
      </div>

      {/* Tier gate */}
      {gated && (
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="font-medium">Оваа секција е достапна за Starter/Pro/Premium.</p>
              <p className="text-xs text-muted-foreground">Ваш план: {tier}. Надоградете за да пристапите до анализа на добавувачи.</p>
            </div>
            <Link href="/settings">
              <Button size="sm" variant="outline">Надоградете</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {loading && (
        <div className="flex items-center justify-center h-40">
          <div className="flex items-center gap-2">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
            <span className="text-sm text-muted-foreground">Се вчитуваат метриките...</span>
          </div>
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      {!loading && !error && data && m && t && r && (
        <>
          {/* Score + Summary Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Score Gauge */}
            <Card className="lg:row-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Medal className="h-5 w-5" />
                  Вкупна оценка
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col items-center gap-4">
                <ScoreGauge score={data.strength_score} />
                <div className="text-center text-sm text-muted-foreground max-w-xs">
                  Оценката се базира на стапка на победа, волумен, вредност на договори, диверзитет на категории и институционални врски.
                </div>
                {/* Rankings */}
                {(r.overall || r.in_city) && (
                  <div className="w-full border-t pt-4 mt-2 space-y-2">
                    {r.overall && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Национално рангирање</span>
                        <Badge variant="outline" className="font-mono">#{r.overall}</Badge>
                      </div>
                    )}
                    {r.in_city && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Рангирање во град</span>
                        <Badge variant="outline" className="font-mono">#{r.in_city}</Badge>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Participation Card */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Trophy className="h-5 w-5 text-yellow-500" />
                  Учество
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Вкупно понуди</p>
                    <p className="text-2xl font-bold">{m.total_bids}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Победи</p>
                    <p className="text-2xl font-bold">{m.total_wins}</p>
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm">Стапка на победа</span>
                    <span className="text-sm font-semibold">{m.win_rate.toFixed(1)}%</span>
                  </div>
                  <Progress
                    value={Math.min(m.win_rate, 100)}
                    className="h-3"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    {getWinRateInterpretation(m.win_rate)} — {m.win_rate > 50 ? "над" : m.win_rate >= 30 ? "околу" : "под"} просекот на пазарот
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Value Card */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Banknote className="h-5 w-5 text-green-500" />
                  Вредност
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-xs text-muted-foreground">Вкупна вредност на договори</p>
                  <p className="text-2xl font-bold">{formatCurrency(m.total_value_mkd)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Категорија</p>
                  <Badge variant="secondary" className="mt-1">{getValueTierLabel(m.value_tier)}</Badge>
                </div>
              </CardContent>
            </Card>

            {/* Diversity Card */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BarChart3 className="h-5 w-5 text-blue-500" />
                  Диверзитет
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Категории</span>
                  <span className="text-lg font-bold">{m.category_diversity}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Институции (победи)</span>
                  <span className="text-lg font-bold">{m.entity_relationships}</span>
                </div>
                <p className="text-xs text-muted-foreground">
                  {m.category_diversity >= 5
                    ? "Широк спектар на категории - добро диверзифициран"
                    : m.category_diversity >= 3
                    ? "Умерена диверзификација"
                    : "Тесна специјализација - фокусиран добавувач"}
                </p>
              </CardContent>
            </Card>

            {/* Trends Card */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Activity className="h-5 w-5 text-purple-500" />
                  Трендови
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-xs text-muted-foreground">Стапка (6 мес.)</p>
                    <p className="text-xl font-bold">{t.win_rate_6m.toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground">Стапка (12 мес.)</p>
                    <p className="text-xl font-bold">{t.win_rate_12m.toFixed(1)}%</p>
                  </div>
                </div>
                <div className="space-y-2 border-t pt-3">
                  {(() => {
                    const wrTrend = getTrendInfo(t.win_rate_trend);
                    return (
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Стапка на победа</span>
                        <span className={`flex items-center gap-1 text-sm font-medium ${wrTrend.color}`}>
                          {wrTrend.icon} {wrTrend.text}
                        </span>
                      </div>
                    );
                  })()}
                  {(() => {
                    const actTrend = getTrendInfo(t.activity_trend);
                    return (
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-muted-foreground">Активност</span>
                        <span className={`flex items-center gap-1 text-sm font-medium ${actTrend.color}`}>
                          {actTrend.icon} {actTrend.text}
                        </span>
                      </div>
                    );
                  })()}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Recent Activity Table */}
          {data.recent_activity && data.recent_activity.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Последна активност</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Тендер</TableHead>
                      <TableHead className="text-right">Понуда</TableHead>
                      <TableHead className="text-center">Статус</TableHead>
                      <TableHead className="text-right">Датум</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.recent_activity.map((a) => (
                      <TableRow key={a.tender_id}>
                        <TableCell>
                          <Link
                            href={tenderUrl(a.tender_id)}
                            className="font-medium hover:text-primary line-clamp-2"
                          >
                            {a.title}
                          </Link>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {a.bid_amount ? formatCurrency(a.bid_amount) : "-"}
                        </TableCell>
                        <TableCell className="text-center">
                          {a.won ? (
                            <Badge className="bg-green-500 text-white">Победник</Badge>
                          ) : (
                            <Badge variant="secondary">Учесник</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          {a.date ? formatDate(a.date) : "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
