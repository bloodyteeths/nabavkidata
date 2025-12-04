"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Target, TrendingUp, TrendingDown, Users, Percent, Building2, Trophy, Sparkles } from "lucide-react";
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
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="h-4 w-4 text-primary" />
            AI Препорака за понуда
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="animate-pulse space-y-3">
            <div className="h-16 bg-muted rounded" />
            <div className="grid grid-cols-3 gap-3">
              <div className="h-24 bg-muted rounded" />
              <div className="h-24 bg-muted rounded" />
              <div className="h-24 bg-muted rounded" />
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
          label: "Агресивна",
          color: "text-red-600 dark:text-red-400",
          bgColor: "bg-red-50 dark:bg-red-950/30",
          borderColor: "border-red-200 dark:border-red-800",
          progressColor: "bg-red-500",
        };
      case "balanced":
        return {
          label: "Балансирана",
          color: "text-amber-600 dark:text-amber-400",
          bgColor: "bg-amber-50 dark:bg-amber-950/30",
          borderColor: "border-amber-200 dark:border-amber-800",
          progressColor: "bg-amber-500",
        };
      case "safe":
        return {
          label: "Сигурна",
          color: "text-green-600 dark:text-green-400",
          bgColor: "bg-green-50 dark:bg-green-950/30",
          borderColor: "border-green-200 dark:border-green-800",
          progressColor: "bg-green-500",
        };
      default:
        return {
          label: strategy,
          color: "text-muted-foreground",
          bgColor: "bg-muted",
          borderColor: "border",
          progressColor: "bg-muted-foreground",
        };
    }
  };

  const getTrendLabel = (trend: string) => {
    if (trend === "increasing") return "Раст";
    if (trend === "decreasing") return "Пад";
    return "Стабилен";
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary" />
          AI Препорака за понуда
        </CardTitle>
        <CardDescription className="text-xs">
          Анализа базирана на историски податоци од слични тендери
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* AI Summary - Compact */}
        {aiSummary && (
          <p className="text-sm text-muted-foreground leading-relaxed">
            {aiSummary}
          </p>
        )}

        {/* Recommendation Cards */}
        {sortedRecommendations.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {sortedRecommendations.map((rec) => {
              const config = getStrategyConfig(rec.strategy);
              const discountPercent = estimatedValue
                ? ((estimatedValue - rec.recommended_bid) / estimatedValue) * 100
                : 0;

              return (
                <div
                  key={rec.strategy}
                  className={`p-3 rounded-lg border ${config.bgColor} ${config.borderColor}`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className={`text-xs font-semibold ${config.color}`}>
                      {config.label}
                    </span>
                    <span className={`text-xs font-medium ${config.color}`}>
                      {Math.round(rec.win_probability)}% шанса
                    </span>
                  </div>
                  <p className="text-lg font-bold">{formatCurrency(rec.recommended_bid)}</p>
                  {estimatedValue && (
                    <p className="text-xs text-muted-foreground">
                      {discountPercent > 0 ? "-" : "+"}{Math.abs(discountPercent).toFixed(0)}% од процена
                    </p>
                  )}
                  <div className="mt-2 h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className={`h-full ${config.progressColor} transition-all`}
                      style={{ width: `${rec.win_probability}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}

        {/* Market Stats - Inline */}
        {marketAnalysis && (
          <div className="flex flex-wrap items-center gap-4 text-sm pt-2 border-t">
            <div className="flex items-center gap-1.5">
              <Users className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-muted-foreground">Понудувачи:</span>
              <span className="font-medium">{marketAnalysis.typical_bidders}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Percent className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-muted-foreground">Попуст:</span>
              <span className="font-medium">{marketAnalysis.avg_discount.toFixed(1)}%</span>
            </div>
            <div className="flex items-center gap-1.5">
              {marketAnalysis.price_trend === "increasing" ? (
                <TrendingUp className="h-3.5 w-3.5 text-red-500" />
              ) : marketAnalysis.price_trend === "decreasing" ? (
                <TrendingDown className="h-3.5 w-3.5 text-green-500" />
              ) : (
                <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
              )}
              <span className="text-muted-foreground">Тренд:</span>
              <span className="font-medium">{getTrendLabel(marketAnalysis.price_trend)}</span>
            </div>
          </div>
        )}

        {/* Competitor Insights - Compact */}
        {competitorInsights && competitorInsights.length > 0 && (
          <div className="pt-2 border-t">
            <p className="text-xs text-muted-foreground mb-2">Топ конкуренти:</p>
            <div className="flex flex-wrap gap-2">
              {competitorInsights.slice(0, 3).map((competitor, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {idx === 0 && <Trophy className="h-3 w-3 mr-1 text-amber-500" />}
                  {competitor.company} ({competitor.win_rate.toFixed(0)}%)
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
