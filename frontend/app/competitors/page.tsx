"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { RefreshCcw, Lock, Trophy, Users, TrendingUp, DollarSign } from "lucide-react";
import Link from "next/link";

export default function CompetitorsPage() {
  const [data, setData] = useState<{ competitors: any[]; summary: any } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tier, setTier] = useState<string | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    checkAuthAndLoad();
  }, []);

  async function checkAuthAndLoad() {
    try {
      const status = await api.getSubscriptionStatus();
      setTier(status.tier || "free");
      setIsLoggedIn(true);

      // Only load data if user has access
      if (status.tier !== "free") {
        load();
      }
    } catch (err: any) {
      // Not logged in
      setIsLoggedIn(false);
      setTier(null);
    }
  }

  async function load() {
    try {
      setLoading(true);
      setError(null);
      const result = await api.getCompetitorAnalysis({ limit: 20 });
      setData(result);
    } catch (err: any) {
      console.error("Failed to load competitor analysis:", err);
      if (err.message?.includes("403") || err.message?.includes("Starter")) {
        setError("Оваа функција бара Starter план или повисок.");
      } else {
        setError("Анализата на конкуренти не е достапна.");
      }
    } finally {
      setLoading(false);
    }
  }

  // Show login/upgrade gate
  if (!isLoggedIn || tier === "free") {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Анализа на конкуренти</h1>
          <p className="text-sm text-muted-foreground">
            Дознајте кои компании најмногу добиваат тендери
          </p>
        </div>

        <Card className="border-2 border-dashed">
          <CardContent className="py-12 flex flex-col items-center text-center space-y-4">
            <div className="p-4 bg-muted rounded-full">
              <Lock className="h-8 w-8 text-muted-foreground" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">Премиум функција</h2>
              <p className="text-muted-foreground mt-1 max-w-md">
                Анализата на конкуренти е достапна за корисници со Starter план или повисок.
                {!isLoggedIn && " Најавете се за да продолжите."}
              </p>
            </div>
            <div className="flex gap-3">
              {!isLoggedIn ? (
                <>
                  <Link href="/auth/login">
                    <Button>Најава</Button>
                  </Link>
                  <Link href="/auth/register">
                    <Button variant="outline">Регистрација</Button>
                  </Link>
                </>
              ) : (
                <Link href="/settings">
                  <Button>Надоградете план</Button>
                </Link>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Preview of what they would see */}
        <div className="opacity-50 pointer-events-none">
          <h3 className="text-lg font-medium mb-4">Што добивате со оваа функција:</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardHeader>
                <Trophy className="h-6 w-6 text-yellow-500 mb-2" />
                <CardTitle className="text-base">Топ победници</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Листа на компании со највеќе победени тендери и нивна успешност
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <Users className="h-6 w-6 text-blue-500 mb-2" />
                <CardTitle className="text-base">Статистика на понуди</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Број на понуди, win rate и историја на учество
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <DollarSign className="h-6 w-6 text-green-500 mb-2" />
                <CardTitle className="text-base">Вкупни вредности</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Вкупна вредност на победени тендери по компанија
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Анализа на конкуренти</h1>
          <p className="text-sm text-muted-foreground">
            Топ компании по број на победени тендери
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Освежи
        </Button>
      </div>

      {loading && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardContent className="p-4 space-y-2">
                <div className="h-4 bg-muted rounded w-1/3" />
                <div className="h-6 bg-muted rounded w-1/2" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {error && (
        <Card className="border-destructive">
          <CardContent className="py-4">
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {!loading && !error && data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Competitors List */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Trophy className="h-5 w-5 text-yellow-500" />
                Топ конкуренти
              </CardTitle>
              <CardDescription>
                Компании со највеќе победени тендери
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {data.competitors?.length ? (
                data.competitors.map((row, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between border-b pb-3 last:border-0"
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-sm font-medium">
                        {idx + 1}
                      </div>
                      <div>
                        <p className="font-medium">{row.name || row.company_name || "Непознат"}</p>
                        <p className="text-xs text-muted-foreground">
                          Вкупна вредност: {(row.total_value_mkd || 0).toLocaleString()} МКД
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-green-600">{row.wins ?? 0} победи</p>
                      <p className="text-xs text-muted-foreground">
                        {row.bids_count ?? 0} понуди
                        {row.win_rate !== undefined && ` · ${row.win_rate}% успешност`}
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  Нема податоци за конкуренти.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5" />
                Резиме
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {data.summary ? (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Вкупно понудувачи</span>
                    <span className="font-bold text-lg">
                      {(data.summary.total_bidders || 0).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Вкупно понуди</span>
                    <span className="font-bold text-lg">
                      {(data.summary.total_bids || 0).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-muted-foreground">Вкупно доделени</span>
                    <span className="font-bold text-lg">
                      {(data.summary.total_awards || 0).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex justify-between items-center pt-2 border-t">
                    <span className="text-muted-foreground">Вкупна вредност</span>
                    <span className="font-bold text-lg text-green-600">
                      {((data.summary.total_awarded_value_mkd || 0) / 1_000_000).toFixed(1)}M МКД
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground pt-2">
                    Период: {data.summary.period === "1y" ? "Последна година" : data.summary.period}
                  </div>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Нема резиме.</p>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
