"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { api, type DashboardData, type CompetitorActivity } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Building2, TrendingUp, Trophy, Search, Calendar, X, CheckCircle, Loader2 } from "lucide-react";

interface Winner {
  company_name: string;
  total_wins: number;
  total_bids: number;
  total_contract_value: number | null;
}

interface CompetitorStats {
  name: string;
  totalActivity: number;
  wonCount: number;
  bidCount: number;
}

export default function CompetitorsPage() {
  const { user } = useAuth();
  const [isHydrated, setIsHydrated] = useState(false);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [winnersLoading, setWinnersLoading] = useState(false);
  const [filterName, setFilterName] = useState("");
  const [searchWinners, setSearchWinners] = useState("");
  const [trackedCompetitors, setTrackedCompetitors] = useState<string[]>([]);
  const [knownWinners, setKnownWinners] = useState<Winner[]>([]);
  const [savingPrefs, setSavingPrefs] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [user?.user_id]);

  // Debounced search for winners
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchWinners.length >= 2 || searchWinners.length === 0) {
        loadWinners(searchWinners);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchWinners]);

  async function loadInitialData() {
    if (!user?.user_id) return;

    try {
      setLoading(true);

      // Load all data in parallel
      const [dashboardResult, winnersResult, prefsResult] = await Promise.all([
        api.getPersonalizedDashboard(user.user_id).catch(() => null),
        api.getKnownWinners(undefined, 100),
        api.getPreferences(user.user_id).catch(() => null),
      ]);

      if (dashboardResult) setData(dashboardResult);
      setKnownWinners(winnersResult.winners);
      if (prefsResult) setTrackedCompetitors(prefsResult.competitor_companies || []);
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  }

  async function loadWinners(search?: string) {
    setWinnersLoading(true);
    try {
      const result = await api.getKnownWinners(search, 100);
      setKnownWinners(result.winners);
    } catch (error) {
      console.error("Failed to load winners:", error);
    } finally {
      setWinnersLoading(false);
    }
  }

  async function toggleCompetitor(companyName: string, isChecked: boolean) {
    if (!user?.user_id) return;

    setSavingPrefs(true);
    try {
      const updated = isChecked
        ? [...trackedCompetitors, companyName]
        : trackedCompetitors.filter((c) => c !== companyName);

      await api.savePreferences(user.user_id, { competitor_companies: updated });
      setTrackedCompetitors(updated);

      // Reload dashboard data to get updated competitor activity
      const dashboardResult = await api.getPersonalizedDashboard(user.user_id).catch(() => null);
      if (dashboardResult) setData(dashboardResult);
    } catch (error) {
      console.error("Failed to update competitor:", error);
    } finally {
      setSavingPrefs(false);
    }
  }

  const getCompetitorStats = (): CompetitorStats[] => {
    if (!data?.competitor_activity) return [];

    const statsMap = new Map<string, CompetitorStats>();

    data.competitor_activity.forEach((activity) => {
      if (!statsMap.has(activity.competitor_name)) {
        statsMap.set(activity.competitor_name, {
          name: activity.competitor_name,
          totalActivity: 0,
          wonCount: 0,
          bidCount: 0,
        });
      }

      const stats = statsMap.get(activity.competitor_name)!;
      stats.totalActivity++;

      if (activity.status === "won" || activity.status === "добиен") {
        stats.wonCount++;
      } else if (activity.status === "bid" || activity.status === "понуда") {
        stats.bidCount++;
      }
    });

    return Array.from(statsMap.values()).sort((a, b) => b.totalActivity - a.totalActivity);
  };

  const getFilteredActivities = (): CompetitorActivity[] => {
    if (!data?.competitor_activity) return [];

    return data.competitor_activity.filter(
      (activity) =>
        filterName === "" || activity.competitor_name.toLowerCase().includes(filterName.toLowerCase())
    );
  };

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === "won" || s === "добиен") {
      return <Badge className="bg-green-100 text-green-700 hover:bg-green-100">Добиен</Badge>;
    } else if (s === "bid" || s === "понуда") {
      return <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100">Понуда</Badge>;
    } else if (s === "lost" || s === "изгубен") {
      return <Badge className="bg-red-100 text-red-700 hover:bg-red-100">Изгубен</Badge>;
    }
    return <Badge variant="outline">{status}</Badge>;
  };

  const competitorStats = getCompetitorStats();
  const filteredActivities = getFilteredActivities();
  const totalCompetitors = trackedCompetitors.length;
  const activeTenders = filteredActivities.length;
  const wonThisMonth = filteredActivities.filter(
    (a) => a.status === "won" || a.status === "добиен"
  ).length;

  if (!isHydrated || loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2 text-muted-foreground">Се вчитува...</span>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Следење на Конкуренти</h1>
        <p className="text-muted-foreground">
          Изберете компании од листата на победници за да ги следите
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Building2 className="h-4 w-4 text-primary" />
              Следени Конкуренти
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCompetitors}</div>
            <p className="text-xs text-muted-foreground">Селектирани компании</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-blue-600" />
              Активни Тендери
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeTenders}</div>
            <p className="text-xs text-muted-foreground">Вкупни активности</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Trophy className="h-4 w-4 text-green-600" />
              Добиени
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{wonThisMonth}</div>
            <p className="text-xs text-muted-foreground">Успешни тендери</p>
          </CardContent>
        </Card>
      </div>

      {/* Winner Selection */}
      <Card>
        <CardHeader>
          <CardTitle>Изберете Конкуренти за Следење</CardTitle>
          <CardDescription>
            Листа на компании кои добиле тендери. Означете ги оние кои сакате да ги следите.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Пребарај компании..."
              value={searchWinners}
              onChange={(e) => setSearchWinners(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Selected competitors summary */}
          {trackedCompetitors.length > 0 && (
            <div className="flex flex-wrap gap-2 p-3 bg-primary/5 rounded-lg">
              <span className="text-sm text-muted-foreground mr-2">Следите:</span>
              {trackedCompetitors.map((name) => (
                <Badge
                  key={name}
                  variant="secondary"
                  className="cursor-pointer hover:bg-destructive/20"
                  onClick={() => toggleCompetitor(name, false)}
                >
                  {name}
                  <X className="h-3 w-3 ml-1" />
                </Badge>
              ))}
            </div>
          )}

          {/* Winners list */}
          <div className="max-h-[400px] overflow-y-auto space-y-2">
            {winnersLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : knownWinners.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Building2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="text-sm">Нема пронајдено компании.</p>
                <p className="text-xs mt-1">
                  Победниците ќе се појават по полната синхронизација на тендерски податоци.
                </p>
              </div>
            ) : (
              knownWinners.map((winner) => {
                const isTracked = trackedCompetitors.includes(winner.company_name);
                return (
                  <div
                    key={winner.company_name}
                    className={`flex items-center justify-between p-3 rounded-lg border transition-colors cursor-pointer ${
                      isTracked ? "bg-primary/10 border-primary/30" : "hover:bg-accent/50"
                    }`}
                    onClick={() => toggleCompetitor(winner.company_name, !isTracked)}
                  >
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                      <Checkbox
                        checked={isTracked}
                        disabled={savingPrefs}
                        className="pointer-events-none"
                      />
                      <div className="flex-1 min-w-0">
                        <h4 className="font-medium text-sm truncate">{winner.company_name}</h4>
                        <div className="flex gap-4 mt-1 text-xs text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Trophy className="h-3 w-3 text-green-600" />
                            {winner.total_wins} победи
                          </span>
                          <span className="flex items-center gap-1">
                            <TrendingUp className="h-3 w-3 text-blue-600" />
                            {winner.total_bids} понуди
                          </span>
                          {winner.total_contract_value && (
                            <span className="hidden sm:inline">
                              {formatCurrency(winner.total_contract_value)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    {isTracked && <CheckCircle className="h-5 w-5 text-primary shrink-0" />}
                  </div>
                );
              })
            )}
          </div>
        </CardContent>
      </Card>

      {/* Activity Timeline */}
      {trackedCompetitors.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Временска Линија на Активности</CardTitle>
            <CardDescription>Детален преглед на активности на следените конкуренти</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Филтрирај по име на конкурент..."
                  value={filterName}
                  onChange={(e) => setFilterName(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            <div className="space-y-3">
              {filteredActivities.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p className="text-sm">Нема пронајдено активности за следените конкуренти.</p>
                  <p className="text-xs mt-1">
                    Активностите ќе се појават откако ќе се синхронизираат тендерските податоци.
                  </p>
                </div>
              ) : (
                filteredActivities.map((activity, idx) => (
                  <div
                    key={idx}
                    className="flex items-start justify-between p-4 rounded-lg border hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex-1 space-y-2">
                      <div className="flex items-start justify-between gap-4">
                        <h4 className="font-medium">{activity.title}</h4>
                        {getStatusBadge(activity.status)}
                      </div>

                      <div className="flex items-center gap-2 text-sm">
                        <Building2 className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium text-primary">{activity.competitor_name}</span>
                      </div>

                      <div className="flex items-center gap-4 text-xs text-muted-foreground">
                        {activity.estimated_value_mkd && (
                          <span>{formatCurrency(activity.estimated_value_mkd)}</span>
                        )}
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          ID: {activity.tender_id}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
