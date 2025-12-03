"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Target, TrendingUp, TrendingDown, Users, Percent, Building2, Trophy } from "lucide-react";
import { formatCurrency } from "@/lib/utils";

interface Recommendation {
  strategy: string;
  recommended_bid: number;
  win_probability: number;
  reasoning: string;
}

interface BidRecommendationProps {
  tenderId: string;
  estimatedValue?: number;
  marketAnalysis?: {
    avg_discount: number;
    typical_bidders: number;
    price_trend: string;
  };
  recommendations: Recommendation[];
  competitorInsights?: Array<{
    company: string;
    win_rate: number;
    avg_discount: number;
  }>;
  aiSummary?: string;
  loading?: boolean;
}

export function BidRecommendation({
  tenderId,
  estimatedValue,
  marketAnalysis,
  recommendations,
  competitorInsights,
  aiSummary,
  loading = false,
}: BidRecommendationProps) {
  if (loading) {
    return (
      <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-primary/10">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="h-5 w-5 text-primary" />
            AI ПРЕПОРАКА ЗА ПОНУДА
          </CardTitle>
          <CardDescription>
            AI анализира слични тендери за да ви даде препорака...
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="animate-pulse space-y-4">
            <div className="h-20 bg-muted rounded-lg" />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="h-48 bg-muted rounded-lg" />
              <div className="h-48 bg-muted rounded-lg" />
              <div className="h-48 bg-muted rounded-lg" />
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Sort recommendations: balanced, aggressive, safe
  const sortedRecommendations = [...recommendations].sort((a, b) => {
    const order = { balanced: 1, aggressive: 0, safe: 2 };
    return (order[a.strategy as keyof typeof order] ?? 3) - (order[b.strategy as keyof typeof order] ?? 3);
  });

  const getStrategyConfig = (strategy: string) => {
    switch (strategy.toLowerCase()) {
      case "aggressive":
        return {
          label: "АГРЕСИВНА",
          icon: "🔴",
          color: "text-red-600",
          bgColor: "bg-red-50 dark:bg-red-950/20",
          borderColor: "border-red-200 dark:border-red-900",
          progressColor: "bg-red-600",
        };
      case "balanced":
        return {
          label: "БАЛАНСИРАНА",
          icon: "🟡",
          color: "text-yellow-600",
          bgColor: "bg-yellow-50 dark:bg-yellow-950/20",
          borderColor: "border-yellow-200 dark:border-yellow-900",
          progressColor: "bg-yellow-600",
        };
      case "safe":
        return {
          label: "СИГУРНА",
          icon: "🟢",
          color: "text-green-600",
          bgColor: "bg-green-50 dark:bg-green-950/20",
          borderColor: "border-green-200 dark:border-green-900",
          progressColor: "bg-green-600",
        };
      default:
        return {
          label: strategy.toUpperCase(),
          icon: "⚪",
          color: "text-muted-foreground",
          bgColor: "bg-muted",
          borderColor: "border-muted",
          progressColor: "bg-muted-foreground",
        };
    }
  };

  const getTrendIcon = (trend: string) => {
    if (trend === "increasing") return <TrendingUp className="h-4 w-4 text-red-600" />;
    if (trend === "decreasing") return <TrendingDown className="h-4 w-4 text-green-600" />;
    return <TrendingUp className="h-4 w-4 text-muted-foreground" />;
  };

  return (
    <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-primary/10">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg md:text-xl">
          <Target className="h-5 w-5 text-primary" />
          AI ПРЕПОРАКА ЗА ПОНУДА
        </CardTitle>
        <CardDescription>
          Паметни стратегии базирани на историски податоци од {recommendations.length > 0 ? "слични тендери" : "тендери"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* AI Summary */}
        {aiSummary && (
          <div className="p-4 rounded-lg bg-primary/10 border border-primary/20">
            <div className="flex items-start gap-2">
              <div className="text-2xl flex-shrink-0">💡</div>
              <p className="text-sm leading-relaxed">
                {aiSummary}
              </p>
            </div>
          </div>
        )}

        {/* Recommendation Cards */}
        {sortedRecommendations.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {sortedRecommendations.map((rec) => {
              const config = getStrategyConfig(rec.strategy);
              const discountPercent = estimatedValue
                ? ((estimatedValue - rec.recommended_bid) / estimatedValue) * 100
                : 0;

              return (
                <Card
                  key={rec.strategy}
                  className={`${config.bgColor} ${config.borderColor} border-2 transition-all hover:shadow-lg`}
                >
                  <CardHeader className="pb-3">
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">{config.icon}</span>
                      <CardTitle className={`text-sm font-bold ${config.color}`}>
                        {config.label}
                      </CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Recommended Bid */}
                    <div>
                      <p className="text-2xl font-bold">{formatCurrency(rec.recommended_bid)}</p>
                      {estimatedValue && (
                        <p className="text-xs text-muted-foreground mt-1">
                          {discountPercent > 0 ? "-" : "+"}{Math.abs(discountPercent).toFixed(0)}% од процена
                        </p>
                      )}
                    </div>

                    {/* Win Probability */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">Веројатност:</span>
                        <span className={`font-bold ${config.color}`}>
                          {Math.round(rec.win_probability)}%
                        </span>
                      </div>
                      <div className="relative h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`absolute top-0 left-0 h-full ${config.progressColor} transition-all`}
                          style={{ width: `${rec.win_probability}%` }}
                        />
                      </div>
                    </div>

                    {/* Reasoning */}
                    <div className="pt-3 border-t border-border/50">
                      <p className="text-xs text-muted-foreground leading-relaxed">
                        {rec.reasoning}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <Target className="h-12 w-12 mx-auto mb-2 opacity-20" />
            <p className="text-sm">Нема достапни препораки за овој тендер</p>
          </div>
        )}

        {/* Market Analysis */}
        {marketAnalysis && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">📊</span>
              <h3 className="font-semibold">ПАЗАРНА АНАЛИЗА</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-background border">
                <div className="flex items-center gap-2 mb-1">
                  <Percent className="h-4 w-4 text-primary" />
                  <p className="text-xs text-muted-foreground">Просечен попуст</p>
                </div>
                <p className="text-lg font-bold">{marketAnalysis.avg_discount.toFixed(1)}%</p>
              </div>
              <div className="p-3 rounded-lg bg-background border">
                <div className="flex items-center gap-2 mb-1">
                  <Users className="h-4 w-4 text-primary" />
                  <p className="text-xs text-muted-foreground">Типични понудувачи</p>
                </div>
                <p className="text-lg font-bold">{marketAnalysis.typical_bidders}</p>
              </div>
              <div className="p-3 rounded-lg bg-background border">
                <div className="flex items-center gap-2 mb-1">
                  {getTrendIcon(marketAnalysis.price_trend)}
                  <p className="text-xs text-muted-foreground">Тренд</p>
                </div>
                <p className="text-lg font-bold capitalize">
                  {marketAnalysis.price_trend === "increasing" ? "Раст" :
                   marketAnalysis.price_trend === "decreasing" ? "Пад" : "Стабилен"}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Competitor Insights */}
        {competitorInsights && competitorInsights.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xl">🏢</span>
              <h3 className="font-semibold">ТОП КОНКУРЕНТИ</h3>
            </div>
            <div className="space-y-2">
              {competitorInsights.slice(0, 3).map((competitor, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg bg-background border flex items-center justify-between"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      {idx === 0 && <Trophy className="h-4 w-4 text-yellow-500" />}
                      <Building2 className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div>
                      <p className="text-sm font-medium">{competitor.company}</p>
                      <p className="text-xs text-muted-foreground">
                        {competitor.win_rate.toFixed(0)}% победи • {competitor.avg_discount.toFixed(0)}% просечен попуст
                      </p>
                    </div>
                  </div>
                  <Badge variant={idx === 0 ? "default" : "secondary"} className="text-xs">
                    #{idx + 1}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Disclaimer */}
        <div className="text-xs text-muted-foreground text-center pt-2 border-t">
          <p>
            Препораките се базирани на историски податоци и не гарантираат успех.
            Секогаш земајте ги предвид специфичните барања на тендерот.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
