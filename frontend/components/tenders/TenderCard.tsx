import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatCurrency, formatDate } from "@/lib/utils";
import { Calendar, Building2, Tag, ExternalLink, Clock } from "lucide-react";
import type { Tender } from "@/lib/api";
import Link from "next/link";

interface TenderCardProps {
  tender: Tender;
  onViewDetails?: (tenderId: string) => void;
}

export function TenderCard({ tender, onViewDetails }: TenderCardProps) {
  const getStatusVariant = (status?: string) => {
    switch (status?.toLowerCase()) {
      case "open":
        return "success";
      case "closed":
        return "secondary";
      case "awarded":
        return "default";
      default:
        return "outline";
    }
  };

  const tenderPath = encodeURIComponent(tender.tender_id);
  const sourceUrl = tender.source_url;

  return (
    <Card className="hover:bg-accent/50 transition-colors">
      <CardContent className="p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 space-y-3">
            {/* Title */}
            <div>
              <Link
                href={`/tenders/${tenderPath}`}
                className="font-semibold text-lg hover:text-primary transition-colors"
              >
                {tender.title}
              </Link>
              {tender.status && (
                <Badge variant={getStatusVariant(tender.status)} className="ml-2">
                  {tender.status}
                </Badge>
              )}
            </div>

            {/* Description */}
            {tender.description && (
              <p className="text-sm text-muted-foreground line-clamp-2">
                {tender.description}
              </p>
            )}

            {/* Meta Info */}
            <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
              {tender.procuring_entity && (
                <div className="flex items-center gap-1">
                  <Building2 className="h-4 w-4" />
                  <span>{tender.procuring_entity}</span>
                </div>
              )}
              {tender.estimated_value_mkd && (
                <div className="flex items-center gap-1 font-medium text-foreground">
                  <Tag className="h-4 w-4" />
                  <span>{formatCurrency(tender.estimated_value_mkd)}</span>
                </div>
              )}
              {tender.closing_date && (
                <div className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  <span>Рок: {formatDate(tender.closing_date)}</span>
                </div>
              )}
            </div>

            {/* Tags */}
            <div className="flex flex-wrap gap-2">
              {tender.category && (
                <Badge variant="outline" className="text-xs">
                  {tender.category}
                </Badge>
              )}
              {tender.cpv_code && (
                <Badge variant="outline" className="text-xs">
                  CPV: {tender.cpv_code}
                </Badge>
              )}
            </div>

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
