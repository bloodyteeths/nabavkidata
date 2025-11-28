"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCcw } from "lucide-react";
import Link from "next/link";

export default function CompetitorsPage() {
  const [data, setData] = useState<{ competitors: any[]; summary: any } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tier, setTier] = useState<string>("unknown");
  const [gated, setGated] = useState(false);

  useEffect(() => {
    loadTier();
  }, []);

  useEffect(() => {
    if (!gated) {
      load();
    }
  }, [gated]);

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
      const result = await api.getCompetitorAnalysis({ limit: 20 });
      setData(result);
    } catch (err) {
      console.error("Failed to load competitor analysis:", err);
      setError("Анализата на конкуренти не е достапна.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Анализа на конкуренти</h1>
          <p className="text-sm text-muted-foreground">Данни од /api/analytics/competitor-analysis</p>
        </div>
        <Button size="sm" variant="outline" onClick={load} disabled={loading || gated}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Освежи
        </Button>
      </div>

      {gated && (
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="font-medium">Оваа секција е достапна за Pro/Premium.</p>
              <p className="text-xs text-muted-foreground">Ваш план: {tier}. Надоградете за да пристапите до анализа на конкуренти.</p>
            </div>
            <Link href="/settings">
              <Button size="sm" variant="outline">Upgrade</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {loading && (
        <Card className="animate-pulse">
          <CardContent className="p-4 space-y-2">
            <div className="h-4 bg-muted rounded w-1/3" />
            <div className="h-6 bg-muted rounded w-1/2" />
          </CardContent>
        </Card>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      {!loading && !error && data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Топ конкуренти</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.competitors?.length ? (
                data.competitors.map((row, idx) => (
                  <div key={idx} className="flex items-center justify-between border-b pb-2">
                    <div>
                      <p className="font-medium">{row.name || row.company_name || "Непознат"}</p>
                      <p className="text-xs text-muted-foreground">
                        Победи: {row.wins ?? 0} · Вкупна вредност: {row.total_value_mkd?.toLocaleString() ?? "n/a"}
                      </p>
                    </div>
                    <div className="text-right text-sm">
                      <p className="font-semibold">Понуди: {row.bids_count ?? "-"}</p>
                      {row.win_rate !== undefined && <p className="text-xs text-muted-foreground">Win rate: {row.win_rate}%</p>}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">Нема податоци за конкуренти.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Резиме</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {data.summary
                ? Object.entries(data.summary).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="capitalize">{key.replace(/_/g, " ")}</span>
                      <span className="font-medium">{typeof value === "number" ? value.toLocaleString() : String(value)}</span>
                    </div>
                  ))
                : "Нема резиме."}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
