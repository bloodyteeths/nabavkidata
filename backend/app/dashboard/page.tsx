"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, type DashboardData } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { TrendingUp, AlertCircle, Target, Award, Sparkles, ArrowRight, Bell, Search } from "lucide-react";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { OnboardingChecklist } from "@/components/onboarding/OnboardingChecklist";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const { user } = useAuth();

  // Onboarding state
  const [onboardingData, setOnboardingData] = useState({
    hasAlerts: false,
    hasSearches: false,
    hasTrackedCompetitors: false,
    hasSetPreferences: false,
  });

  // Track hydration to prevent client-side navigation errors
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (!isHydrated || !user) return;
    loadDashboard();
    loadOnboardingStatus();
  }, [isHydrated, user]);

  async function loadOnboardingStatus() {
    try {
      // Check for alerts, saved searches, and tracked competitors
      const [alertsRes, searchesRes, competitorsRes] = await Promise.allSettled([
        api.getAlerts(),
        api.getSavedSearches(),
        api.getTrackedCompetitors(),
      ]);

      setOnboardingData({
        hasAlerts: alertsRes.status === "fulfilled" && ((alertsRes.value as any)?.alerts?.length || 0) > 0,
        hasSearches: searchesRes.status === "fulfilled" && ((searchesRes.value as any)?.items?.length || 0) > 0,
        hasTrackedCompetitors: competitorsRes.status === "fulfilled" && ((competitorsRes.value as any)?.tracked_competitors?.length || (competitorsRes.value as any)?.count || 0) > 0,
        hasSetPreferences: Boolean((user as any)?.preferences_set || (user as any)?.industry || (user as any)?.cpv_codes?.length),
      });
    } catch (error) {
      console.debug("Failed to load onboarding status:", error);
    }
  }

  async function loadDashboard() {
    if (!user?.user_id) return;

    try {
      setLoading(true);
      setError(null);

      // Get personalized dashboard data (backend generates fresh analysis each time)
      const dashboardData = await api.getPersonalizedDashboard(user.user_id);
      setData(dashboardData);
    } catch (error) {
      console.error("Failed to load personalized dashboard:", error);

      // Fallback to generic tenders if personalization fails
      try {
        const tenders = await api.searchTenders({ page: 1, page_size: 10 });
        const fallbackData: DashboardData = {
          stats: {
            recommended_count: tenders.items?.length || 0,
            competitor_activity_count: 0,
            insights_count: 0,
          },
          recommended_tenders: (tenders.items || []).map(t => ({
            ...t,
            score: 0.75,
            match_reasons: ['Нов тендер']
          })),
          insights: [],
          competitor_activity: []
        };
        setData(fallbackData);
      } catch (fallbackError) {
        console.error("Failed to load fallback data:", fallbackError);
        setError("Не можевме да ги вчитаме податоците. Ве молиме обидете се повторно.");
      }
    } finally {
      setLoading(false);
    }
  }

  if (!isHydrated || loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <Card className="max-w-md">
          <CardContent className="p-6 text-center">
            <AlertCircle className="h-12 w-12 mx-auto mb-4 text-destructive" />
            <h3 className="text-lg font-semibold mb-2">Грешка при вчитување</h3>
            <p className="text-muted-foreground mb-4">{error}</p>
            <Button onClick={() => loadDashboard()}>Обиди се повторно</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-3 md:p-6 lg:p-8 space-y-3 md:space-y-6 lg:space-y-8">
      {/* Free Tier Upgrade Banner - Only show for FREE plan users */}
      {user?.subscription_tier?.toLowerCase() === 'free' && (
        <div>
          <Card className="bg-gradient-to-r from-primary/10 via-purple-500/10 to-pink-500/10 border-primary/30">
            <CardContent className="p-3 md:p-6">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 md:gap-4">
                <div className="flex items-start md:items-center gap-3 md:gap-4 flex-1">
                  <div className="h-8 w-8 md:h-12 md:w-12 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                    <Sparkles className="h-4 w-4 md:h-6 md:w-6 text-primary" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-sm md:text-lg font-bold text-white">Вие сте на FREE планот</h3>
                    <p className="text-xs md:text-sm text-muted-foreground mt-1">
                      Надоградете за целосен пристап до напредна аналитика, неограничени пребарувања и повеќе функции
                    </p>
                  </div>
                </div>
                <Link href="/settings" className="w-full md:w-auto">
                  <Button className="w-full md:w-auto bg-primary hover:bg-primary/90 shadow-lg h-8 md:h-10 text-xs md:text-sm">
                    <Award className="mr-2 h-3 w-3 md:h-4 md:w-4" />
                    <span className="hidden sm:inline">Надогради сега</span>
                    <span className="sm:hidden">Надогради</span>
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Onboarding Checklist - Show for users who haven't completed key steps */}
      <OnboardingChecklist
        hasAlerts={onboardingData.hasAlerts}
        hasSearches={onboardingData.hasSearches}
        hasTrackedCompetitors={onboardingData.hasTrackedCompetitors}
        hasSetPreferences={onboardingData.hasSetPreferences}
      />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 md:gap-4">
        <div>
          <h1 className="text-xl md:text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
            Персонализирана Табла
          </h1>
          <p className="text-xs md:text-base text-muted-foreground mt-1">
            Вашите препорачани тендери и анализа на конкуренцијата
          </p>
        </div>
        <Button
          onClick={() => loadDashboard()}
          disabled={loading}
          className="w-full sm:w-auto bg-primary hover:bg-primary/90 text-white shadow-[0_0_20px_rgba(124,58,237,0.3)] h-9 md:h-10 text-xs md:text-sm"
        >
          <Sparkles className={`mr-2 h-3 w-3 md:h-4 md:w-4 ${loading ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">{loading ? 'Анализирам...' : 'Освежи'}</span>
          <span className="sm:hidden">{loading ? '...' : 'Освежи'}</span>
        </Button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        <div>
          <Card className="bg-primary/10 border-primary/20 h-full">
            <CardHeader className="p-3 md:p-6 pb-2 md:pb-3">
              <CardTitle className="text-xs md:text-sm font-medium flex items-center gap-1.5 md:gap-2 text-primary">
                <Target className="h-3.5 w-3.5 md:h-4 md:w-4" />
                Препораки
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 md:p-6 pt-0 md:pt-0">
              <div className="text-2xl md:text-3xl font-bold text-white">
                {data?.stats.recommended_count || 0}
              </div>
              <p className="text-[10px] md:text-xs text-primary/70 mt-1">Тендери за вас</p>
            </CardContent>
          </Card>
        </div>

        <div>
          <Card className="h-full">
            <CardHeader className="p-3 md:p-6 pb-2 md:pb-3">
              <CardTitle className="text-xs md:text-sm font-medium flex items-center gap-1.5 md:gap-2 text-green-400">
                <TrendingUp className="h-3.5 w-3.5 md:h-4 md:w-4" />
                Конкуренти
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 md:p-6 pt-0 md:pt-0">
              <div className="text-2xl md:text-3xl font-bold text-white">
                {data?.stats.competitor_activity_count || 0}
              </div>
              <p className="text-[10px] md:text-xs text-muted-foreground mt-1">Активности</p>
            </CardContent>
          </Card>
        </div>

        <div>
          <Card className="h-full">
            <CardHeader className="p-3 md:p-6 pb-2 md:pb-3">
              <CardTitle className="text-xs md:text-sm font-medium flex items-center gap-1.5 md:gap-2 text-orange-400">
                <AlertCircle className="h-3.5 w-3.5 md:h-4 md:w-4" />
                Инсајти
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 md:p-6 pt-0 md:pt-0">
              <div className="text-2xl md:text-3xl font-bold text-white">
                {data?.stats.insights_count || 0}
              </div>
              <p className="text-[10px] md:text-xs text-muted-foreground mt-1">AI анализи</p>
            </CardContent>
          </Card>
        </div>

        <div>
          <Card className="h-full">
            <CardHeader className="p-3 md:p-6 pb-2 md:pb-3">
              <CardTitle className="text-xs md:text-sm font-medium flex items-center gap-1.5 md:gap-2 text-blue-400">
                <Award className="h-3.5 w-3.5 md:h-4 md:w-4" />
                Отворени
              </CardTitle>
            </CardHeader>
            <CardContent className="p-3 md:p-6 pt-0 md:pt-0">
              <div className="text-2xl md:text-3xl font-bold text-white">
                {data?.recommended_tenders?.filter(t => t.status === 'open').length || 0}
              </div>
              <p className="text-[10px] md:text-xs text-muted-foreground mt-1">Активни тендери</p>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 md:gap-6 lg:gap-8">
        {/* Recommended Tenders */}
        <div className="lg:col-span-2">
          <Card className="h-full">
            <CardHeader className="p-4 md:p-6">
              <CardTitle className="text-lg md:text-xl">Препорачани Тендери</CardTitle>
              <CardDescription className="text-xs md:text-sm">Базирано на вашите преференци и интереси</CardDescription>
            </CardHeader>
            <CardContent className="p-4 md:p-6 pt-0">
              <div className="space-y-3 md:space-y-4">
                {(!data?.recommended_tenders || data.recommended_tenders.length === 0) && (
                  <div className="text-center py-8">
                    <Target className="h-10 w-10 md:h-12 md:w-12 mx-auto mb-3 md:mb-4 text-primary/50" />
                    <h3 className="text-sm font-semibold mb-2">Персонализирајте ги препораките</h3>
                    <p className="text-xs text-muted-foreground mb-4 max-w-sm mx-auto">
                      Поставете ги вашите преференци за да добивате AI препораки за релевантни тендери.
                    </p>
                    <div className="flex flex-col sm:flex-row gap-2 justify-center">
                      <Link href="/settings">
                        <Button size="sm" className="w-full sm:w-auto">
                          <Sparkles className="h-4 w-4 mr-2" />
                          Постави преференци
                        </Button>
                      </Link>
                      <Link href="/tenders">
                        <Button size="sm" variant="outline" className="w-full sm:w-auto">
                          <Search className="h-4 w-4 mr-2" />
                          Истражи тендери
                        </Button>
                      </Link>
                    </div>
                  </div>
                )}
                {(data?.recommended_tenders || []).slice(0, 5).map((tender) => (
                  <Link
                    key={tender.tender_id}
                    href={`/tenders/${encodeURIComponent(tender.tender_id)}`}
                    className="group flex items-start justify-between p-3 md:p-4 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 transition-all hover:border-primary/20 cursor-pointer block"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <h4 className="font-medium text-sm md:text-base text-white group-hover:text-primary transition-colors line-clamp-2">
                          {tender.title}
                        </h4>
                        <span className="px-1.5 py-0.5 rounded-full bg-green-500/10 text-green-400 text-[10px] md:text-xs font-medium border border-green-500/20 whitespace-nowrap">
                          {Math.round(tender.score * 100)}% match
                        </span>
                      </div>
                      <p className="text-xs md:text-sm text-muted-foreground line-clamp-1">
                        {tender.procuring_entity}
                      </p>
                      <div className="flex items-center gap-3 md:gap-4 mt-2 md:mt-3 text-[10px] md:text-xs text-muted-foreground flex-wrap">
                        <span className="flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
                          {formatCurrency(tender.estimated_value_mkd)}
                        </span>
                        {tender.closing_date && (
                          <span>Рок: {formatDate(tender.closing_date)}</span>
                        )}
                      </div>
                      <div className="flex gap-1.5 md:gap-2 mt-2 md:mt-3 flex-wrap">
                        {tender.match_reasons.map((reason, idx) => (
                          <span key={idx} className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                            {reason}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity ml-2 flex-shrink-0 hidden sm:block">
                      <ArrowRight className="h-4 w-4 text-primary" />
                    </div>
                  </Link>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar Column */}
        <div className="space-y-4 md:space-y-8">
          {/* AI Insights */}
          <div>
            <Card className="bg-gradient-to-b from-primary/10 to-transparent border-primary/20">
              <CardHeader className="p-4 md:p-6">
                <CardTitle className="flex items-center gap-2 text-base md:text-lg">
                  <Sparkles className="h-4 w-4 text-primary" />
                  AI Инсајти
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 md:p-6 pt-0 space-y-3 md:space-y-4">
                {(!data?.insights || data.insights.length === 0) ? (
                  <div className="text-center py-4">
                    <Sparkles className="h-6 w-6 md:h-8 md:w-8 mx-auto mb-2 text-primary/50" />
                    <p className="text-xs font-medium mb-1">AI инсајти</p>
                    <p className="text-[10px] text-muted-foreground mb-3">
                      Креирајте алерт за персонализирани анализи
                    </p>
                    <Link href="/alerts?tab=create">
                      <Button size="sm" variant="outline" className="h-7 text-xs">
                        <Bell className="h-3 w-3 mr-1" />
                        Креирај алерт
                      </Button>
                    </Link>
                  </div>
                ) : (
                  data.insights.map((insight, idx) => {
                    // Build URL based on insight type
                    const getInsightUrl = () => {
                      switch (insight.insight_type) {
                        case 'alert':
                          // Deadlines approaching - show tenders closing soon
                          return '/tenders?status=open&closing_within=7';
                        case 'opportunity':
                          // Budget opportunities - show open tenders
                          return '/tenders?status=open';
                        case 'trend':
                          // Trending sectors - show open tenders
                          return '/tenders?status=open';
                        default:
                          return '/tenders?status=open';
                      }
                    };

                    // Translate insight type to Macedonian
                    const getInsightTypeLabel = () => {
                      switch (insight.insight_type) {
                        case 'alert':
                          return 'Известување';
                        case 'opportunity':
                          return 'Можност';
                        case 'trend':
                          return 'Тренд';
                        default:
                          return insight.insight_type;
                      }
                    };

                    return (
                      <Link
                        key={idx}
                        href={getInsightUrl()}
                        className="group block p-3 md:p-4 rounded-xl bg-background/50 border border-white/5 hover:bg-background/80 hover:border-primary/20 transition-all cursor-pointer"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-[10px] md:text-xs font-medium px-2 py-1 rounded bg-primary/10 text-primary">
                            {getInsightTypeLabel()}
                          </span>
                          <span className="text-[10px] md:text-xs text-muted-foreground">
                            {Math.round(insight.confidence * 100)}% доверба
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <div className="flex-1">
                            <h4 className="font-medium text-xs md:text-sm text-white mb-1 group-hover:text-primary transition-colors">{insight.title}</h4>
                            <p className="text-[10px] md:text-xs text-muted-foreground">{insight.description}</p>
                          </div>
                          <ArrowRight className="h-4 w-4 text-primary opacity-0 group-hover:opacity-100 transition-opacity ml-2 flex-shrink-0 hidden sm:block" />
                        </div>
                      </Link>
                    );
                  })
                )}
              </CardContent>
            </Card>
          </div>

          {/* Competitor Activity */}
          {data?.competitor_activity && data.competitor_activity.length > 0 && (
            <div>
              <Card>
                <CardHeader className="p-4 md:p-6">
                  <CardTitle className="text-base md:text-lg">Активности</CardTitle>
                </CardHeader>
                <CardContent className="p-4 md:p-6 pt-0">
                  <div className="space-y-3">
                    {data.competitor_activity.map((activity, idx) => (
                      <Link
                        key={idx}
                        href={`/tenders/${encodeURIComponent(activity.tender_id)}`}
                        className="group flex items-center justify-between p-3 rounded-lg border border-white/5 bg-white/5 hover:bg-white/10 hover:border-primary/20 transition-all cursor-pointer block"
                      >
                        <div className="flex-1 min-w-0">
                          <h4 className="font-medium text-xs md:text-sm text-white group-hover:text-primary transition-colors line-clamp-2">{activity.title}</h4>
                          <p className="text-[10px] md:text-xs text-muted-foreground mt-1">
                            {activity.competitor_name}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                          <span className="text-[10px] px-2 py-1 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                            {activity.status}
                          </span>
                          <ArrowRight className="h-3 w-3 text-primary opacity-0 group-hover:opacity-100 transition-opacity hidden sm:block" />
                        </div>
                      </Link>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>

  );
}
