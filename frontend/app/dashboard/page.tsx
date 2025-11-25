"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api, type DashboardData } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import { TrendingUp, AlertCircle, Target, Award, Sparkles, ArrowRight, Clock } from "lucide-react";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isHydrated, setIsHydrated] = useState(false);
  const { user } = useAuth();

  // Track hydration to prevent client-side navigation errors
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (!isHydrated || !user) return;
    loadDashboard();
  }, [isHydrated, user]);

  async function loadDashboard() {
    if (!user?.user_id) return;

    try {
      setLoading(true);
      setError(null);

      // Try to get personalized dashboard data
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
            <Button onClick={loadDashboard}>Обиди се повторно</Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const container = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const item = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 }
  };

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="p-4 md:p-6 lg:p-8 space-y-4 md:space-y-6 lg:space-y-8"
    >
      {/* Free Tier Upgrade Banner - Only show for FREE plan users */}
      {user?.subscription_tier?.toLowerCase() === 'free' && (
        <motion.div variants={item}>
          <Card className="bg-gradient-to-r from-primary/10 via-purple-500/10 to-pink-500/10 border-primary/30">
            <CardContent className="p-4 md:p-6">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-start md:items-center gap-3 md:gap-4 flex-1">
                  <div className="h-10 w-10 md:h-12 md:w-12 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                    <Sparkles className="h-5 w-5 md:h-6 md:w-6 text-primary" />
                  </div>
                  <div className="flex-1">
                    <h3 className="text-base md:text-lg font-bold text-white">Вие сте на FREE планот</h3>
                    <p className="text-xs md:text-sm text-muted-foreground mt-1">
                      Надоградете за целосен пристап до напредна аналитика, неограничени пребарувања и повеќе функции
                    </p>
                  </div>
                </div>
                <a href="/settings" className="w-full md:w-auto">
                  <Button className="w-full md:w-auto bg-primary hover:bg-primary/90 shadow-lg">
                    <Award className="mr-2 h-4 w-4" />
                    <span className="hidden sm:inline">Надогради сега</span>
                    <span className="sm:hidden">Надогради</span>
                  </Button>
                </a>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      )}

      {/* Header */}
      <motion.div variants={item} className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400">
            Персонализирана Табла
          </h1>
          <p className="text-sm md:text-base text-muted-foreground mt-1">
            Вашите препорачани тендери и анализа на конкуренцијата
          </p>
        </div>
        <Button
          onClick={loadDashboard}
          disabled={loading}
          className="w-full sm:w-auto bg-primary hover:bg-primary/90 text-white shadow-[0_0_20px_rgba(124,58,237,0.3)]"
        >
          <Sparkles className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">{loading ? 'Анализирам...' : 'Нова Анализа'}</span>
          <span className="sm:hidden">{loading ? '...' : 'Анализа'}</span>
        </Button>
      </motion.div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <motion.div variants={item}>
          <Card className="bg-primary/10 border-primary/20">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2 text-primary">
                <Target className="h-4 w-4" />
                Препораки
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {data?.stats.recommended_count || 0}
              </div>
              <p className="text-xs text-primary/70 mt-1">Тендери за вас</p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={item}>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2 text-green-400">
                <TrendingUp className="h-4 w-4" />
                Конкуренти
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {data?.stats.competitor_activity_count || 0}
              </div>
              <p className="text-xs text-muted-foreground mt-1">Активности</p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={item}>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2 text-orange-400">
                <AlertCircle className="h-4 w-4" />
                Инсајти
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {data?.stats.insights_count || 0}
              </div>
              <p className="text-xs text-muted-foreground mt-1">AI анализи</p>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={item}>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center gap-2 text-blue-400">
                <Award className="h-4 w-4" />
                Отворени
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold text-white">
                {data?.recommended_tenders.filter(t => t.status === 'open').length || 0}
              </div>
              <p className="text-xs text-muted-foreground mt-1">Активни тендери</p>
            </CardContent>
          </Card>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6 lg:gap-8">
        {/* Recommended Tenders */}
        <motion.div variants={item} className="lg:col-span-2">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Препорачани Тендери</CardTitle>
              <CardDescription>Базирано на вашите преференци и интереси</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {data?.recommended_tenders.slice(0, 5).map((tender, idx) => (
                  <motion.div
                    key={tender.tender_id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className="group flex items-start justify-between p-4 rounded-xl border border-white/5 bg-white/5 hover:bg-white/10 transition-all hover:border-primary/20"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h4 className="font-medium text-white group-hover:text-primary transition-colors">
                          {tender.title}
                        </h4>
                        <span className="px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 text-xs font-medium border border-green-500/20">
                          {Math.round(tender.score * 100)}% match
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {tender.procuring_entity}
                      </p>
                      <div className="flex items-center gap-4 mt-3 text-xs text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-primary"></span>
                          {formatCurrency(tender.estimated_value_mkd)}
                        </span>
                        <span>Рок: {formatDate(tender.closing_date)}</span>
                      </div>
                      <div className="flex gap-2 mt-3">
                        {tender.match_reasons.map((reason, idx) => (
                          <span key={idx} className="text-[10px] px-2 py-1 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20">
                            {reason}
                          </span>
                        ))}
                      </div>
                      {tender.created_at && (
                        <div className="flex items-center gap-1 text-[10px] text-muted-foreground mt-2">
                          <Clock className="h-3 w-3" />
                          <span>Ажурирано: {formatDate(tender.created_at)}</span>
                        </div>
                      )}
                    </div>
                    <Button variant="ghost" size="icon" className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <ArrowRight className="h-4 w-4" />
                    </Button>
                  </motion.div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>

        {/* Sidebar Column */}
        <div className="space-y-8">
          {/* AI Insights */}
          {data?.insights && data.insights.length > 0 && (
            <motion.div variants={item}>
              <Card className="bg-gradient-to-b from-primary/10 to-transparent border-primary/20">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    AI Инсајти
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {data.insights.map((insight, idx) => (
                    <div key={idx} className="p-4 rounded-xl bg-background/50 border border-white/5">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs font-medium px-2 py-1 rounded bg-primary/10 text-primary">
                          {insight.insight_type}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {Math.round(insight.confidence * 100)}% доверба
                        </span>
                      </div>
                      <h4 className="font-medium text-sm text-white mb-1">{insight.title}</h4>
                      <p className="text-xs text-muted-foreground">{insight.description}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </motion.div>
          )}

          {/* Competitor Activity */}
          {data?.competitor_activity && data.competitor_activity.length > 0 && (
            <motion.div variants={item}>
              <Card>
                <CardHeader>
                  <CardTitle>Активности</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {data.competitor_activity.map((activity, idx) => (
                      <div key={idx} className="flex items-center justify-between p-3 rounded-lg border border-white/5 bg-white/5">
                        <div>
                          <h4 className="font-medium text-sm text-white">{activity.title}</h4>
                          <p className="text-xs text-muted-foreground mt-1">
                            {activity.competitor_name}
                          </p>
                        </div>
                        <span className="text-[10px] px-2 py-1 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
                          {activity.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
