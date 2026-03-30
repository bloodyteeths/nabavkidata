"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatDate, tenderUrl } from "@/lib/utils";
import { Calendar, Building2, ExternalLink, Trophy } from "lucide-react";
import type { Tender } from "@/lib/api";
import Link from "next/link";
import { AlertBellButton } from "@/components/alerts/AlertBellButton";

interface TenderCardProps {
  tender: Tender;
}

// Compute effective status based on closing_date
function getEffectiveStatus(status?: string, closingDate?: string): string {
  if (status === 'awarded' || status === 'cancelled') return status;
  if (status === 'open' && closingDate) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const closeDate = new Date(closingDate);
    closeDate.setHours(0, 0, 0, 0);
    if (closeDate < today) return 'closed';
  }
  return status || 'open';
}

// Always show a price — never leave it blank
function getPriceDisplay(tender: Tender): { label: string; value: string; highlight: boolean } {
  if (tender.actual_value_mkd) {
    return { label: 'Договор', value: formatCurrency(tender.actual_value_mkd), highlight: true };
  }
  if (tender.estimated_value_mkd) {
    return { label: 'Проценка', value: formatCurrency(tender.estimated_value_mkd), highlight: false };
  }
  return { label: 'Вредност', value: 'Нема податок', highlight: false };
}

export function TenderCard({ tender }: TenderCardProps) {
  const [effectiveStatus, setEffectiveStatus] = useState(tender.status || 'open');

  useEffect(() => {
    setEffectiveStatus(getEffectiveStatus(tender.status, tender.closing_date));
  }, [tender.status, tender.closing_date]);

  const getStatusVariant = (status?: string): "default" | "secondary" | "destructive" | "outline" => {
    switch (status?.toLowerCase()) {
      case "open": return "default";
      case "closed": return "secondary";
      case "awarded": return "outline";
      case "cancelled": return "destructive";
      default: return "outline";
    }
  };

  const getStatusLabel = (status?: string) => {
    switch (status?.toLowerCase()) {
      case "open": return "Отворен";
      case "closed": return "Затворен";
      case "awarded": return "Доделен";
      case "cancelled": return "Поништен";
      default: return status;
    }
  };

  const tenderPath = tenderUrl(tender.tender_id);
  const price = getPriceDisplay(tender);

  const getSourceUrl = (): string | undefined => {
    if (tender.dossier_id) {
      return `https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie-acpp/${tender.dossier_id}`;
    }
    if (tender.source_url?.includes('e-nabavki.gov.mk')) {
      return tender.source_url;
    }
    return undefined;
  };

  const sourceUrl = getSourceUrl();

  return (
    <Card className="hover:bg-accent/50 transition-colors">
      <CardContent className="p-4 sm:p-5">
        <div className="flex flex-col sm:flex-row items-start justify-between gap-3">
          <div className="flex-1 space-y-2 w-full min-w-0">
            {/* Title and Status */}
            <div className="flex items-start gap-2">
              <Link
                href={tenderPath}
                className="font-semibold text-base hover:text-primary transition-colors flex-1 min-w-0 line-clamp-2"
              >
                {tender.title}
              </Link>
              <Badge variant={getStatusVariant(effectiveStatus)} className="flex-shrink-0">
                {getStatusLabel(effectiveStatus)}
              </Badge>
            </div>

            {/* Winner — compact green line for awarded */}
            {tender.winner && (
              <div className="flex items-center gap-2 text-sm bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-md px-3 py-1.5">
                <Trophy className="h-4 w-4 text-green-600 dark:text-green-400 flex-shrink-0" aria-hidden="true" />
                <span className="font-medium text-green-800 dark:text-green-200 truncate">
                  {tender.winner}
                </span>
                {tender.actual_value_mkd && (
                  <span className="text-green-700 dark:text-green-300 flex-shrink-0">
                    — {formatCurrency(tender.actual_value_mkd)}
                  </span>
                )}
              </div>
            )}

            {/* Key info — institution, price, deadline */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
              {tender.procuring_entity && (
                <span className="flex items-center gap-1 truncate max-w-[250px]">
                  <Building2 className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
                  {tender.procuring_entity}
                </span>
              )}
              <span className={`flex items-center gap-1 ${price.highlight ? 'text-foreground font-semibold' : ''}`}>
                {price.label}: {price.value}
              </span>
              {tender.closing_date && (
                <span className="flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
                  Рок: {formatDate(tender.closing_date)}
                </span>
              )}
              {tender.category && (
                <Badge variant="outline" className="text-xs">
                  {tender.category}
                </Badge>
              )}
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-row sm:flex-col gap-2 w-full sm:w-auto">
            <Button size="sm" variant="default" asChild className="flex-1 sm:flex-none">
              <Link href={tenderPath}>Детали</Link>
            </Button>
            <AlertBellButton
              tenderId={tender.tender_id}
              cpvCode={tender.cpv_code}
              procuringEntity={tender.procuring_entity}
              title={tender.title}
            />
            {sourceUrl ? (
              <Button size="sm" variant="outline" asChild className="flex-1 sm:flex-none">
                <a href={sourceUrl} target="_blank" rel="noopener noreferrer" aria-label="Отвори на е-набавки" title="Отвори на е-набавки">
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                </a>
              </Button>
            ) : (
              <Button size="sm" variant="outline" disabled title="Нема изворна врска" aria-label="Нема изворна врска" className="flex-1 sm:flex-none">
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
