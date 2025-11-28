"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCcw } from "lucide-react";

export default function AnalyticsPage() {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getMarketOverview();
      setData(result);
    } catch (err: any) {
      console.error("Failed to load market overview:", err);
      setError("Пазарниот преглед не е достапен моментално.");
    } finally {
      setLoading(false);
    }
  }

  const cards = data?.cards || [];
  const charts = data?.charts || {};

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Пазарен преглед</h1>
          <p className="text-sm text-muted-foreground">Клучни метрики и трендови од /api/analytics/market-overview</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Освежи
        </Button>
      </div>

      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-4 space-y-3">
                <div className="h-4 bg-muted rounded w-1/3" />
                <div className="h-6 bg-muted rounded w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      {!loading && !error && (
        <>
          {cards.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {cards.map((card: any, idx: number) => (
                <Card key={idx}>
                  <CardHeader>
                    <CardTitle>{card.title || "Метрика"}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-1">
                    <p className="text-2xl font-bold">{card.value ?? "-"}</p>
                    {card.subtitle && <p className="text-xs text-muted-foreground">{card.subtitle}</p>}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {charts?.by_status && (
            <Card>
              <CardHeader>
                <CardTitle>Статуси</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {charts.by_status.map((row: any, idx: number) => (
                  <div key={idx} className="flex justify-between border-b py-1">
                    <span className="capitalize">{row.status || "n/a"}</span>
                    <span className="font-medium">{row.count?.toLocaleString() ?? "-"}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
