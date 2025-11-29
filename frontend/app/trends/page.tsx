"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RefreshCcw, TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  LineChart,
  Line,
} from "recharts";

export default function TrendsPage() {
  const [cpv, setCpv] = useState("");
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getCategoryTrends(cpv ? { cpv_code: cpv } : undefined);
      setData(result);
    } catch (err) {
      console.error("Failed to load category trends:", err);
      setError("Трендовите по категории не се достапни.");
    } finally {
      setLoading(false);
    }
  }

  // Format large numbers
  const formatValue = (val: number) => {
    if (val >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(1)}B`;
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K`;
    return val?.toFixed ? val.toFixed(0) : String(val);
  };

  // Prepare chart data - group by month with categories as separate bars
  const monthlyData: Record<string, any> = {};
  data?.categories?.forEach((cat: any) => {
    cat.monthly_trend?.forEach((t: any) => {
      if (!monthlyData[t.month]) {
        monthlyData[t.month] = { month: t.month };
      }
      monthlyData[t.month][cat.category] = t.value || 0;
      monthlyData[t.month][`${cat.category}_count`] = t.count || 0;
    });
  });
  const chartData = Object.values(monthlyData).sort((a: any, b: any) =>
    a.month.localeCompare(b.month)
  );

  // Category colors
  const categoryColors: Record<string, string> = {
    "Стоки": "#3b82f6",
    "Услуги": "#10b981",
    "Работи": "#f59e0b",
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Трендови по категории</h1>
          <p className="text-sm text-muted-foreground">
            Преглед на тендери по категорија (Стоки, Услуги, Работи)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Input
            placeholder="CPV код (опционално)"
            value={cpv}
            onChange={(e) => setCpv(e.target.value)}
            className="w-48"
          />
          <Button size="sm" onClick={load} disabled={loading}>
            <RefreshCcw className="h-4 w-4 mr-2" />
            Освежи
          </Button>
        </div>
      </div>

      {loading && <p className="text-sm text-muted-foreground">Се вчитуваат трендовите...</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {!loading && !error && data && (
        <>
          {/* Category Summary Cards */}
          {data.categories && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {data.categories.map((cat: any) => {
                // Calculate trend from monthly data
                const trend = cat.monthly_trend || [];
                const lastTwo = trend.slice(-2);
                let trendDirection = 0;
                if (lastTwo.length === 2 && lastTwo[0].count && lastTwo[1].count) {
                  trendDirection = lastTwo[1].count > lastTwo[0].count ? 1 :
                                   lastTwo[1].count < lastTwo[0].count ? -1 : 0;
                }

                return (
                  <Card key={cat.category} className="relative overflow-hidden">
                    <div
                      className="absolute top-0 left-0 w-1 h-full"
                      style={{ backgroundColor: categoryColors[cat.category] || "#888" }}
                    />
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center justify-between">
                        <span>{cat.category}</span>
                        {trendDirection === 1 && <TrendingUp className="h-4 w-4 text-green-500" />}
                        {trendDirection === -1 && <TrendingDown className="h-4 w-4 text-red-500" />}
                        {trendDirection === 0 && <Minus className="h-4 w-4 text-gray-400" />}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div>
                        <p className="text-3xl font-bold">{cat.tender_count?.toLocaleString() || 0}</p>
                        <p className="text-xs text-muted-foreground">тендери</p>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div>
                          <p className="font-medium">{formatValue(cat.total_value_mkd || 0)} МКД</p>
                          <p className="text-xs text-muted-foreground">вкупно</p>
                        </div>
                        <div>
                          <p className="font-medium">{formatValue(cat.avg_value_mkd || 0)} МКД</p>
                          <p className="text-xs text-muted-foreground">просечно</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          {/* Value Chart */}
          {chartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Вредност по месеци (МКД)</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={350}>
                  <BarChart data={chartData}>
                    <XAxis dataKey="month" />
                    <YAxis tickFormatter={formatValue} />
                    <Tooltip
                      formatter={(val: number) => `${formatValue(val)} МКД`}
                      labelFormatter={(label) => `Месец: ${label}`}
                    />
                    <Legend />
                    {data.categories?.map((cat: any) => (
                      <Bar
                        key={cat.category}
                        dataKey={cat.category}
                        name={cat.category}
                        fill={categoryColors[cat.category] || "#888"}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Count Chart */}
          {chartData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Број на тендери по месеци</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip
                      formatter={(val: number) => `${val} тендери`}
                      labelFormatter={(label) => `Месец: ${label}`}
                    />
                    <Legend />
                    {data.categories?.map((cat: any) => (
                      <Line
                        key={cat.category}
                        type="monotone"
                        dataKey={`${cat.category}_count`}
                        name={cat.category}
                        stroke={categoryColors[cat.category] || "#888"}
                        strokeWidth={2}
                        dot={{ r: 4 }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {chartData.length === 0 && (
            <p className="text-sm text-muted-foreground">Нема податоци за трендови.</p>
          )}
        </>
      )}
    </div>
  );
}
