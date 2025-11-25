"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, type DashboardData, type CompetitorActivity } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { useAuth } from "@/lib/auth";
import { Building2, TrendingUp, Trophy, Plus, X, Search, Calendar } from "lucide-react";

interface CompetitorStats {
  name: string;
  totalActivity: number;
  wonCount: number;
  bidCount: number;
}

export default function CompetitorsPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterName, setFilterName] = useState("");
  const [newCompetitor, setNewCompetitor] = useState("");
  const [trackedCompetitors, setTrackedCompetitors] = useState<string[]>([]);

  useEffect(() => {
    if (user?.user_id) {
      loadData();
    }
  }, [user?.user_id]);

  async function loadData() {
    if (!user?.user_id) return;

    try {
      const result = await api.getPersonalizedDashboard(user.user_id);
      setData(result);

      const prefs = await api.getPreferences(user.user_id);
      setTrackedCompetitors(prefs.competitor_companies || []);
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  }

  async function addCompetitor() {
    if (!newCompetitor.trim() || !user?.user_id) return;

    try {
      const updated = [...trackedCompetitors, newCompetitor.trim()];
      await api.updatePreferences(user.user_id, { competitor_companies: updated });
      setTrackedCompetitors(updated);
      setNewCompetitor("");
    } catch (error) {
      console.error("Failed to add competitor:", error);
    }
  }

  async function removeCompetitor(name: string) {
    if (!user?.user_id) return;

    try {
      const updated = trackedCompetitors.filter(c => c !== name);
      await api.updatePreferences(user.user_id, { competitor_companies: updated });
      setTrackedCompetitors(updated);
    } catch (error) {
      console.error("Failed to remove competitor:", error);
    }
  }

  const getCompetitorStats = (): CompetitorStats[] => {
    if (!data?.competitor_activity) return [];

    const statsMap = new Map<string, CompetitorStats>();

    data.competitor_activity.forEach(activity => {
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

      if (activity.status === 'won' || activity.status === 'добиен') {
        stats.wonCount++;
      } else if (activity.status === 'bid' || activity.status === 'понуда') {
        stats.bidCount++;
      }
    });

    return Array.from(statsMap.values()).sort((a, b) => b.totalActivity - a.totalActivity);
  };

  const getFilteredActivities = (): CompetitorActivity[] => {
    if (!data?.competitor_activity) return [];

    return data.competitor_activity.filter(activity =>
      filterName === "" || activity.competitor_name.toLowerCase().includes(filterName.toLowerCase())
    );
  };

  const getWonThisMonth = (): number => {
    if (!data?.competitor_activity) return 0;
    return data.competitor_activity.filter(a =>
      a.status === 'won' || a.status === 'добиен'
    ).length;
  };

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'won' || s === 'добиен') {
      return <Badge className="bg-green-100 text-green-700 hover:bg-green-100">Добиен</Badge>;
    } else if (s === 'bid' || s === 'понуда') {
      return <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-100">Понуда</Badge>;
    } else if (s === 'lost' || s === 'изгубен') {
      return <Badge className="bg-red-100 text-red-700 hover:bg-red-100">Изгубен</Badge>;
    }
    return <Badge variant="outline">{status}</Badge>;
  };

  const competitorStats = getCompetitorStats();
  const filteredActivities = getFilteredActivities();
  const totalCompetitors = competitorStats.length;
  const activeTenders = filteredActivities.length;
  const wonThisMonth = getWonThisMonth();

  if (loading) return <div className="flex items-center justify-center h-full"><p className="text-muted-foreground">Се вчитува...</p></div>;

  return (
    <div className="p-8 space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Следење на Конкуренти</h1>
        <p className="text-muted-foreground">Анализа на активности и успеси на вашите конкуренти</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Building2 className="h-4 w-4 text-primary" />
              Вкупно Конкуренти
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalCompetitors}</div>
            <p className="text-xs text-muted-foreground">Следени компании</p>
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
              Добиени Овој Месец
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{wonThisMonth}</div>
            <p className="text-xs text-muted-foreground">Успешни тендери</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Следени Конкуренти</CardTitle>
          <CardDescription>Управувајте со листата на конкуренти што ги следите</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <Input
              placeholder="Внесете име на конкурент..."
              value={newCompetitor}
              onChange={(e) => setNewCompetitor(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addCompetitor()}
            />
            <Button onClick={addCompetitor} className="shrink-0">
              <Plus className="h-4 w-4 mr-2" />
              Додади
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {competitorStats.map((competitor) => (
              <div
                key={competitor.name}
                className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-sm truncate">{competitor.name}</h4>
                  <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                    <span>Вкупно: {competitor.totalActivity}</span>
                    <span className="text-green-600">Добиени: {competitor.wonCount}</span>
                  </div>
                </div>
                {trackedCompetitors.includes(competitor.name) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeCompetitor(competitor.name)}
                    className="ml-2 h-8 w-8 p-0"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Временска Линија на Активности</CardTitle>
          <CardDescription>Детален преглед на активности на конкурентите</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Пребарај по име на конкурент..."
                value={filterName}
                onChange={(e) => setFilterName(e.target.value)}
                className="pl-10"
              />
            </div>
          </div>

          <div className="space-y-3">
            {filteredActivities.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">Нема пронајдено активности</p>
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
                      {activity.estimated_value_mkd && <span>{formatCurrency(activity.estimated_value_mkd)}</span>}
                      <span className="flex items-center gap-1"><Calendar className="h-3 w-3" />ID: {activity.tender_id}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
