"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Star, StarOff, Loader2, TrendingUp, Award } from "lucide-react";

interface CompetitorCardProps {
  name: string;
  wins?: number;
  bidsCount?: number;
  winRate?: number;
  totalValueMkd?: number;
  isTracked: boolean;
  onToggleTrack: (name: string) => void;
  isLoading?: boolean;
  rank?: number;
  onClick?: () => void;
}

export function CompetitorCard({
  name,
  wins = 0,
  bidsCount = 0,
  winRate,
  totalValueMkd = 0,
  isTracked,
  onToggleTrack,
  isLoading = false,
  rank,
  onClick,
}: CompetitorCardProps) {
  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {rank !== undefined && (
              <div className="flex items-center justify-center w-8 h-8 rounded-full bg-muted text-sm font-medium flex-shrink-0">
                {rank}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <CardTitle
                  className={`text-base truncate ${onClick ? 'cursor-pointer hover:text-primary' : ''}`}
                  onClick={onClick}
                >
                  {name}
                </CardTitle>
                {isTracked && (
                  <Badge variant="secondary" className="text-xs flex-shrink-0">
                    <Star className="h-3 w-3 mr-1 fill-yellow-500 text-yellow-500" />
                    Следена
                  </Badge>
                )}
              </div>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onToggleTrack(name)}
            disabled={isLoading}
            title={isTracked ? "Отстрани од следење" : "Следи компанија"}
            className="flex-shrink-0"
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : isTracked ? (
              <Star className="h-5 w-5 fill-yellow-500 text-yellow-500" />
            ) : (
              <StarOff className="h-5 w-5 text-muted-foreground" />
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-1 text-muted-foreground text-xs">
              <Award className="h-3 w-3" />
              <span>Победи</span>
            </div>
            <p className="text-lg font-bold text-green-600">{wins}</p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-1 text-muted-foreground text-xs">
              <TrendingUp className="h-3 w-3" />
              <span>Понуди</span>
            </div>
            <p className="text-lg font-bold">{bidsCount}</p>
          </div>
        </div>

        {/* Win Rate */}
        {winRate !== undefined && (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Успешност</span>
              <span className="font-semibold">{winRate}%</span>
            </div>
            <div className="w-full bg-muted rounded-full h-2">
              <div
                className="bg-gradient-to-r from-green-500 to-emerald-600 h-2 rounded-full transition-all"
                style={{ width: `${Math.min(winRate, 100)}%` }}
              />
            </div>
          </div>
        )}

        {/* Total Value */}
        <div className="pt-2 border-t">
          <p className="text-xs text-muted-foreground">Вкупна вредност</p>
          <p className="font-semibold text-sm">
            {totalValueMkd.toLocaleString()} МКД
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
