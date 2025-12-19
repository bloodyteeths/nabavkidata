"use client";

import { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { DollarSign, BarChart2, TrendingUp } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { api } from "@/lib/api";

interface PriceBenchmarkItem {
  cpv_division: string;
  cpv_division_name: string | null;
  avg_value: number | null;
  median_value: number | null;
  min_value: number | null;
  max_value: number | null;
  tender_count: number;
}

interface PriceBenchmarksData {
  category: string;
  benchmarks: PriceBenchmarkItem[];
  total_divisions: number;
}

const CATEGORY_LABELS: Record<string, string> = {
  "Стоки": "Стоки",
  "Услуги": "Услуги",
  "Работи": "Работи",
  "Goods": "Стоки",
  "Services": "Услуги",
  "Works": "Работи",
};

const COLORS = ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ef4444"];

export function PriceBenchmarks() {
  const [data, setData] = useState<PriceBenchmarksData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  useEffect(() => {
    fetchBenchmarks();
  }, [selectedCategory]);

  const fetchBenchmarks = async () => {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getPriceBenchmarks(
        selectedCategory !== "all" ? selectedCategory : undefined
      );
      setData(result);
    } catch (err: any) {
      setError(err.message || "Failed to load price benchmarks");
      console.error("Error fetching price benchmarks:", err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value: number | null | undefined) => {
    if (value == null) return "Н/Д";
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(1)}M МКД`;
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(0)}K МКД`;
    }
    return `${value.toFixed(0)} МКД`;
  };

  const formatCurrencyShort = (value: number | null | undefined) => {
    if (value == null) return "0";
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(1)}M`;
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(0)}K`;
    }
    return value.toFixed(0);
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Ценовни Показатели
          </CardTitle>
          <CardDescription>
            Анализа на типични цени по категории и сектори
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-12">
            <div className="text-muted-foreground">Се вчитува...</div>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Ценовни Показатели
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-destructive text-center py-12">
            {error || "Нема достапни податоци"}
          </div>
        </CardContent>
      </Card>
    );
  }

  const maxBenchmarkValue = Math.max(
    ...data.benchmarks.map((b) => b.avg_value || 0),
    1
  );

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <DollarSign className="h-5 w-5" />
            Ценовни Показатели
          </CardTitle>
          <CardDescription>
            Анализа на типични цени по категории и сектори - помага на понудувачите да разберат пазарните стандарди
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={selectedCategory} onValueChange={setSelectedCategory}>
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="all">Сите</TabsTrigger>
              <TabsTrigger value="Стоки">Стоки</TabsTrigger>
              <TabsTrigger value="Услуги">Услуги</TabsTrigger>
              <TabsTrigger value="Работи">Работи</TabsTrigger>
            </TabsList>

            <TabsContent value={selectedCategory} className="space-y-6 mt-6">
              {/* CPV Division Rankings */}
              <div>
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Топ CPV сектори (по просечна вредност)
                </h3>
                {data.benchmarks.length > 0 ? (
                  <>
                    {/* Bar Chart */}
                    <div className="mb-6">
                      <ResponsiveContainer width="100%" height={400}>
                        <BarChart
                          data={data.benchmarks.slice(0, 15)}
                          layout="vertical"
                          margin={{ top: 5, right: 30, left: 120, bottom: 5 }}
                        >
                          <XAxis
                            type="number"
                            tickFormatter={(v) => formatCurrencyShort(v)}
                          />
                          <YAxis
                            type="category"
                            dataKey="cpv_division"
                            width={110}
                            tick={{ fontSize: 12 }}
                          />
                          <Tooltip
                            formatter={(value: number) => formatCurrency(value)}
                            labelFormatter={(label) => {
                              const item = data.benchmarks.find(
                                (d) => d.cpv_division === label
                              );
                              return item?.cpv_division_name || label;
                            }}
                          />
                          <Bar dataKey="avg_value" name="Просечна вредност">
                            {data.benchmarks.slice(0, 15).map((_, index) => (
                              <Cell
                                key={`cell-${index}`}
                                fill={COLORS[index % COLORS.length]}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>

                    {/* Detailed List */}
                    <div className="space-y-2">
                      {data.benchmarks.slice(0, 20).map((cpv, index) => (
                        <div
                          key={cpv.cpv_division}
                          className="flex items-center gap-4 p-3 rounded-lg border bg-card/50 hover:bg-accent/50 transition-colors"
                        >
                          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center font-semibold text-sm">
                            {index + 1}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-sm font-medium text-muted-foreground">
                                {cpv.cpv_division}
                              </span>
                              <span className="text-sm truncate">
                                {cpv.cpv_division_name || `Division ${cpv.cpv_division}`}
                              </span>
                            </div>
                            <div className="flex items-center gap-4 mt-1">
                              <span className="text-xs text-muted-foreground">
                                {cpv.tender_count?.toLocaleString() || 0} тендери
                              </span>
                              <Progress
                                value={((cpv.avg_value || 0) / maxBenchmarkValue) * 100}
                                className="h-1.5 flex-1 max-w-xs"
                              />
                            </div>
                          </div>
                          <div className="flex-shrink-0 text-right">
                            <div className="font-semibold">
                              {formatCurrency(cpv.avg_value)}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              просек
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    Нема достапни податоци за CPV сектори
                  </div>
                )}
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      {/* Key Insights Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Клучни наоди</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-start gap-3">
            <div className="h-2 w-2 rounded-full bg-primary mt-2" />
            <p className="text-sm text-muted-foreground">
              Просечните и медијанските вредности помагаат да се разбере типичниот буџет за различни категории тендери
            </p>
          </div>
          <div className="flex items-start gap-3">
            <div className="h-2 w-2 rounded-full bg-primary mt-2" />
            <p className="text-sm text-muted-foreground">
              Опсегот (мин-макс) покажува колку варијабилни се цените во секоја категорија
            </p>
          </div>
          <div className="flex items-start gap-3">
            <div className="h-2 w-2 rounded-full bg-primary mt-2" />
            <p className="text-sm text-muted-foreground">
              CPV секторите со повисоки просечни вредности обично претставуваат покомплексни или поскапи набавки
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
