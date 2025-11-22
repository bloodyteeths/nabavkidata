"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, type DashboardData } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { TrendingUp, AlertCircle, Target, Award } from "lucide-react";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard() {
    try {
      // TODO: Get real user_id from auth
      const userId = "demo-user-id";
      const result = await api.getPersonalizedDashboard(userId);
      setData(result);
    } catch (error) {
      console.error("Failed to load dashboard:", error);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Се вчитува...</p>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Персонализирана Табла</h1>
        <p className="text-muted-foreground">
          Вашите препорачани тендери и анализа на конкуренцијата
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Target className="h-4 w-4 text-primary" />
              Препораки
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data?.stats.recommended_count || 0}
            </div>
            <p className="text-xs text-muted-foreground">Тендери за вас</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-600" />
              Конкуренти
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data?.stats.competitor_activity_count || 0}
            </div>
            <p className="text-xs text-muted-foreground">Активности</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <AlertCircle className="h-4 w-4 text-orange-600" />
              Инсајти
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data?.stats.insights_count || 0}
            </div>
            <p className="text-xs text-muted-foreground">AI анализи</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Award className="h-4 w-4 text-blue-600" />
              Отворени
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {data?.recommended_tenders.filter(t => t.status === 'open').length || 0}
            </div>
            <p className="text-xs text-muted-foreground">Активни тендери</p>
          </CardContent>
        </Card>
      </div>

      {/* AI Insights */}
      {data?.insights && data.insights.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>AI Инсајти</CardTitle>
            <CardDescription>Персонализирани анализи базирани на вашите преференци</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {data.insights.map((insight, idx) => (
              <div key={idx} className="flex items-start gap-3 p-4 rounded-lg bg-accent/50">
                <AlertCircle className="h-5 w-5 text-primary mt-0.5" />
                <div className="flex-1">
                  <h4 className="font-medium">{insight.title}</h4>
                  <p className="text-sm text-muted-foreground mt-1">{insight.description}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs px-2 py-1 rounded bg-background">
                      {insight.insight_type}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      Доверба: {Math.round(insight.confidence * 100)}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Recommended Tenders */}
      <Card>
        <CardHeader>
          <CardTitle>Препорачани Тендери</CardTitle>
          <CardDescription>Базирано на вашите преференци и интереси</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {data?.recommended_tenders.slice(0, 5).map((tender) => (
              <div key={tender.tender_id} className="flex items-start justify-between p-4 rounded-lg border hover:bg-accent/50 transition-colors">
                <div className="flex-1">
                  <h4 className="font-medium">{tender.title}</h4>
                  <p className="text-sm text-muted-foreground mt-1">
                    {tender.procuring_entity}
                  </p>
                  <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                    <span>{formatCurrency(tender.estimated_value_mkd)}</span>
                    <span>Рок: {formatDate(tender.closing_date)}</span>
                    <span className="px-2 py-1 rounded bg-green-100 text-green-700">
                      {Math.round(tender.score * 100)}% match
                    </span>
                  </div>
                  <div className="flex gap-2 mt-2">
                    {tender.match_reasons.map((reason, idx) => (
                      <span key={idx} className="text-xs px-2 py-1 rounded bg-blue-100 text-blue-700">
                        {reason}
                      </span>
                    ))}
                  </div>
                </div>
                <Button variant="outline" size="sm">
                  Детали
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Competitor Activity */}
      {data?.competitor_activity && data.competitor_activity.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Активности на Конкуренти</CardTitle>
            <CardDescription>Следење на вашите главни конкуренти</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data.competitor_activity.map((activity, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-lg border">
                  <div>
                    <h4 className="font-medium text-sm">{activity.title}</h4>
                    <p className="text-xs text-muted-foreground mt-1">
                      Конкурент: {activity.competitor_name}
                    </p>
                  </div>
                  <span className="text-xs px-2 py-1 rounded bg-yellow-100 text-yellow-700">
                    {activity.status}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
