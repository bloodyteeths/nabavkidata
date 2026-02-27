"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, type Tender } from "@/lib/api";
import { formatCurrency, formatDate, tenderUrl } from "@/lib/utils";
import { Tag, Calendar, Building2, ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";

interface RelatedTendersProps {
  currentTenderId: string;
  cpvCode?: string;
  category?: string;
  limit?: number;
}

export function RelatedTenders({
  currentTenderId,
  cpvCode,
  category,
  limit = 5
}: RelatedTendersProps) {
  const [relatedTenders, setRelatedTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadRelatedTenders();
  }, [currentTenderId, cpvCode, category]);

  async function loadRelatedTenders() {
    try {
      setLoading(true);

      // Try to find tenders with same CPV code first, then same category
      const searchParams: any = {
        limit: limit + 1, // Get one extra to exclude current tender
        offset: 0
      };

      if (cpvCode) {
        searchParams.cpv_code = cpvCode;
      } else if (category) {
        searchParams.category = category;
      }

      const result = await api.searchTenders(searchParams);

      // Filter out the current tender and limit results
      const filtered = (result.items || [])
        .filter((t: Tender) => t.tender_id !== currentTenderId)
        .slice(0, limit);

      setRelatedTenders(filtered);
    } catch (error) {
      console.error("Failed to load related tenders:", error);
      setRelatedTenders([]);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-background">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Поврзани тендери
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 bg-muted/50 rounded-lg animate-pulse" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (relatedTenders.length === 0) {
    return null; // Don't show the section if there are no related tenders
  }

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-background">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          Поврзани тендери
        </CardTitle>
        <CardDescription>
          {cpvCode
            ? `Слични тендери со CPV код ${cpvCode}`
            : category
              ? `Тендери во категоријата ${category}`
              : "Слични тендери"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {relatedTenders.map((tender) => (
            <Link
              key={tender.tender_id}
              href={tenderUrl(tender.tender_id)}
              className="block"
            >
              <div className="p-4 rounded-lg border bg-card hover:bg-accent/50 transition-all duration-200 hover:border-primary/30">
                <div className="space-y-2">
                  {/* Title and Status */}
                  <div className="flex items-start justify-between gap-3">
                    <h4 className="text-sm font-semibold line-clamp-2 flex-1">
                      {tender.title}
                    </h4>
                    {tender.status && (
                      <Badge
                        variant={
                          tender.status.toLowerCase() === 'open' ? 'default' :
                          tender.status.toLowerCase() === 'awarded' ? 'secondary' :
                          'outline'
                        }
                        className="text-xs flex-shrink-0"
                      >
                        {tender.status === 'open' ? 'Отворен' :
                         tender.status === 'awarded' ? 'Доделен' :
                         tender.status === 'closed' ? 'Затворен' :
                         tender.status}
                      </Badge>
                    )}
                  </div>

                  {/* Meta info */}
                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                    {tender.procuring_entity && (
                      <div className="flex items-center gap-1">
                        <Building2 className="h-3 w-3" />
                        <span className="truncate max-w-[200px]">{tender.procuring_entity}</span>
                      </div>
                    )}
                    {tender.estimated_value_mkd && (
                      <div className="flex items-center gap-1">
                        <Tag className="h-3 w-3" />
                        <span className="font-medium">{formatCurrency(tender.estimated_value_mkd)}</span>
                      </div>
                    )}
                  </div>

                  {/* Date */}
                  {tender.closing_date && (
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Calendar className="h-3 w-3" />
                      <span>Краен рок: {formatDate(tender.closing_date)}</span>
                    </div>
                  )}

                  {/* Winner info for awarded tenders */}
                  {tender.winner && (
                    <div className="pt-2 border-t">
                      <p className="text-xs text-muted-foreground">
                        Добитник: <span className="font-medium text-foreground">{tender.winner}</span>
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </Link>
          ))}
        </div>

        {/* View More Link */}
        {cpvCode && (
          <div className="mt-4 pt-4 border-t">
            <Button asChild variant="outline" className="w-full group">
              <Link href={`/categories/${cpvCode}`}>
                Види ги сите во категоријата
                <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
              </Link>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
