"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  RefreshCcw,
  Lock,
  Trophy,
  Users,
  TrendingUp,
  DollarSign,
  Star,
  StarOff,
  Bell,
  Activity,
  Eye,
  CheckCircle,
  ArrowRight,
  Search,
  Plus,
  Loader2
} from "lucide-react";
import Link from "next/link";

interface Competitor {
  name?: string;
  company_name?: string;
  wins?: number;
  bids_count?: number;
  win_rate?: number;
  total_value_mkd?: number;
}

interface CompetitorActivity {
  tender_id: string;
  title: string;
  competitor_name: string;
  status: string;
  estimated_value_mkd?: number;
  closing_date?: string;
  bid_amount_mkd?: number;
  is_winner?: boolean;
  rank?: number;
  activity_type: "win" | "bid";
}

export default function CompetitorsPage() {
  const [data, setData] = useState<{ competitors: Competitor[]; summary: any } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tier, setTier] = useState<string | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  // Tracked competitors state
  const [trackedCompetitors, setTrackedCompetitors] = useState<string[]>([]);
  const [trackedActivity, setTrackedActivity] = useState<CompetitorActivity[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [trackingLoading, setTrackingLoading] = useState<string | null>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Array<{
    company_name: string;
    total_wins: number;
    total_bids: number;
    total_contract_value: number | null;
  }>>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);

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
        loadTrackedCompetitors();
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

  async function loadTrackedCompetitors() {
    try {
      const result = await api.getTrackedCompetitors();
      setTrackedCompetitors(result.tracked_competitors || []);

      // Load activity for tracked competitors
      if (result.tracked_competitors?.length > 0) {
        loadTrackedActivity();
      }
    } catch (err) {
      console.error("Failed to load tracked competitors:", err);
    }
  }

  async function loadTrackedActivity() {
    try {
      setActivityLoading(true);
      const result = await api.getTrackedCompetitorActivity(20);
      setTrackedActivity(result.activities || []);
    } catch (err) {
      console.error("Failed to load tracked activity:", err);
    } finally {
      setActivityLoading(false);
    }
  }

  async function toggleTrack(companyName: string) {
    try {
      setTrackingLoading(companyName);
      const isTracked = trackedCompetitors.includes(companyName);

      if (isTracked) {
        const result = await api.removeTrackedCompetitor(companyName);
        setTrackedCompetitors(result.tracked_competitors || []);
      } else {
        const result = await api.addTrackedCompetitor(companyName);
        setTrackedCompetitors(result.tracked_competitors || []);
        // Reload activity when adding a new competitor
        loadTrackedActivity();
      }
    } catch (err) {
      console.error("Failed to toggle tracking:", err);
    } finally {
      setTrackingLoading(null);
    }
  }

  function isTracked(companyName: string): boolean {
    return trackedCompetitors.some(
      (c) => c.toLowerCase() === companyName.toLowerCase()
    );
  }

  // Search for companies
  async function searchCompanies(query: string) {
    if (query.length < 2) {
      setSearchResults([]);
      setShowSearchResults(false);
      return;
    }

    try {
      setSearchLoading(true);
      const result = await api.getKnownWinners(query, 10);
      setSearchResults(result.winners || []);
      setShowSearchResults(true);
    } catch (err) {
      console.error("Failed to search companies:", err);
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery) {
        searchCompanies(searchQuery);
      } else {
        setSearchResults([]);
        setShowSearchResults(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

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
                <Bell className="h-6 w-6 text-blue-500 mb-2" />
                <CardTitle className="text-base">Следење на компании</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Изберете компании за следење и добивајте известувања за нивна активност
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <Activity className="h-6 w-6 text-green-500 mb-2" />
                <CardTitle className="text-base">Активност на конкуренти</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  Видете ги најновите понуди и победи на следените компании
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
            Следете ги топ компаниите и нивната активност
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={load} disabled={loading}>
          <RefreshCcw className="h-4 w-4 mr-2" />
          Освежи
        </Button>
      </div>

      {/* Search Bar - Always visible at top */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Search className="h-4 w-4" />
            Пребарај компании
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Внесете име на компанија за пребарување..."
                className="pl-9"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onFocus={() => searchQuery.length >= 2 && setShowSearchResults(true)}
                onBlur={() => setTimeout(() => setShowSearchResults(false), 200)}
              />
              {searchLoading && (
                <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </div>

            {/* Search Results Dropdown */}
            {showSearchResults && searchResults.length > 0 && (
              <div className="absolute z-50 w-full mt-1 max-h-64 overflow-auto border rounded-md bg-background shadow-lg">
                {searchResults.map((result) => {
                  const tracked = isTracked(result.company_name);
                  return (
                    <div
                      key={result.company_name}
                      className="flex items-center justify-between px-3 py-2 hover:bg-accent border-b last:border-0"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm truncate">{result.company_name}</p>
                        <p className="text-xs text-muted-foreground">
                          {result.total_wins} победи · {result.total_bids} понуди
                          {result.total_contract_value && ` · ${(result.total_contract_value / 1_000_000).toFixed(1)}M МКД`}
                        </p>
                      </div>
                      <Button
                        variant={tracked ? "secondary" : "default"}
                        size="sm"
                        className="ml-2 flex-shrink-0"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          toggleTrack(result.company_name);
                        }}
                        disabled={trackingLoading === result.company_name}
                      >
                        {trackingLoading === result.company_name ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : tracked ? (
                          <>
                            <Star className="h-4 w-4 mr-1 fill-yellow-500 text-yellow-500" />
                            Следена
                          </>
                        ) : (
                          <>
                            <Plus className="h-4 w-4 mr-1" />
                            Следи
                          </>
                        )}
                      </Button>
                    </div>
                  );
                })}
              </div>
            )}

            {showSearchResults && searchQuery.length >= 2 && searchResults.length === 0 && !searchLoading && (
              <div className="absolute z-50 w-full mt-1 border rounded-md bg-background shadow-lg p-4 text-center text-sm text-muted-foreground">
                Нема резултати за „{searchQuery}"
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tabs for Top Competitors and Tracked Activity */}
      <Tabs defaultValue="top" className="space-y-4">
        <TabsList>
          <TabsTrigger value="top" className="flex items-center gap-2">
            <Trophy className="h-4 w-4" />
            Топ конкуренти
          </TabsTrigger>
          <TabsTrigger value="tracked" className="flex items-center gap-2">
            <Star className="h-4 w-4" />
            Следени ({trackedCompetitors.length})
          </TabsTrigger>
          <TabsTrigger value="activity" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Активност
          </TabsTrigger>
        </TabsList>

        {/* Top Competitors Tab */}
        <TabsContent value="top" className="space-y-4">
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
                    Кликнете на ѕвездата за да следите компанија
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {data.competitors?.length ? (
                    data.competitors.map((row, idx) => {
                      const companyName = row.name || row.company_name || "Непознат";
                      const tracked = isTracked(companyName);

                      return (
                        <div
                          key={idx}
                          className="flex items-center justify-between border-b pb-3 last:border-0"
                        >
                          <div className="flex items-center gap-3">
                            <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-sm font-medium">
                              {idx + 1}
                            </div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <p className="font-medium">{companyName}</p>
                                {tracked && (
                                  <Badge variant="secondary" className="text-xs">
                                    <Star className="h-3 w-3 mr-1 fill-yellow-500 text-yellow-500" />
                                    Следена
                                  </Badge>
                                )}
                              </div>
                              <p className="text-xs text-muted-foreground">
                                Вкупна вредност: {(row.total_value_mkd || 0).toLocaleString()} МКД
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-3">
                            <div className="text-right">
                              <p className="font-semibold text-green-600">{row.wins ?? 0} победи</p>
                              <p className="text-xs text-muted-foreground">
                                {row.bids_count ?? 0} понуди
                                {row.win_rate !== undefined && ` · ${row.win_rate}% успешност`}
                              </p>
                            </div>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => toggleTrack(companyName)}
                              disabled={trackingLoading === companyName}
                              title={tracked ? "Отстрани од следење" : "Следи компанија"}
                            >
                              {trackingLoading === companyName ? (
                                <RefreshCcw className="h-4 w-4 animate-spin" />
                              ) : tracked ? (
                                <Star className="h-5 w-5 fill-yellow-500 text-yellow-500" />
                              ) : (
                                <StarOff className="h-5 w-5 text-muted-foreground" />
                              )}
                            </Button>
                          </div>
                        </div>
                      );
                    })
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
        </TabsContent>

        {/* Tracked Competitors Tab */}
        <TabsContent value="tracked" className="space-y-4">
          {/* Tracked Companies List */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Star className="h-5 w-5 text-yellow-500" />
                Следени компании ({trackedCompetitors.length})
              </CardTitle>
              <CardDescription>
                Компании кои ги следите за известувања
              </CardDescription>
            </CardHeader>
            <CardContent>
              {trackedCompetitors.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <StarOff className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="mb-2">Немате следени компании</p>
                  <p className="text-sm">
                    Користете го полето за пребарување погоре или кликнете на ѕвездата кај топ конкурентите
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {trackedCompetitors.map((name) => (
                    <div
                      key={name}
                      className="flex items-center justify-between p-3 border rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <Star className="h-5 w-5 fill-yellow-500 text-yellow-500" />
                        <span className="font-medium">{name}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleTrack(name)}
                        disabled={trackingLoading === name}
                        className="text-destructive hover:text-destructive"
                      >
                        {trackingLoading === name ? (
                          <RefreshCcw className="h-4 w-4 animate-spin" />
                        ) : (
                          "Отстрани"
                        )}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Activity Tab */}
        <TabsContent value="activity" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Activity className="h-5 w-5 text-green-500" />
                    Активност на следени компании
                  </CardTitle>
                  <CardDescription>
                    Најнови понуди и победи од компании кои ги следите
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={loadTrackedActivity}
                  disabled={activityLoading}
                >
                  <RefreshCcw className={`h-4 w-4 mr-2 ${activityLoading ? "animate-spin" : ""}`} />
                  Освежи
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {trackedCompetitors.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="mb-2">Немате следени компании</p>
                  <p className="text-sm">
                    Додадете компании за следење за да ја видите нивната активност
                  </p>
                </div>
              ) : activityLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="animate-pulse border-b pb-3 last:border-0">
                      <div className="h-4 bg-muted rounded w-3/4 mb-2" />
                      <div className="h-3 bg-muted rounded w-1/2" />
                    </div>
                  ))}
                </div>
              ) : trackedActivity.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <Activity className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Нема скорешна активност за следените компании</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {trackedActivity.map((activity, idx) => (
                    <div
                      key={`${activity.tender_id}-${activity.competitor_name}-${idx}`}
                      className="flex items-start gap-3 border-b pb-4 last:border-0"
                    >
                      <div className="flex-shrink-0 mt-1">
                        {activity.activity_type === "win" || activity.is_winner ? (
                          <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-full">
                            <CheckCircle className="h-4 w-4 text-green-600" />
                          </div>
                        ) : (
                          <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-full">
                            <Eye className="h-4 w-4 text-blue-600" />
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-medium text-sm">{activity.competitor_name}</span>
                          <Badge
                            variant={activity.activity_type === "win" || activity.is_winner ? "default" : "secondary"}
                            className="text-xs"
                          >
                            {activity.activity_type === "win" || activity.is_winner ? "Победа" : "Понуда"}
                          </Badge>
                          {activity.rank && activity.rank > 1 && (
                            <Badge variant="outline" className="text-xs">
                              #{activity.rank} место
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground line-clamp-2 mb-1">
                          {activity.title}
                        </p>
                        <div className="flex items-center gap-4 text-xs text-muted-foreground">
                          {activity.bid_amount_mkd && (
                            <span className="flex items-center gap-1">
                              <DollarSign className="h-3 w-3" />
                              {activity.bid_amount_mkd.toLocaleString()} МКД
                            </span>
                          )}
                          {activity.estimated_value_mkd && !activity.bid_amount_mkd && (
                            <span className="flex items-center gap-1">
                              <DollarSign className="h-3 w-3" />
                              ~{activity.estimated_value_mkd.toLocaleString()} МКД
                            </span>
                          )}
                          <Badge variant="outline" className="text-xs">
                            {activity.status}
                          </Badge>
                        </div>
                      </div>
                      <Link href={`/tenders/${encodeURIComponent(activity.tender_id)}`}>
                        <Button variant="ghost" size="icon" className="flex-shrink-0">
                          <ArrowRight className="h-4 w-4" />
                        </Button>
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
