"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  AlertCircle,
  Calendar,
  DollarSign,
  ExternalLink,
  Sparkles,
  Target,
  TrendingUp,
  Clock
} from "lucide-react";
import { BriefingTenderMatch } from "@/lib/api";
import Link from "next/link";
import { tenderUrl } from "@/lib/utils";

interface PriorityTendersProps {
  matches?: BriefingTenderMatch[];
}

export function PriorityTenders({ matches = [] }: PriorityTendersProps) {
  if (matches.length === 0) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Target className="w-5 h-5 text-orange-500" />
            Високо Приоритетни Совпаѓања
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Нема високо приоритетни совпаѓања за денес.</p>
            <p className="text-sm mt-2">
              Проверете ги вашите алерти и преференци за подобри совпаѓања.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Target className="w-5 h-5 text-orange-500" />
            Високо Приоритетни Совпаѓања
            <Badge variant="secondary" className="ml-2">
              {matches.length} нови
            </Badge>
          </CardTitle>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Тендери со висока релевантност за вашиот бизнис
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {matches.map((match, index) => (
            <PriorityTenderCard key={match.tender_id} match={match} rank={index + 1} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

interface PriorityTenderCardProps {
  match: BriefingTenderMatch;
  rank: number;
}

function PriorityTenderCard({ match, rank }: PriorityTenderCardProps) {
  const getUrgencyColor = (days?: number) => {
    if (!days) return "text-gray-500";
    if (days <= 3) return "text-red-600 dark:text-red-400";
    if (days <= 7) return "text-orange-600 dark:text-orange-400";
    return "text-green-600 dark:text-green-400";
  };

  const getMatchColor = (score: number) => {
    if (score >= 90) return "text-emerald-600 dark:text-emerald-400";
    if (score >= 75) return "text-green-600 dark:text-green-400";
    if (score >= 60) return "text-yellow-600 dark:text-yellow-400";
    return "text-orange-600 dark:text-orange-400";
  };

  const formatCurrency = (value?: number) => {
    if (!value) return "Нема податок";
    return new Intl.NumberFormat('mk-MK', {
      style: 'decimal',
      maximumFractionDigits: 0,
    }).format(value) + ' МКД';
  };

  return (
    <div className="border border-orange-200 dark:border-orange-800 rounded-lg p-4 bg-gradient-to-r from-orange-50/50 to-transparent dark:from-orange-950/20 dark:to-transparent hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4">
        {/* Rank Badge */}
        <div className="flex items-center justify-center w-10 h-10 rounded-full bg-gradient-to-br from-orange-500 to-red-500 text-primary-foreground font-bold text-lg flex-shrink-0">
          {rank}
        </div>

        {/* Content */}
        <div className="flex-1 space-y-3">
          {/* Title & Entity */}
          <div>
            <h3 className="font-semibold text-lg mb-1 leading-tight">
              {match.title}
            </h3>
            {match.procuring_entity && (
              <p className="text-sm text-muted-foreground">
                {match.procuring_entity}
              </p>
            )}
          </div>

          {/* Stats Row */}
          <div className="flex flex-wrap items-center gap-4 text-sm">
            {/* Budget */}
            {match.estimated_value_mkd && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <DollarSign className="w-4 h-4" />
                <span className="font-semibold text-foreground">
                  {formatCurrency(match.estimated_value_mkd)}
                </span>
              </div>
            )}

            {/* Days Remaining */}
            {match.days_remaining !== undefined && (
              <div className={`flex items-center gap-1 ${getUrgencyColor(match.days_remaining)}`}>
                <Clock className="w-4 h-4" />
                <span className="font-semibold">
                  {match.days_remaining} денови преостануваат
                </span>
              </div>
            )}

            {/* Match Score */}
            <div className={`flex items-center gap-1 ${getMatchColor(match.match_score)}`}>
              <Target className="w-4 h-4" />
              <span className="font-semibold">
                {match.match_score}% совпаѓање
              </span>
            </div>
          </div>

          {/* Progress Bar for Match Score */}
          <div className="space-y-1">
            <Progress
              value={match.match_score}
              className="h-2"
            />
          </div>

          {/* Match Reasons */}
          {match.match_reasons && match.match_reasons.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {match.match_reasons.map((reason, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {reason}
                </Badge>
              ))}
            </div>
          )}

          {/* AI Recommendation */}
          {match.ai_recommendation && (
            <div className="bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg p-3">
              <div className="flex items-start gap-2">
                <Sparkles className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                <p className="text-sm text-blue-900 dark:text-blue-100 italic">
                  {match.ai_recommendation}
                </p>
              </div>
            </div>
          )}

          {/* Alert Name */}
          {match.alert_name && (
            <div className="text-xs text-muted-foreground">
              Алерт: <span className="font-medium">{match.alert_name}</span>
            </div>
          )}
        </div>

        {/* Action Button */}
        <div className="flex-shrink-0">
          <Link href={tenderUrl(match.tender_id)}>
            <Button size="sm" className="gap-2">
              <span>Детали</span>
              <ExternalLink className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
