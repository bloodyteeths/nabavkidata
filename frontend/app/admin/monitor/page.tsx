"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, CheckCircle, RefreshCcw } from "lucide-react";

interface HealthResponse {
  status: string;
  timestamp: string;
  database?: { status: string; tenders?: number } | string;
  scraper?: any;
  cron?: string;
  rag?: string;
}

export default function MonitorPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadHealth = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("health request failed");
      const data = await res.json();
      setHealth(data);
    } catch (e: any) {
      setError("Не може да се вчита health");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, []);

  const statusBadge = (value?: string) => {
    const ok = value && value.includes("ok");
    return (
      <Badge variant={ok ? "default" : "destructive"}>
        {ok ? "OK" : value || "n/a"}
      </Badge>
    );
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Мониторинг</h1>
          <p className="text-muted-foreground text-sm">
            Health за API, Cron, Scraper и база (активни тендери)
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={loadHealth} disabled={loading}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Освежи
        </Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>API</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-2">
              {health?.status === "healthy" ? (
                <CheckCircle className="h-4 w-4 text-green-500" />
              ) : (
                <AlertCircle className="h-4 w-4 text-yellow-500" />
              )}
              <span>{health?.status || "n/a"}</span>
            </div>
            <div className="text-xs text-muted-foreground">{health?.timestamp}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>База</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div>
              Статус: {typeof health?.database === "string" ? health?.database : statusBadge(health?.database?.status as string)}
            </div>
            <div>Тендери: {typeof health?.database === "string" ? "n/a" : health?.database?.tenders ?? "n/a"}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div>RAG: {health?.rag}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Scraper / Cron</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <div>Крон: {health?.cron || "n/a"}</div>
          <div>
            Последен health запис:
            <pre className="bg-muted mt-2 p-3 rounded text-xs overflow-auto">
              {health?.scraper ? JSON.stringify(health.scraper, null, 2) : "n/a"}
            </pre>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
