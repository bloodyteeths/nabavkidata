"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PriceHistoryChart } from "@/components/charts/PriceHistoryChart";
import { RefreshCcw } from "lucide-react";

export default function TrendsPage() {
  const [cpv, setCpv] = useState("");
  const [data, setData] = useState<{ trends: any[]; summary: any } | null>(null);
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

  const chartData =
    data?.trends?.map((t) => ({
      date: t.date || t.period || "",
      value: t.total_value_mkd || t.avg_value_mkd || 0,
    })) || [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">Трендови по категории</h1>
          <p className="text-sm text-muted-foreground">Данни од /api/analytics/category-trends</p>
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

      {!loading && !error && (
        <>
          {data?.summary && (
            <Card>
              <CardHeader>
                <CardTitle>Резиме</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {Object.entries(data.summary).map(([key, value]) => (
                  <div key={key} className="flex justify-between">
                    <span className="capitalize">{key.replace(/_/g, " ")}</span>
                    <span className="font-medium">{typeof value === "number" ? value.toLocaleString() : String(value)}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {chartData.length > 0 ? (
            <PriceHistoryChart
              data={chartData}
              xKey="date"
              series={[{ key: "value", label: "Вкупна вредност" }]}
              title="Тренд по време"
            />
          ) : (
            <p className="text-sm text-muted-foreground">Нема податоци за трендови.</p>
          )}
        </>
      )}
    </div>
  );
}
