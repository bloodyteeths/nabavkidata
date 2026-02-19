"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, RefreshCcw } from "lucide-react";
import Link from "next/link";

export default function SupplierStrengthPage() {
  const { id } = useParams();
  const router = useRouter();
  const supplierId = decodeURIComponent(id as string);
  const [data, setData] = useState<any | null>(null);
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
      setData(result);
    } catch (err) {
      console.error("Failed to load supplier strength:", err);
      setError("Статистиките за добавувачот не се достапни.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            Назад
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Сила на добавувач</h1>
            <p className="text-sm text-muted-foreground">Данни од /api/analytics/supplier-strength/{supplierId}</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Освежи
        </Button>
      </div>

      {gated && (
        <Card>
          <CardContent className="py-4 flex items-center justify-between">
            <div>
              <p className="font-medium">Оваа секција е достапна за Pro/Premium.</p>
              <p className="text-xs text-muted-foreground">Ваш план: {tier}. Надоградете за да пристапите до анализа на добавувачи.</p>
            </div>
            <Link href="/settings">
              <Button size="sm" variant="outline">Upgrade</Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {loading && <p className="text-sm text-muted-foreground">Се вчитуваат метриките...</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}

      {!loading && !error && data && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Оценка</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-3xl font-bold">{data.score ?? "-"}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Резиме</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm">
              {data.metrics
                ? Object.entries(data.metrics).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="capitalize">{key.replace(/_/g, " ")}</span>
                      <span className="font-medium">{typeof value === "number" ? value.toLocaleString() : String(value)}</span>
                    </div>
                  ))
                : "Нема метрики."}
            </CardContent>
          </Card>

          {data.breakdown && (
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>Детали</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                {Object.entries(data.breakdown).map(([key, value]) => (
                  <div key={key} className="border rounded-md p-3">
                    <p className="font-semibold capitalize mb-1">{key.replace(/_/g, " ")}</p>
                    <p className="text-muted-foreground">
                      {typeof value === "number" ? value.toLocaleString() : JSON.stringify(value)}
                    </p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
