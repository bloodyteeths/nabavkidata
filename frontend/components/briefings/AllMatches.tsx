"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ChevronDown,
  ChevronUp,
  List,
  Target,
  ExternalLink,
  DollarSign,
  Calendar,
  AlertCircle,
} from "lucide-react";
import { BriefingTenderMatch } from "@/lib/api";
import Link from "next/link";
import { formatCurrency as formatCurrencyUtil, formatDate as formatDateUtil } from "@/lib/utils";

interface AllMatchesProps {
  matches?: BriefingTenderMatch[];
}

export function AllMatches({ matches = [] }: AllMatchesProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Group matches by alert name
  const groupedMatches = matches.reduce((acc, match) => {
    const alertName = match.alert_name || "Општи Совпаѓања";
    if (!acc[alertName]) {
      acc[alertName] = [];
    }
    acc[alertName].push(match);
    return acc;
  }, {} as Record<string, BriefingTenderMatch[]>);

  const alertNames = Object.keys(groupedMatches);

  if (matches.length === 0) {
    return (
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <List className="w-5 h-5" />
            Сите Совпаѓања
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <AlertCircle className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>Нема совпаѓања за денес.</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="mb-6">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <List className="w-5 h-5" />
              Сите Совпаѓања
              <Badge variant="secondary" className="ml-2">
                {matches.length} вкупно
              </Badge>
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Групирани по ваши алерти
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="gap-2"
          >
            {isExpanded ? (
              <>
                <ChevronUp className="w-4 h-4" />
                Затвори
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4" />
                Прошири
              </>
            )}
          </Button>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent>
          <div className="space-y-6">
            {alertNames.map((alertName) => (
              <AlertGroup
                key={alertName}
                alertName={alertName}
                matches={groupedMatches[alertName]}
              />
            ))}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

interface AlertGroupProps {
  alertName: string;
  matches: BriefingTenderMatch[];
}

function AlertGroup({ alertName, matches }: AlertGroupProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border rounded-lg overflow-hidden">
      {/* Group Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-muted/50 hover:bg-muted transition-colors"
      >
        <div className="flex items-center gap-3">
          <Target className="w-5 h-5 text-blue-500" />
          <div className="text-left">
            <h3 className="font-semibold">{alertName}</h3>
            <p className="text-xs text-muted-foreground">
              {matches.length} {matches.length === 1 ? "совпаѓање" : "совпаѓања"}
            </p>
          </div>
        </div>
        {isExpanded ? (
          <ChevronUp className="w-5 h-5 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-5 h-5 text-muted-foreground" />
        )}
      </button>

      {/* Group Content */}
      {isExpanded && (
        <div className="divide-y">
          {matches.map((match) => (
            <MatchRow key={match.tender_id} match={match} />
          ))}
        </div>
      )}
    </div>
  );
}

interface MatchRowProps {
  match: BriefingTenderMatch;
}

function MatchRow({ match }: MatchRowProps) {
  const getScoreColor = (score: number) => {
    if (score >= 90) return "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400";
    if (score >= 75) return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
    if (score >= 60) return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400";
    return "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400";
  };

  const formatCurrency = (value?: number) => {
    if (!value) return "Нема податок";
    return formatCurrencyUtil(value);
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return null;
    return formatDateUtil(dateStr);
  };

  return (
    <div className="p-4 hover:bg-muted/30 transition-colors">
      <div className="flex items-start justify-between gap-4">
        {/* Content */}
        <div className="flex-1 space-y-2">
          {/* Title */}
          <Link
            href={`/tenders/${match.tender_id}`}
            className="font-medium hover:text-primary transition-colors"
          >
            {match.title}
          </Link>

          {/* Entity */}
          {match.procuring_entity && (
            <p className="text-sm text-muted-foreground">
              {match.procuring_entity}
            </p>
          )}

          {/* Info Row */}
          <div className="flex flex-wrap items-center gap-3 text-sm">
            {/* Budget */}
            {match.estimated_value_mkd && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <DollarSign className="w-3 h-3" />
                <span>{formatCurrency(match.estimated_value_mkd)}</span>
              </div>
            )}

            {/* Closing Date */}
            {match.closing_date && (
              <div className="flex items-center gap-1 text-muted-foreground">
                <Calendar className="w-3 h-3" />
                <span>{formatDate(match.closing_date)}</span>
              </div>
            )}

            {/* Category */}
            {match.category && (
              <Badge variant="outline" className="text-xs">
                {match.category}
              </Badge>
            )}
          </div>

          {/* Match Reasons */}
          {match.match_reasons && match.match_reasons.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {match.match_reasons.map((reason, idx) => (
                <Badge key={idx} variant="secondary" className="text-xs">
                  {reason}
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Score & Action */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Match Score Badge */}
          <div className={`px-3 py-1 rounded-full text-sm font-semibold ${getScoreColor(match.match_score)}`}>
            {match.match_score}%
          </div>

          {/* View Button */}
          <Link href={`/tenders/${match.tender_id}`}>
            <Button size="sm" variant="ghost">
              <ExternalLink className="w-4 h-4" />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
