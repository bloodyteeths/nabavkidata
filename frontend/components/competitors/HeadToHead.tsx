"use client";

import { useState } from "react";
import { api, HeadToHeadResponse } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Swords, Trophy, TrendingDown, TrendingUp, Minus, AlertCircle } from "lucide-react";
import Link from "next/link";

interface HeadToHeadProps {
  initialCompanyA?: string;
  initialCompanyB?: string;
}

export default function HeadToHead({ initialCompanyA, initialCompanyB }: HeadToHeadProps) {
  const [companyA, setCompanyA] = useState(initialCompanyA || "");
  const [companyB, setCompanyB] = useState(initialCompanyB || "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<HeadToHeadResponse | null>(null);

  async function runComparison() {
    if (!companyA.trim() || !companyB.trim()) {
      setError("Внесете имиња на двете компании");
      return;
    }

    if (companyA.trim().toLowerCase() === companyB.trim().toLowerCase()) {
      setError("Изберете различни компании");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const result = await api.getHeadToHead(companyA.trim(), companyB.trim(), 20);
      setData(result);
    } catch (err: any) {
      console.error("Head-to-head comparison failed:", err);
      setError(err.message || "Компарацијата не успеа. Обидете се повторно.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  function getWinnerColor(winner: string): string {
    if (!data) return "text-muted-foreground";
    if (winner === data.company_a) return "text-blue-600 dark:text-blue-400";
    if (winner === data.company_b) return "text-green-600 dark:text-green-400";
    return "text-muted-foreground";
  }

  function getCompanyWinRate(wins: number, total: number): number {
    return total > 0 ? (wins / total) * 100 : 0;
  }

  function formatMKD(value: number | null | undefined): string {
    if (value === null || value === undefined) return "N/A";
    return new Intl.NumberFormat("mk-MK").format(value) + " МКД";
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "N/A";
    try {
      return new Date(dateStr).toLocaleDateString("mk-MK");
    } catch {
      return "N/A";
    }
  }

  return (
    <div className="space-y-6">
      {/* Input Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Swords className="h-5 w-5" />
            Head-to-Head Компарација
          </CardTitle>
          <CardDescription>
            Споредете две компании и видете ги нивните директни конфронтации
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="companyA">Компанија А</Label>
              <Input
                id="companyA"
                placeholder="Внесете име на прва компанија..."
                value={companyA}
                onChange={(e) => setCompanyA(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runComparison()}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="companyB">Компанија Б</Label>
              <Input
                id="companyB"
                placeholder="Внесете име на втора компанија..."
                value={companyB}
                onChange={(e) => setCompanyB(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && runComparison()}
              />
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 p-3 bg-destructive/10 border border-destructive rounded-md">
              <AlertCircle className="h-4 w-4 text-destructive" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          <Button
            onClick={runComparison}
            disabled={loading || !companyA.trim() || !companyB.trim()}
            className="w-full"
          >
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Анализирам...
              </>
            ) : (
              <>
                <Swords className="h-4 w-4 mr-2" />
                Компарирај
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Loading State */}
      {loading && (
        <Card className="border-purple-200 bg-purple-50 dark:bg-purple-900/20">
          <CardContent className="py-12 text-center">
            <Loader2 className="h-12 w-12 animate-spin mx-auto mb-4 text-purple-500" />
            <p className="text-sm text-muted-foreground">Анализирам директни конфронтации...</p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {!loading && data && (
        <>
          {/* Overview Stats */}
          <Card>
            <CardHeader>
              <CardTitle className="text-center">
                {data.company_a} vs {data.company_b}
              </CardTitle>
              <CardDescription className="text-center">
                Тендери каде обајцата понудија: {data.total_confrontations}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.total_confrontations === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <AlertCircle className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="mb-2">Нема директни конфронтации</p>
                  <p className="text-sm">
                    Овие компании не се натпревариле на истите тендери
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Win/Loss Bars */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Company A */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-blue-600 dark:text-blue-400">
                          {data.company_a}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          {getCompanyWinRate(data.company_a_wins, data.total_confrontations).toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-12 bg-muted rounded-lg overflow-hidden relative">
                        <div
                          className="h-full bg-blue-500 dark:bg-blue-600 flex items-center justify-center text-white font-bold transition-all"
                          style={{
                            width: `${getCompanyWinRate(data.company_a_wins, data.total_confrontations)}%`,
                          }}
                        >
                          {data.company_a_wins > 0 && <span>{data.company_a_wins} победи</span>}
                        </div>
                      </div>
                    </div>

                    {/* Company B */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-green-600 dark:text-green-400">
                          {data.company_b}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          {getCompanyWinRate(data.company_b_wins, data.total_confrontations).toFixed(1)}%
                        </span>
                      </div>
                      <div className="h-12 bg-muted rounded-lg overflow-hidden relative">
                        <div
                          className="h-full bg-green-500 dark:bg-green-600 flex items-center justify-center text-white font-bold transition-all"
                          style={{
                            width: `${getCompanyWinRate(data.company_b_wins, data.total_confrontations)}%`,
                          }}
                        >
                          {data.company_b_wins > 0 && <span>{data.company_b_wins} победи</span>}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Ties */}
                  {data.ties > 0 && (
                    <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                      <Minus className="h-4 w-4" />
                      <span>{data.ties} нерешени (обајцата победиле)</span>
                    </div>
                  )}

                  {/* Bid Difference */}
                  {data.avg_bid_difference !== null && data.avg_bid_difference !== undefined && (
                    <div className="pt-4 border-t">
                      <div className="flex items-center justify-center gap-2">
                        {data.avg_bid_difference > 0 ? (
                          <>
                            <TrendingDown className="h-5 w-5 text-blue-600" />
                            <span className="text-sm">
                              <span className="font-semibold text-blue-600">{data.company_a}</span> понудува{" "}
                              <span className="font-bold">{formatMKD(Math.abs(data.avg_bid_difference))}</span> пониско
                              во просек
                            </span>
                          </>
                        ) : data.avg_bid_difference < 0 ? (
                          <>
                            <TrendingDown className="h-5 w-5 text-green-600" />
                            <span className="text-sm">
                              <span className="font-semibold text-green-600">{data.company_b}</span> понудува{" "}
                              <span className="font-bold">{formatMKD(Math.abs(data.avg_bid_difference))}</span> пониско
                              во просек
                            </span>
                          </>
                        ) : (
                          <>
                            <Minus className="h-5 w-5 text-muted-foreground" />
                            <span className="text-sm">Двете компании имаат слични цени</span>
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* AI Insights */}
          {data.ai_insights && (
            <Card className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 border-purple-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <Trophy className="h-4 w-4 text-purple-500" />
                  AI Инсајти
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed">{data.ai_insights}</p>
              </CardContent>
            </Card>
          )}

          {/* Category Dominance */}
          {(data.company_a_categories.length > 0 || data.company_b_categories.length > 0) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Доминација по категории</CardTitle>
                <CardDescription>
                  Категории каде една компанија има предност
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Company A Categories */}
                  <div className="space-y-2">
                    <h4 className="font-semibold text-sm text-blue-600 dark:text-blue-400">
                      {data.company_a}
                    </h4>
                    {data.company_a_categories.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Нема доминантни категории</p>
                    ) : (
                      <div className="space-y-2">
                        {data.company_a_categories.map((cat, idx) => (
                          <div key={idx} className="p-2 border rounded-md bg-blue-50 dark:bg-blue-900/20">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-medium">{cat.category}</span>
                              <Badge variant="secondary" className="text-xs">
                                {cat.win_rate.toFixed(0)}%
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {cat.win_count}/{cat.total_count} победи
                              {cat.cpv_code && ` • ${cat.cpv_code}`}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Company B Categories */}
                  <div className="space-y-2">
                    <h4 className="font-semibold text-sm text-green-600 dark:text-green-400">
                      {data.company_b}
                    </h4>
                    {data.company_b_categories.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Нема доминантни категории</p>
                    ) : (
                      <div className="space-y-2">
                        {data.company_b_categories.map((cat, idx) => (
                          <div key={idx} className="p-2 border rounded-md bg-green-50 dark:bg-green-900/20">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-sm font-medium">{cat.category}</span>
                              <Badge variant="secondary" className="text-xs">
                                {cat.win_rate.toFixed(0)}%
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground">
                              {cat.win_count}/{cat.total_count} победи
                              {cat.cpv_code && ` • ${cat.cpv_code}`}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Recent Confrontations */}
          {data.recent_confrontations.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Последни конфронтации</CardTitle>
                <CardDescription>
                  Најнови тендери каде обајцата понудија
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {data.recent_confrontations.map((conf, idx) => (
                    <Link
                      key={idx}
                      href={`/tenders/${encodeURIComponent(conf.tender_id)}`}
                      className="block p-3 border rounded-lg hover:bg-accent transition-colors"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm line-clamp-2 mb-1">{conf.title}</p>
                          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                            {conf.date && <span>{formatDate(conf.date)}</span>}
                            {conf.estimated_value && (
                              <>
                                <span>•</span>
                                <span>{formatMKD(conf.estimated_value)}</span>
                              </>
                            )}
                            {conf.num_bidders && (
                              <>
                                <span>•</span>
                                <span>{conf.num_bidders} понудувачи</span>
                              </>
                            )}
                          </div>
                        </div>
                        <div className="flex-shrink-0 text-right space-y-1">
                          <Badge variant={conf.winner === data.company_a ? "default" : conf.winner === data.company_b ? "secondary" : "outline"}>
                            <Trophy className="h-3 w-3 mr-1" />
                            {conf.winner}
                          </Badge>
                          <div className="text-xs space-y-0.5">
                            {conf.company_a_bid !== null && (
                              <div className={conf.winner === data.company_a ? "text-blue-600 font-semibold" : "text-muted-foreground"}>
                                А: {formatMKD(conf.company_a_bid)}
                              </div>
                            )}
                            {conf.company_b_bid !== null && (
                              <div className={conf.winner === data.company_b ? "text-green-600 font-semibold" : "text-muted-foreground"}>
                                Б: {formatMKD(conf.company_b_bid)}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Empty State */}
      {!loading && !data && !error && (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <Swords className="h-16 w-16 mx-auto mb-4 opacity-30" />
            <p className="text-lg font-medium mb-2">Споредете два конкуренти</p>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              Внесете имиња на две компании погоре за да видите детална анализа на нивните директни
              конфронтации во тендери
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
