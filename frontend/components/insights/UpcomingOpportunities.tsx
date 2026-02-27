"use client";

import React from "react";
import Link from "next/link";
import { Clock, AlertTriangle, Calendar, TrendingUp } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface TenderOpportunity {
  tender_id: string;
  title: string;
  estimated_value_mkd: number | null;
  closing_date: string;
  days_left: number;
  category: string | null;
  procuring_entity: string | null;
  cpv_code?: string | null;
}

interface UpcomingOpportunitiesData {
  closing_soon: TenderOpportunity[];
  closing_this_month: TenderOpportunity[];
  upcoming: TenderOpportunity[];
  total: number;
}

interface UpcomingOpportunitiesProps {
  cpvCode?: string;
}

export function UpcomingOpportunities({ cpvCode }: UpcomingOpportunitiesProps) {
  const [data, setData] = React.useState<UpcomingOpportunitiesData | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    async function fetchOpportunities() {
      try {
        setLoading(true);
        setError(null);
        const result = await api.getUpcomingOpportunities(cpvCode);
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load opportunities");
        console.error("Error fetching upcoming opportunities:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchOpportunities();
  }, [cpvCode]);

  const formatCurrency = (value: number): string => {
    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(1)}М`;
    } else if (value >= 1_000) {
      return `${(value / 1_000).toFixed(0)}К`;
    }
    return value.toLocaleString("mk-MK");
  };

  const renderTenderCard = (tender: TenderOpportunity) => (
    <Link
      key={tender.tender_id}
      href={`/tenders/${tender.tender_id}`}
      className="block group"
    >
      <Card className="hover:shadow-md transition-shadow duration-200 h-full">
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-3 mb-2">
            <h4 className="font-medium text-sm line-clamp-2 group-hover:text-primary transition-colors flex-1">
              {tender.title}
            </h4>
            <Badge variant="outline" className="shrink-0 text-xs">
              {tender.days_left}д
            </Badge>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-sm font-semibold text-foreground">
                {tender.estimated_value_mkd ? `${formatCurrency(tender.estimated_value_mkd)} МКД` : 'Н/Д'}
              </span>
            </div>

            {tender.category && (
              <Badge variant="secondary" className="text-xs">
                {tender.category}
              </Badge>
            )}

            <p className="text-xs text-muted-foreground line-clamp-1">
              {tender.procuring_entity}
            </p>
          </div>
        </CardContent>
      </Card>
    </Link>
  );

  const renderSection = (
    title: string,
    tenders: TenderOpportunity[],
    icon: React.ReactNode,
    variant: "destructive" | "warning" | "default"
  ) => {
    if (!tenders || tenders.length === 0) return null;

    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          {icon}
          <h3 className="font-semibold text-base">{title}</h3>
          <Badge variant={variant} className="ml-auto">
            {tenders.length}
          </Badge>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {tenders.map(renderTenderCard)}
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Следни можности
          </CardTitle>
          <CardDescription>Се вчитуваат можности...</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-3">
                <div className="h-6 bg-muted rounded animate-pulse w-32" />
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {[1, 2, 3].map((j) => (
                    <div key={j} className="h-32 bg-muted rounded-xl animate-pulse" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Следни можности
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <p className="text-muted-foreground">{error}</p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => window.location.reload()}
            >
              Обиди се повторно
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.total === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Следни можности
          </CardTitle>
          <CardDescription>Тендери што се затвораат наскоро</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8">
            <Calendar className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
            <p className="text-muted-foreground">Нема пронајдени можности</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calendar className="h-5 w-5" />
          Следни можности
        </CardTitle>
        <CardDescription>
          {data.total} тендер{data.total !== 1 ? "и" : ""} се затвораат во следните 30 дена
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {renderSection(
          "Итно (7 дена)",
          data.closing_soon,
          <AlertTriangle className="h-5 w-5 text-red-600" />,
          "destructive"
        )}

        {renderSection(
          "Скоро (14 дена)",
          data.closing_this_month,
          <Clock className="h-5 w-5 text-orange-600" />,
          "warning"
        )}

        {renderSection(
          "Во месецот",
          data.upcoming,
          <Calendar className="h-5 w-5 text-blue-600" />,
          "default"
        )}
      </CardContent>
    </Card>
  );
}

export default UpcomingOpportunities;
