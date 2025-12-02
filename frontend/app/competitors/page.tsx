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
  Loader2,
  Bot,
  Building2,
  Package,
  Send
} from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import Link from "next/link";
import { CompetitorCard } from "@/components/competitors/CompetitorCard";
import { CompetitorSearch } from "@/components/competitors/CompetitorSearch";
import ActivityFeed from "@/components/competitors/ActivityFeed";
import { CompetitorComparison, CompetitorStats } from "@/components/competitors/CompetitorComparison";
import HeadToHead from "@/components/competitors/HeadToHead";

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

interface CompanyAnalysis {
  company_name: string;
  summary: string;
  tender_stats: {
    total_bids: number;
    total_wins: number;
    win_rate: number;
    avg_bid_value_mkd?: number;
    total_won_value_mkd?: number;
    first_bid_date?: string;
    last_bid_date?: string;
  };
  recent_wins: Array<{
    tender_id: string;
    title: string;
    procuring_entity: string;
    category: string;
    cpv_code: string;
    contract_value_mkd?: number;
    date?: string;
  }>;
  common_categories: Array<{
    category: string;
    bid_count: number;
    win_count: number;
    won_value_mkd: number;
  }>;
  frequent_institutions: Array<{
    institution: string;
    bid_count: number;
    win_count: number;
    avg_bid_mkd?: number;
  }>;
  product_specifications: Array<{
    item_name: string;
    unit?: string;
    unit_price_mkd?: number;
    quantity?: number;
    tender_title?: string;
    institution?: string;
  }>;
  ai_insights: string;
  analysis_timestamp: string;
}

