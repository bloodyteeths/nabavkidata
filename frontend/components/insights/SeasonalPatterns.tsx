"use client";

import { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Calendar, BarChart2, TrendingUp, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface PatternData {
  month: string;
  month_name: string;
  tender_count: number;
  total_value: number | null;
  avg_value: number | null;
  category_breakdown: Record<string, number>;
}

interface SeasonalPatternsData {
  patterns: PatternData[];
  total_months: number;
}

const CATEGORY_COLORS: Record<string, string> = {
  "Стоки": "#3b82f6",
  "Услуги": "#10b981",
  "Работи": "#f59e0b",
};

export default function SeasonalPatterns() {
  const [data, setData] = useState<SeasonalPatternsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"count" | "value">("count");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getSeasonalPatterns();
      setData(result);
    } catch (err: any) {
      console.error("Failed to load seasonal patterns:", err);
      setError(err.message || "Failed to load seasonal patterns");
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Сезонски модели
          </CardTitle>
          <CardDescription>
            Кога обично се објавуваат тендери
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[400px] flex items-center justify-center text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            Се вчитува...
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Сезонски модели
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[300px] flex flex-col items-center justify-center text-muted-foreground">
            <p className="text-destructive mb-2">{error}</p>
            <button
              onClick={loadData}
              className="text-sm text-primary hover:underline"
            >
              Обиди се повторно
            </button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data || !data.patterns || data.patterns.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Сезонски модели
          </CardTitle>
          <CardDescription>
            Кога обично се објавуваат тендери
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[400px] flex items-center justify-center text-muted-foreground">
            Нема доволно податоци за прикажување на сезонски модели
          </div>
        </CardContent>
      </Card>
    );
  }

  const patterns = data.patterns;

  // Format data for charts - reverse to show oldest first
  const chartData = [...patterns].reverse().map((item) => ({
    month: item.month_name,
    count: item.tender_count,
    value: (item.total_value || 0) / 1_000_000,
    Стоки: item.category_breakdown["Стоки"] || 0,
    Услуги: item.category_breakdown["Услуги"] || 0,
    Работи: item.category_breakdown["Работи"] || 0,
  }));

  // Find quietest month
  const quietestMonth = patterns.reduce((min, item) =>
    item.tender_count < min.tender_count ? item : min
  , patterns[0]);

  // Find busiest month
  const busiestMonth = patterns.reduce((max, item) =>
    item.tender_count > max.tender_count ? item : max
  , patterns[0]);

  // Calculate best months per category
  const categoryMonths: Record<string, { month: string; count: number }[]> = {};
  for (const p of patterns) {
    for (const [cat, count] of Object.entries(p.category_breakdown)) {
      if (!categoryMonths[cat]) categoryMonths[cat] = [];
      categoryMonths[cat].push({ month: p.month_name, count: count as number });
    }
  }
  const best_months: Record<string, string[]> = {};
  for (const [cat, months] of Object.entries(categoryMonths)) {
    const sorted = months.sort((a, b) => b.count - a.count);
    best_months[cat] = sorted.slice(0, 2).map(m => m.month);
  }

  const formatValue = (val: number) => {
    if (viewMode === "value") {
      return `${val.toFixed(1)}M МКД`;
    }
    return val.toFixed(0);
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Calendar className="h-5 w-5" />
              Сезонски модели / Кога да се јавите
            </CardTitle>
            <CardDescription>
              Вкупна историска активност по месец (2008-2025) - 221,000+ тендери
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setViewMode("count")}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                viewMode === "count"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              Број
            </button>
            <button
              onClick={() => setViewMode("value")}
              className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                viewMode === "value"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              Вредност
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Summary Insights */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-lg border bg-card/50">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="h-4 w-4 text-green-600" />
              <span className="text-sm font-medium text-muted-foreground">
                Најактивен месец
              </span>
            </div>
            <div className="text-2xl font-bold">{busiestMonth.month_name.trim()}</div>
            <div className="text-sm text-muted-foreground">
              {busiestMonth.tender_count.toLocaleString()} тендери вкупно
            </div>
          </div>

          <div className="p-4 rounded-lg border bg-card/50">
            <div className="flex items-center gap-2 mb-2">
              <BarChart2 className="h-4 w-4 text-orange-600" />
              <span className="text-sm font-medium text-muted-foreground">
                Најмирен период
              </span>
            </div>
            <div className="text-2xl font-bold">{quietestMonth.month_name.trim()}</div>
            <div className="text-sm text-muted-foreground">
              {quietestMonth.tender_count.toLocaleString()} тендери вкупно
            </div>
          </div>

          <div className="p-4 rounded-lg border bg-card/50">
            <div className="flex items-center gap-2 mb-2">
              <Calendar className="h-4 w-4 text-blue-600" />
              <span className="text-sm font-medium text-muted-foreground">
                Вкупно историски
              </span>
            </div>
            <div className="text-2xl font-bold">
              {patterns.reduce((sum, item) => sum + item.tender_count, 0).toLocaleString()}
            </div>
            <div className="text-sm text-muted-foreground">
              Тендери (2008-2025)
            </div>
          </div>
        </div>

        {/* Best Months by Category */}
        {best_months && Object.keys(best_months).length > 0 && (
          <div className="space-y-3">
            <h3 className="text-sm font-semibold">Најдобри месеци по категорија</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {Object.entries(best_months).map(([category, months]) => (
                <div key={category} className="flex items-center gap-2">
                  <Badge
                    variant="outline"
                    className="font-medium"
                    style={{
                      borderColor: CATEGORY_COLORS[category] || "#94a3b8",
                      color: CATEGORY_COLORS[category] || "#94a3b8",
                    }}
                  >
                    {category}
                  </Badge>
                  <span className="text-sm text-muted-foreground">
                    {months.join(", ")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Charts in Tabs */}
        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="overview">Преглед</TabsTrigger>
            <TabsTrigger value="categories">По категорија</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-4">
            <ResponsiveContainer width="100%" height={350}>
              <BarChart
                data={chartData}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11 }}
                  angle={-45}
                  textAnchor="end"
                  height={80}
                />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                  }}
                  formatter={(value: number) => formatValue(value)}
                  cursor={{ fill: "hsl(var(--muted))", opacity: 0.3 }}
                />
                <Bar
                  dataKey={viewMode === "count" ? "count" : "value"}
                  fill="#3b82f6"
                  radius={[8, 8, 0, 0]}
                  name={viewMode === "count" ? "Број на тендери" : "Вредност"}
                />
              </BarChart>
            </ResponsiveContainer>
          </TabsContent>

          <TabsContent value="categories" className="mt-4">
            <ResponsiveContainer width="100%" height={350}>
              <LineChart
                data={chartData}
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11 }}
                  angle={-45}
                  textAnchor="end"
                  height={80}
                />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="Стоки"
                  stroke={CATEGORY_COLORS["Стоки"]}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="Услуги"
                  stroke={CATEGORY_COLORS["Услуги"]}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="Работи"
                  stroke={CATEGORY_COLORS["Работи"]}
                  strokeWidth={2}
                  dot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </TabsContent>
        </Tabs>

        {/* Data Quality Note */}
        <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-200">
          <strong>Забелешка:</strong> Графиконот прикажува вкупен број на тендери по месец од сите години (2008-2025).
          Декември историски има најмногу тендери, а Јануари најмалку.
        </div>

        {/* Business Planning Insight */}
        <div className="p-4 rounded-lg bg-muted/50 border-l-4 border-blue-600">
          <h4 className="font-semibold text-sm mb-2 flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Совети за планирање
          </h4>
          <ul className="text-sm text-muted-foreground space-y-1">
            <li>
              • Најактивниот месец е <strong>{busiestMonth.month_name}</strong> -
              очекувајте повеќе конкуренција
            </li>
            <li>
              • <strong>{quietestMonth.month_name}</strong> е најмирен период -
              може да има помалку конкуренција
            </li>
            {best_months && Object.keys(best_months).length > 0 && (
              <li>
                • Планирајте ги вашите ресурси според сезонските трендови по категорија
              </li>
            )}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
