"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api, type DashboardData } from "@/lib/api";
import { formatCurrency, formatDate, tenderUrl } from "@/lib/utils";
import { TrendingUp, AlertCircle, Target, Award, Sparkles, ArrowRight, Bell, Search, Clock, DollarSign, Users, RefreshCw, Zap, FileText } from "lucide-react";
import { useAuth } from "@/lib/auth";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { WelcomeWizard } from "@/components/onboarding/WelcomeWizard";
import { PageContainer } from "@/components/ui/page-container";
import { PageHeader } from "@/components/ui/page-header";
import { StatCard, StatsGrid } from "@/components/ui/stat-card";
import { EmptyState } from "@/components/ui/empty-state";
import { LoadingStats } from "@/components/ui/loading-card";

const SEARCH_CHIPS = [
  "канцелариски материјали",
  "медицинска опрема",
  "ИТ услуги",
  "градежни работи",
  "храна и пијалоци",
  "транспорт",
];

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const { user } = useAuth();
  const router = useRouter();
  const [showWizard, setShowWizard] = useState(false);

  useEffect(() => {
    if (!user) return;
    loadDashboard();
    if (typeof window !== 'undefined') {
      const wizardDone = localStorage.getItem('wizard_completed') === 'true';
      if (!wizardDone) setShowWizard(true);
    }
  }, [user]);

  async function loadDashboard() {
    if (!user?.user_id) return;
    try {
      setLoading(true);
      setError(null);
      const dashboardData = await api.getPersonalizedDashboard(user.user_id);
      setData(dashboardData);
    } catch {
      try {
        const tenders = await api.searchTenders({ page: 1, page_size: 10 });
        setData({
          stats: { recommended_count: tenders.items?.length || 0, competitor_activity_count: 0, insights_count: 0 },
          recommended_tenders: (tenders.items || []).map(t => ({ ...t, score: 0.75, match_reasons: ['Нов тендер'] })),
          insights: [],
          competitor_activity: []
        });
      } catch {
        setError("Не можевме да ги вчитаме податоците.");
      }
    } finally {
      setLoading(false);
    }
  }

  const firstName = user?.full_name?.split(" ")[0] || "User";
  const isFree = user?.subscription_tier?.toLowerCase() === 'free';
  const hasPersonalData = (data?.stats.recommended_count || 0) > 0;

  return (
    <PageContainer>
      {showWizard && <WelcomeWizard onComplete={() => setShowWizard(false)} />}

      {/* Trial/Upgrade Banner */}
      {isFree && (
        <div className="rounded-xl border border-primary/30 bg-gradient-to-r from-primary/10 via-purple-500/10 to-pink-500/10 p-4 md:p-5">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-primary/20 flex items-center justify-center shrink-0">
                <Zap className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold">Бесплатен план</p>
                <p className="text-xs text-muted-foreground">3 AI пребарувања дневно. Надоградете за неограничен пристап.</p>
              </div>
            </div>
            <Link href="/settings">
              <Button size="sm" className="shadow-[0_0_20px_rgba(124,58,237,0.2)]">
                <Award className="mr-2 h-4 w-4" /> Надогради
              </Button>
            </Link>
          </div>
        </div>
      )}

      {/* Page Header */}
      <PageHeader
        icon={Target}
        title={`Добредојде, ${firstName}`}
        description="Вашите препорачани тендери и конкурентна интелигенција"
      >
        <Button onClick={loadDashboard} disabled={loading} variant="outline" size="sm">
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Освежи
        </Button>
      </PageHeader>

      {/* Search Bar */}
      <Card className="border-primary/20">
        <CardContent className="p-4">
          <form onSubmit={(e) => { e.preventDefault(); if (searchQuery.trim()) router.push(`/tenders?search=${encodeURIComponent(searchQuery.trim())}`); }} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Пребарајте тендери по клучен збор, купувач или сектор..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 h-11"
              />
            </div>
            <Button type="submit" disabled={!searchQuery.trim()} className="h-11 px-5">
              <Search className="h-4 w-4 md:mr-2" />
              <span className="hidden md:inline">Пребарај</span>
            </Button>
          </form>
          <div className="flex flex-wrap gap-1.5 mt-3">
            {SEARCH_CHIPS.map((chip) => (
              <button key={chip} type="button" onClick={() => router.push(`/tenders?search=${encodeURIComponent(chip)}`)}
                className="text-xs px-3 py-1.5 rounded-full border border-primary/20 hover:bg-primary/10 hover:border-primary/40 transition-colors text-muted-foreground hover:text-foreground">
                {chip}
              </button>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Stats Grid */}
      {loading ? (
        <LoadingStats count={4} />
      ) : error ? (
        <Card className="border-destructive/30">
          <CardContent className="p-6 text-center">
            <AlertCircle className="h-10 w-10 mx-auto mb-3 text-destructive" />
            <p className="text-sm text-muted-foreground mb-3">{error}</p>
            <Button size="sm" onClick={loadDashboard}>Обиди се повторно</Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <StatsGrid columns={4}>
            <StatCard
              icon={Target}
              iconColor="bg-primary/10 text-primary"
              label={hasPersonalData ? "Препораки" : "Тендери"}
              value={hasPersonalData ? data?.stats.recommended_count || 0 : "290K+"}
              subtitle={hasPersonalData ? "Тендери за вас" : "Во базата"}
            />
            <StatCard
              icon={FileText}
              iconColor="bg-green-500/10 text-green-500"
              label="Отворени"
              value={hasPersonalData ? data?.recommended_tenders?.filter(t => t.status === 'open').length || 0 : "880+"}
              subtitle="Активни тендери"
            />
            <StatCard
              icon={Users}
              iconColor="bg-orange-500/10 text-orange-500"
              label="Конкуренти"
              value={data?.stats.competitor_activity_count || 0}
              subtitle="Активности"
            />
            <StatCard
              icon={Sparkles}
              iconColor="bg-purple-500/10 text-purple-500"
              label="AI Инсајти"
              value={data?.stats.insights_count || 0}
              subtitle="Анализи за вас"
            />
          </StatsGrid>

          {/* Closing Soon */}
          {(() => {
            const now = new Date();
            const weekFromNow = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
            const closingSoon = (data?.recommended_tenders || []).filter(t => {
              if (!t.closing_date) return false;
              const cd = new Date(t.closing_date);
              return cd > now && cd <= weekFromNow;
            }).sort((a, b) => new Date(a.closing_date!).getTime() - new Date(b.closing_date!).getTime());

            if (closingSoon.length === 0) return null;
            return (
              <Card className="border-orange-500/30">
                <CardHeader className="p-4 pb-3">
                  <CardTitle className="text-base flex items-center gap-2 text-orange-500">
                    <Clock className="h-5 w-5" />
                    Затвораат наскоро
                    <Badge variant="outline" className="ml-auto text-xs font-normal border-orange-500/20 text-orange-500">следните 7 дена</Badge>
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-0">
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {closingSoon.slice(0, 3).map(tender => {
                      const daysLeft = Math.ceil((new Date(tender.closing_date!).getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
                      return (
                        <Link key={tender.tender_id} href={tenderUrl(tender.tender_id)}
                          className="group p-3 rounded-xl border hover:border-primary/30 hover:bg-accent/5 transition-all">
                          <div className="flex items-center justify-between mb-2">
                            <Badge variant="outline" className={daysLeft <= 2 ? 'border-red-500/30 text-red-500 text-[10px]' : 'border-orange-500/30 text-orange-500 text-[10px]'}>
                              {daysLeft <= 1 ? 'УТРЕ!' : `${daysLeft} дена`}
                            </Badge>
                            <span className="text-[10px] text-green-500 font-medium">{Math.round(tender.score * 100)}%</span>
                          </div>
                          <h4 className="text-sm font-medium line-clamp-2 group-hover:text-primary transition-colors">{tender.title}</h4>
                          <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{tender.procuring_entity}</p>
                          {tender.estimated_value_mkd && (
                            <p className="text-xs font-semibold text-primary mt-2">{formatCurrency(tender.estimated_value_mkd)}</p>
                          )}
                        </Link>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            );
          })()}

          {/* Main Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Recommended Tenders */}
            <div className="lg:col-span-2">
              <Card>
                <CardHeader className="p-4 md:p-6">
                  <CardTitle className="text-lg">Препорачани Тендери</CardTitle>
                  <CardDescription>Базирано на вашите преференци и интереси</CardDescription>
                </CardHeader>
                <CardContent className="p-4 md:p-6 pt-0">
                  {(!data?.recommended_tenders || data.recommended_tenders.length === 0) ? (
                    <EmptyState
                      icon={Target}
                      title="Персонализирајте ги препораките"
                      description="Поставете ги вашите преференци за да добивате AI препораки за релевантни тендери."
                      action={{ label: "Постави преференци", href: "/settings" }}
                      secondaryAction={{ label: "Истражи тендери", href: "/tenders" }}
                    />
                  ) : (
                    <div className="space-y-3">
                      {data.recommended_tenders.slice(0, 5).map((tender) => (
                        <Link key={tender.tender_id} href={tenderUrl(tender.tender_id)}
                          className="group flex items-start justify-between p-4 rounded-xl border hover:border-primary/20 hover:bg-accent/5 transition-all">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <h4 className="font-medium text-sm text-foreground group-hover:text-primary transition-colors line-clamp-2">
                                {tender.title}
                              </h4>
                              <Badge variant="outline" className="border-green-500/20 text-green-500 text-[10px]">
                                {Math.round(tender.score * 100)}%
                              </Badge>
                            </div>
                            <p className="text-xs text-muted-foreground line-clamp-1">{tender.procuring_entity}</p>
                            <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground flex-wrap">
                              <span className="font-medium text-foreground">{formatCurrency(tender.estimated_value_mkd)}</span>
                              {tender.closing_date && <span>Рок: {formatDate(tender.closing_date)}</span>}
                            </div>
                            <div className="flex gap-1.5 mt-2 flex-wrap">
                              {tender.match_reasons.map((reason, idx) => (
                                <span key={idx} className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                                  {reason}
                                </span>
                              ))}
                            </div>
                          </div>
                          <ArrowRight className="h-4 w-4 text-primary opacity-0 group-hover:opacity-100 transition-opacity ml-3 mt-1 shrink-0 hidden sm:block" />
                        </Link>
                      ))}
                      <Link href="/tenders" className="flex items-center justify-center gap-1 pt-2 text-sm text-primary hover:text-primary/80 transition-colors">
                        Погледни ги сите тендери <ArrowRight className="h-4 w-4" />
                      </Link>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Quick Actions */}
              <Card>
                <CardHeader className="p-4">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" /> Брзи акции
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-4 pt-0 space-y-2">
                  {[
                    { href: "/products", icon: DollarSign, color: "text-green-500", label: "Провери цени", desc: "Пазарни цени за производи" },
                    { href: "/trends", icon: TrendingUp, color: "text-blue-500", label: "Трендови", desc: "Итни можности во 7 дена" },
                    { href: "/competitors", icon: Users, color: "text-orange-500", label: "Конкуренти", desc: "Кој понудува во вашиот сектор" },
                    { href: "/alerts?tab=create", icon: Bell, color: "text-purple-500", label: "Креирај алерт", desc: "Известувања за нови тендери" },
                  ].map(({ href, icon: Icon, color, label, desc }) => (
                    <Link key={href} href={href}
                      className="flex items-center gap-3 p-3 rounded-xl border hover:border-primary/20 hover:bg-accent/5 transition-all group">
                      <div className={`h-8 w-8 rounded-lg bg-muted flex items-center justify-center shrink-0`}>
                        <Icon className={`h-4 w-4 ${color}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium group-hover:text-primary transition-colors">{label}</p>
                        <p className="text-xs text-muted-foreground">{desc}</p>
                      </div>
                      <ArrowRight className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                    </Link>
                  ))}
                </CardContent>
              </Card>

              {/* AI Insights */}
              {data?.insights && data.insights.length > 0 && (
                <Card className="border-primary/20">
                  <CardHeader className="p-4">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-primary" /> AI Инсајти
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 pt-0 space-y-3">
                    {data.insights.map((insight, idx) => (
                      <Link key={idx} href="/tenders?status=open"
                        className="group block p-3 rounded-xl border hover:border-primary/20 hover:bg-accent/5 transition-all">
                        <div className="flex items-center justify-between mb-1">
                          <Badge variant="outline" className="text-[10px] border-primary/20 text-primary">
                            {insight.insight_type === 'alert' ? 'Известување' : insight.insight_type === 'opportunity' ? 'Можност' : 'Тренд'}
                          </Badge>
                          <span className="text-[10px] text-muted-foreground">{Math.round(insight.confidence * 100)}%</span>
                        </div>
                        <h4 className="text-sm font-medium group-hover:text-primary transition-colors">{insight.title}</h4>
                        <p className="text-xs text-muted-foreground mt-0.5">{insight.description}</p>
                      </Link>
                    ))}
                  </CardContent>
                </Card>
              )}

              {/* Competitor Activity */}
              {data?.competitor_activity && data.competitor_activity.length > 0 && (
                <Card>
                  <CardHeader className="p-4">
                    <CardTitle className="text-base">Активности на конкуренти</CardTitle>
                  </CardHeader>
                  <CardContent className="p-4 pt-0 space-y-2">
                    {data.competitor_activity.map((activity, idx) => (
                      <Link key={idx} href={tenderUrl(activity.tender_id)}
                        className="group flex items-center justify-between p-3 rounded-xl border hover:border-primary/20 hover:bg-accent/5 transition-all">
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm font-medium group-hover:text-primary transition-colors line-clamp-1">{activity.title}</h4>
                          <p className="text-xs text-muted-foreground mt-0.5">{activity.competitor_name}</p>
                        </div>
                        <Badge variant="outline" className="ml-2 shrink-0 text-[10px] border-yellow-500/20 text-yellow-500">{activity.status}</Badge>
                      </Link>
                    ))}
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </>
      )}
    </PageContainer>
  );
}