export default function CompetitorsPage() {
  const [data, setData] = useState<{ competitors: Competitor[]; summary: any } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tier, setTier] = useState<string | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Tracked competitors state
  const [trackedCompetitors, setTrackedCompetitors] = useState<string[]>([]);
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

  // AI Analysis state
  const [analysisCompany, setAnalysisCompany] = useState("");
  const [companyAnalysis, setCompanyAnalysis] = useState<CompanyAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Comparison state
  const [comparisonCompetitors, setComparisonCompetitors] = useState<CompetitorStats[]>([]);
  const [comparisonLoading, setComparisonLoading] = useState(false);

  useEffect(() => {
    setMounted(true);
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

      // Load comparison data for tracked competitors
      if (result.tracked_competitors?.length > 0) {
        loadComparisonData(result.tracked_competitors);
      }
    } catch (err) {
      console.error("Failed to load tracked competitors:", err);
    }
  }

  async function loadComparisonData(companies: string[]) {
    if (companies.length === 0) {
      setComparisonCompetitors([]);
      return;
    }

    try {
      setComparisonLoading(true);
      // Load stats for up to 6 competitors for comparison
      const statsPromises = companies.slice(0, 6).map(async (name) => {
        try {
          // Try to get stats from top competitors first
          const competitor = data?.competitors?.find(
            (c) => (c.name || c.company_name)?.toLowerCase() === name.toLowerCase()
          );

          if (competitor) {
            return {
              name: competitor.name || competitor.company_name || name,
              wins: competitor.wins || 0,
              bidsCount: competitor.bids_count || 0,
              winRate: competitor.win_rate || 0,
              totalValueMkd: competitor.total_value_mkd || 0,
              avgDiscount: undefined,
              specialtyAreas: [],
            };
          }

          // If not in top competitors, we'll use basic data
          return {
            name,
            wins: 0,
            bidsCount: 0,
            winRate: 0,
            totalValueMkd: 0,
            avgDiscount: undefined,
            specialtyAreas: [],
          };
        } catch (err) {
          console.error(`Failed to load stats for ${name}:`, err);
          return null;
        }
      });

      const stats = await Promise.all(statsPromises);
      const validStats = stats.filter((s) => s !== null) as CompetitorStats[];
      setComparisonCompetitors(validStats);
    } catch (err) {
      console.error("Failed to load comparison data:", err);
    } finally {
      setComparisonLoading(false);
    }
  }

  async function toggleTrack(companyName: string) {
    try {
      setTrackingLoading(companyName);
      const isTracked = trackedCompetitors.includes(companyName);

      if (isTracked) {
        const result = await api.removeTrackedCompetitor(companyName);
        setTrackedCompetitors(result.tracked_competitors || []);
        loadComparisonData(result.tracked_competitors || []);
      } else {
        const result = await api.addTrackedCompetitor(companyName);
        setTrackedCompetitors(result.tracked_competitors || []);
        // Reload comparison when adding a new competitor
        loadComparisonData(result.tracked_competitors || []);
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

  // Run AI company analysis
  async function runCompanyAnalysis(companyName?: string) {
    const targetCompany = companyName || analysisCompany;
    if (!targetCompany || targetCompany.length < 3) {
      setAnalysisError("Внесете име на компанија (минимум 3 карактери)");
      return;
    }

    try {
      setAnalysisLoading(true);
      setAnalysisError(null);
      setCompanyAnalysis(null);

      const result = await api.analyzeCompany(targetCompany);
      setCompanyAnalysis(result);
      setAnalysisCompany(targetCompany);
    } catch (err: any) {
      console.error("Company analysis failed:", err);
      setAnalysisError(err.message || "Анализата не успеа. Обидете се повторно.");
    } finally {
      setAnalysisLoading(false);
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

      {/* Search Bar - Using new component */}
      <CompetitorSearch
        onSearch={async (query) => {
          const result = await api.getKnownWinners(query, 10);
          return result.winners || [];
        }}
        onAddCompetitor={toggleTrack}
        trackedCompetitors={trackedCompetitors}
        isTrackingLoading={trackingLoading}
      />

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
          <TabsTrigger value="comparison" className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4" />
            Споредба
          </TabsTrigger>
          <TabsTrigger value="activity" className="flex items-center gap-2">
            <Activity className="h-4 w-4" />
            Активност
          </TabsTrigger>
          <TabsTrigger value="ai-analysis" className="flex items-center gap-2">
            <Bot className="h-4 w-4" />
            AI Анализа
          </TabsTrigger>
          <TabsTrigger value="head-to-head" className="flex items-center gap-2">
            <Users className="h-4 w-4" />
            Head-to-Head
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
                                <Link
                                  href={`/competitors/${encodeURIComponent(companyName)}`}
                                  className="font-medium hover:text-primary hover:underline transition-colors"
                                >
                                  {companyName}
                                </Link>
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

        {/* Comparison Tab */}
        <TabsContent value="comparison" className="space-y-4">
          {comparisonLoading ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4" />
                <p className="text-sm text-muted-foreground">Се вчитува споредба...</p>
              </CardContent>
            </Card>
          ) : (
            <CompetitorComparison
              competitors={comparisonCompetitors}
              onRemoveCompetitor={(name) => toggleTrack(name)}
            />
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
                        <Link
                          href={`/competitors/${encodeURIComponent(name)}`}
                          className="font-medium hover:text-primary hover:underline transition-colors"
                        >
                          {name}
                        </Link>
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
          <ActivityFeed companyNames={trackedCompetitors} limit={50} />
        </TabsContent>

        {/* AI Analysis Tab */}
        <TabsContent value="ai-analysis" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-purple-500" />
                AI Анализа на компанија
              </CardTitle>
              <CardDescription>
                Добијте детална AI-генерирана анализа за било која компанија
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Search Input */}
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Внесете име на компанија за анализа..."
                    className="pl-9"
                    value={analysisCompany}
                    onChange={(e) => setAnalysisCompany(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && runCompanyAnalysis()}
                  />
                </div>
                <Button
                  onClick={() => runCompanyAnalysis()}
                  disabled={analysisLoading || analysisCompany.length < 3}
                >
                  {analysisLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                  ) : (
                    <Send className="h-4 w-4 mr-2" />
                  )}
                  Анализирај
                </Button>
              </div>

              {/* Quick Access - Tracked Companies */}
              {trackedCompetitors.length > 0 && !companyAnalysis && (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Брз пристап до следени компании:</p>
                  <div className="flex flex-wrap gap-2">
                    {trackedCompetitors.slice(0, 5).map((name) => (
                      <Button
                        key={name}
                        variant="outline"
                        size="sm"
                        onClick={() => runCompanyAnalysis(name)}
                        disabled={analysisLoading}
                      >
                        <Star className="h-3 w-3 mr-1 fill-yellow-500 text-yellow-500" />
                        {name}
                      </Button>
                    ))}
                  </div>
                </div>
              )}

              {/* Error Display */}
              {analysisError && (
                <Card className="border-destructive bg-destructive/10">
                  <CardContent className="py-3 flex items-center gap-2">
                    <Activity className="h-4 w-4 text-destructive" />
                    <p className="text-sm text-destructive">{analysisError}</p>
                  </CardContent>
                </Card>
              )}

              {/* Loading State */}
              {analysisLoading && (
                <Card className="border-purple-200 bg-purple-50 dark:bg-purple-900/20">
                  <CardContent className="py-8 text-center">
                    <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-purple-500" />
                    <p className="text-sm text-muted-foreground">AI ја анализира компанијата...</p>
                    <p className="text-xs text-muted-foreground mt-1">Ова може да потрае неколку секунди</p>
                  </CardContent>
                </Card>
              )}

              {/* Analysis Results */}
              {companyAnalysis && !analysisLoading && (
                <div className="space-y-6">
                  {/* Company Header */}
                  <div className="flex items-center justify-between border-b pb-4">
                    <div>
                      <h3 className="text-xl font-bold">{companyAnalysis.company_name}</h3>
                      {mounted && companyAnalysis.analysis_timestamp && (
                        <p className="text-sm text-muted-foreground">
                          Анализирано на: {new Date(companyAnalysis.analysis_timestamp).toLocaleString('mk-MK')}
                        </p>
                      )}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleTrack(companyAnalysis.company_name)}
                      disabled={trackingLoading === companyAnalysis.company_name}
                    >
                      {isTracked(companyAnalysis.company_name) ? (
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

                  {/* AI Summary */}
                  <Card className="bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 border-purple-200">
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Bot className="h-4 w-4 text-purple-500" />
                        AI Резиме
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm leading-relaxed">{companyAnalysis.summary}</p>
                    </CardContent>
                  </Card>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <Card>
                      <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold text-blue-600">{companyAnalysis.tender_stats.total_bids}</p>
                        <p className="text-xs text-muted-foreground">Вкупно понуди</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold text-green-600">{companyAnalysis.tender_stats.total_wins}</p>
                        <p className="text-xs text-muted-foreground">Победи</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold text-purple-600">{companyAnalysis.tender_stats.win_rate}%</p>
                        <p className="text-xs text-muted-foreground">Успешност</p>
                      </CardContent>
                    </Card>
                    <Card>
                      <CardContent className="pt-4 text-center">
                        <p className="text-2xl font-bold text-orange-600">
                          {companyAnalysis.tender_stats.total_won_value_mkd
                            ? `${(companyAnalysis.tender_stats.total_won_value_mkd / 1_000_000).toFixed(1)}M`
                            : '-'}
                        </p>
                        <p className="text-xs text-muted-foreground">Вкупна вредност МКД</p>
                      </CardContent>
                    </Card>
                  </div>

                  {/* AI Insights */}
                  {companyAnalysis.ai_insights && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                          <TrendingUp className="h-4 w-4 text-green-500" />
                          AI Инсајти
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="text-sm whitespace-pre-wrap">{companyAnalysis.ai_insights}</p>
                      </CardContent>
                    </Card>
                  )}

                  {/* Common Categories */}
                  {companyAnalysis.common_categories?.length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                          <Package className="h-4 w-4" />
                          Најчести категории
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {companyAnalysis.common_categories.slice(0, 5).map((cat, idx) => (
                            <div key={idx} className="flex items-center justify-between text-sm">
                              <span className="truncate flex-1">{cat.category}</span>
                              <div className="flex items-center gap-4 text-muted-foreground">
                                <span>{cat.bid_count} понуди</span>
                                <span className="text-green-600">{cat.win_count} победи</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Frequent Institutions */}
                  {companyAnalysis.frequent_institutions?.length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                          <Building2 className="h-4 w-4" />
                          Најчести институции
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2">
                          {companyAnalysis.frequent_institutions.slice(0, 5).map((inst, idx) => (
                            <div key={idx} className="flex items-center justify-between text-sm">
                              <span className="truncate flex-1">{inst.institution}</span>
                              <div className="flex items-center gap-4 text-muted-foreground">
                                <span>{inst.bid_count} понуди</span>
                                <span className="text-green-600">{inst.win_count} победи</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Recent Wins */}
                  {companyAnalysis.recent_wins?.length > 0 && (
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base flex items-center gap-2">
                          <Trophy className="h-4 w-4 text-yellow-500" />
                          Последни победи
                        </CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-3">
                          {companyAnalysis.recent_wins.slice(0, 5).map((win, idx) => (
                            <Link
                              key={idx}
                              href={`/tenders/${encodeURIComponent(win.tender_id)}`}
                              className="block p-3 border rounded-lg hover:bg-accent transition-colors"
                            >
                              <p className="font-medium text-sm line-clamp-1">{win.title}</p>
                              <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                                <span>{win.procuring_entity}</span>
                                {win.contract_value_mkd && (
                                  <>
                                    <span>·</span>
                                    <span className="text-green-600">
                                      {win.contract_value_mkd.toLocaleString()} МКД
                                    </span>
                                  </>
                                )}
                              </div>
                            </Link>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}

              {/* Empty State */}
              {!companyAnalysis && !analysisLoading && !analysisError && (
                <div className="text-center py-12 text-muted-foreground">
                  <Bot className="h-16 w-16 mx-auto mb-4 opacity-30" />
                  <p className="text-lg font-medium mb-2">Анализирајте било која компанија</p>
                  <p className="text-sm max-w-md mx-auto">
                    Внесете име на компанија погоре за да добиете детална AI-генерирана анализа
                    на нивната активност во јавните набавки
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Head-to-Head Tab */}
        <TabsContent value="head-to-head" className="space-y-4">
          <HeadToHead />
        </TabsContent>
      </Tabs>
    </div>
  );
}
