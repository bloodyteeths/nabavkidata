import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Calendar, Building2, Tag, ExternalLink, Clock, User, Mail, Phone, Trophy, FileText } from "lucide-react";
import type { Tender } from "@/lib/api";
import Link from "next/link";

interface TenderCardProps {
  tender: Tender;
  onViewDetails?: (tenderId: string) => void;
}

export function TenderCard({ tender, onViewDetails }: TenderCardProps) {
  const getStatusVariant = (status?: string): "default" | "secondary" | "destructive" | "outline" => {
    switch (status?.toLowerCase()) {
      case "open":
        return "default"; // Blue/primary color for active tenders
      case "closed":
        return "secondary"; // Gray for closed tenders
      case "awarded":
        return "outline"; // Outline for awarded
      case "cancelled":
        return "destructive"; // Red for cancelled
      default:
        return "outline";
    }
  };

  const getStatusLabel = (status?: string) => {
    switch (status?.toLowerCase()) {
      case "open":
        return "Отворен";
      case "closed":
        return "Затворен";
      case "awarded":
        return "Доделен";
      case "cancelled":
        return "Поништен";
      default:
        return status;
    }
  };

  const getProcedureTypeVariant = (procedureType?: string): "default" | "secondary" | "outline" => {
    if (!procedureType) return "outline";
    const lower = procedureType.toLowerCase();
    if (lower.includes("отворен")) return "default";
    if (lower.includes("ограничен")) return "secondary";
    return "outline";
  };

  const tenderPath = encodeURIComponent(tender.tender_id);
  const sourceUrl = tender.source_url;

  return (
    <Card className="hover:bg-accent/50 transition-colors">
      <CardContent className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-3">
            {/* Title and Status */}
            <div className="flex items-start gap-2 flex-wrap">
              <Link
                href={`/tenders/${tenderPath}`}
                className="font-semibold text-lg hover:text-primary transition-colors flex-1 min-w-0"
              >
                {tender.title}
              </Link>
              <div className="flex items-center gap-2 flex-wrap">
                {tender.status && (
                  <Badge variant={getStatusVariant(tender.status)}>
                    {getStatusLabel(tender.status)}
                  </Badge>
                )}
                {tender.procedure_type && (
                  <Badge variant={getProcedureTypeVariant(tender.procedure_type)}>
                    {tender.procedure_type}
                  </Badge>
                )}
              </div>
            </div>

            {/* Description */}
            {tender.description && (
              <p className="text-sm text-muted-foreground line-clamp-2">
                {tender.description}
              </p>
            )}

            {/* Winner Section for Awarded Contracts - Prominent Display */}
            {tender.winner && (
              <div className="p-3 bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 rounded-md">
                <div className="flex items-center gap-2 mb-2">
                  <Trophy className="h-5 w-5 text-green-600 dark:text-green-400" />
                  <span className="font-semibold text-green-800 dark:text-green-300">Добитник на договор</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-green-700/70 dark:text-green-400/70">Компанија</span>
                    <span className="font-semibold text-green-900 dark:text-green-200">
                      {tender.winner}
                    </span>
                  </div>
                  {tender.actual_value_mkd && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-green-700/70 dark:text-green-400/70">Вредност на договор</span>
                      <span className="font-semibold text-green-900 dark:text-green-200">
                        {formatCurrency(tender.actual_value_mkd)}
                      </span>
                    </div>
                  )}
                  {tender.contract_signing_date && (
                    <div className="flex flex-col gap-1">
                      <span className="text-xs text-green-700/70 dark:text-green-400/70">Датум на договор</span>
                      <span className="font-medium text-green-900 dark:text-green-200">
                        {formatDate(tender.contract_signing_date)}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Key Procurement Data - Highlighted */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 p-3 bg-muted/30 rounded-md">
              {/* Estimated Value */}
              {tender.estimated_value_mkd && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground">Проценета вредност</span>
                  <span className="font-semibold text-foreground">
                    {formatCurrency(tender.estimated_value_mkd)}
                  </span>
                </div>
              )}

              {/* Actual Contract Value (if available and no winner section) */}
              {tender.actual_value_mkd && !tender.winner && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground">Вредност на договор</span>
                  <span className="font-semibold text-foreground">
                    {formatCurrency(tender.actual_value_mkd)}
                  </span>
                </div>
              )}

              {/* CPV Code */}
              {tender.cpv_code && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground">CPV Код</span>
                  <span className="font-medium text-foreground font-mono text-sm">
                    {tender.cpv_code}
                  </span>
                </div>
              )}

              {/* Number of Bidders */}
              {tender.num_bidders !== undefined && tender.num_bidders > 0 && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground">Понудувачи</span>
                  <span className="font-semibold text-foreground">
                    {tender.num_bidders} {tender.num_bidders === 1 ? 'понудувач' : 'понудувачи'}
                  </span>
                </div>
              )}

              {/* Contract Signing Date (if available and no winner section) */}
              {tender.contract_signing_date && !tender.winner && (
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-muted-foreground">Датум на договор</span>
                  <span className="font-medium text-foreground">
                    {formatDate(tender.contract_signing_date)}
                  </span>
                </div>
              )}
            </div>

            {/* Meta Info */}
            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
              {tender.procuring_entity && (
                <div className="flex items-center gap-1">
                  <Building2 className="h-4 w-4" />
                  <span className="truncate max-w-xs">{tender.procuring_entity}</span>
                </div>
              )}
              {tender.closing_date && (
                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  <span>Краен рок: {formatDate(tender.closing_date)}</span>
                </div>
              )}
            </div>

            {/* Contact Information */}
            {(tender.contact_person || tender.contact_email || tender.contact_phone) && (
              <div className="flex flex-wrap gap-4 text-sm text-muted-foreground border-t pt-3 mt-1">
                {tender.contact_person && (
                  <div className="flex items-center gap-1">
                    <User className="h-4 w-4" />
                    <span>{tender.contact_person}</span>
                  </div>
                )}
                {tender.contact_email && (
                  <div className="flex items-center gap-1">
                    <Mail className="h-4 w-4" />
                    <a href={`mailto:${tender.contact_email}`} className="hover:text-primary">
                      {tender.contact_email}
                    </a>
                  </div>
                )}
                {tender.contact_phone && (
                  <div className="flex items-center gap-1">
                    <Phone className="h-4 w-4" />
                    <a href={`tel:${tender.contact_phone}`} className="hover:text-primary">
                      {tender.contact_phone}
                    </a>
                  </div>
                )}
              </div>
            )}

            {/* Additional Tags */}
            {(tender.category || tender.evaluation_method) && (
              <div className="flex flex-wrap gap-2">
                {tender.category && (
                  <Badge variant="outline" className="text-xs">
                    {tender.category}
                  </Badge>
                )}
                {tender.evaluation_method && (
                  <Badge variant="outline" className="text-xs">
                    {tender.evaluation_method}
                  </Badge>
                )}
              </div>
            )}

            {/* Last Updated */}
            {tender.created_at && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                <span>Последно ажурирано: {formatDate(tender.created_at)}</span>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-2">
            <Button
              size="sm"
              variant="default"
              asChild
            >
              <Link href={`/tenders/${tenderPath}`}>
                Детали
              </Link>
            </Button>
            {sourceUrl ? (
              <Button size="sm" variant="outline" asChild>
                <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
            ) : (
              <Button size="sm" variant="outline" disabled title="Нема изворна врска">
                <ExternalLink className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
