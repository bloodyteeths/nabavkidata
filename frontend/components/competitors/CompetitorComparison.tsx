"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TrendingUp, Award, Target, DollarSign, X } from "lucide-react";

export interface CompetitorStats {
  name: string;
  wins: number;
  bidsCount: number;
  winRate: number;
  avgDiscount?: number;
  totalValueMkd: number;
  specialtyAreas?: string[];
}

interface CompetitorComparisonProps {
  competitors: CompetitorStats[];
  onRemoveCompetitor?: (name: string) => void;
}

export function CompetitorComparison({
  competitors,
  onRemoveCompetitor,
}: CompetitorComparisonProps) {
  if (competitors.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center text-muted-foreground">
          <div className="space-y-2">
            <TrendingUp className="h-12 w-12 mx-auto opacity-30" />
            <p className="text-lg font-medium">Споредба на конкуренти</p>
            <p className="text-sm">
              Следете компании за да ги споредите нивните перформанси
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Calculate max values for scaling bars
  const maxWins = Math.max(...competitors.map((c) => c.wins));
  const maxBids = Math.max(...competitors.map((c) => c.bidsCount));
  const maxValue = Math.max(...competitors.map((c) => c.totalValueMkd));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <TrendingUp className="h-5 w-5" />
          Споредба на конкуренти
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {competitors.map((competitor, idx) => (
            <Card key={idx} className="relative">
              {onRemoveCompetitor && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="absolute top-2 right-2 h-6 w-6"
                  onClick={() => onRemoveCompetitor(competitor.name)}
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
              <CardContent className="pt-6 space-y-4">
                {/* Company Name */}
                <div className="pr-8">
                  <h3 className="font-semibold text-sm truncate">
                    {competitor.name}
                  </h3>
                </div>

                {/* Win Rate Badge */}
                <div className="flex items-center justify-center">
                  <Badge
                    variant={
                      competitor.winRate >= 50
                        ? "default"
                        : competitor.winRate >= 30
                        ? "secondary"
                        : "outline"
                    }
                    className="text-lg font-bold py-1 px-3"
                  >
                    {competitor.winRate}% успешност
                  </Badge>
                </div>

                {/* Metrics with Visual Bars */}
                <div className="space-y-3">
                  {/* Wins */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <Award className="h-3 w-3" />
                        Победи
                      </span>
                      <span className="font-semibold">{competitor.wins}</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div
                        className="bg-gradient-to-r from-green-500 to-emerald-600 h-2 rounded-full transition-all"
                        style={{
                          width: `${maxWins > 0 ? (competitor.wins / maxWins) * 100 : 0}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Bids */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <Target className="h-3 w-3" />
                        Понуди
                      </span>
                      <span className="font-semibold">{competitor.bidsCount}</span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div
                        className="bg-gradient-to-r from-blue-500 to-cyan-600 h-2 rounded-full transition-all"
                        style={{
                          width: `${maxBids > 0 ? (competitor.bidsCount / maxBids) * 100 : 0}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Total Value */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1 text-muted-foreground">
                        <DollarSign className="h-3 w-3" />
                        Вкупна вредност
                      </span>
                      <span className="font-semibold">
                        {(competitor.totalValueMkd / 1_000_000).toFixed(1)}M
                      </span>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div
                        className="bg-gradient-to-r from-purple-500 to-pink-600 h-2 rounded-full transition-all"
                        style={{
                          width: `${
                            maxValue > 0
                              ? (competitor.totalValueMkd / maxValue) * 100
                              : 0
                          }%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Average Discount */}
                  {competitor.avgDiscount !== undefined && (
                    <div className="pt-2 border-t">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-muted-foreground">Просечен попуст</span>
                        <span className="font-semibold text-orange-600">
                          {competitor.avgDiscount.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Specialty Areas */}
                  {competitor.specialtyAreas && competitor.specialtyAreas.length > 0 && (
                    <div className="pt-2 border-t space-y-1">
                      <p className="text-xs text-muted-foreground">Специјалност</p>
                      <div className="flex flex-wrap gap-1">
                        {competitor.specialtyAreas.slice(0, 2).map((area, i) => (
                          <Badge key={i} variant="outline" className="text-xs">
                            {area.length > 20 ? area.substring(0, 20) + "..." : area}
                          </Badge>
                        ))}
                        {competitor.specialtyAreas.length > 2 && (
                          <Badge variant="outline" className="text-xs">
                            +{competitor.specialtyAreas.length - 2}
                          </Badge>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
