"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { tenderIdFromParam, formatCurrency, formatDate } from "@/lib/utils";
import {
  Trophy,
  Building2,
  Calendar,
  Tag,
  Users,
  ArrowRight,
  Award,
  FileText,
} from "lucide-react";
import Link from "next/link";
import { SignupGate } from "@/components/SignupGate";

const API_URL = "https://api.nabavkidata.com";

interface AwardData {
  tender_id: string;
  title: string | null;
  description: string | null;
  procuring_entity: string | null;
  estimated_value_mkd: number | null;
  actual_value_mkd: number | null;
  winner: string | null;
  num_bidders: number | null;
  publication_date: string | null;
  closing_date: string | null;
  cpv_code: string | null;
  procedure_type: string | null;
  category: string | null;
}

export default function AwardDetailClient() {
  const params = useParams();
  const rawId = params?.id;
  const tenderId = rawId ? tenderIdFromParam(String(rawId)) : null;
  const paramId = rawId ? String(rawId) : "";

  const [award, setAward] = useState<AwardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tenderId) return;
    async function loadAward() {
      try {
        setLoading(true);
        const res = await fetch(
          `${API_URL}/api/seo/award/${encodeURIComponent(tenderId!)}`,
        );
        if (!res.ok) {
          setAward(null);
          return;
        }
        const data = await res.json();
        setAward(data);
      } catch {
        setAward(null);
      } finally {
        setLoading(false);
      }
    }
    loadAward();
  }, [tenderId]);

  if (!tenderId || loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <p className="text-muted-foreground">Се вчитува...</p>
      </div>
    );
  }

  if (!award) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[40vh] gap-4">
        <p className="text-muted-foreground">Доделената набавка не е пронајдена</p>
        <Button asChild variant="outline">
          <Link href="/tenders">Назад на тендери</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl space-y-6">
      {/* Award Banner */}
      <div className="rounded-xl border bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800 p-6">
        <div className="flex items-start gap-4">
          <div className="h-12 w-12 rounded-full bg-green-100 dark:bg-green-900 flex items-center justify-center shrink-0">
            <Trophy className="h-6 w-6 text-green-600" />
          </div>
          <div className="space-y-1">
            <Badge variant="default" className="bg-green-600 mb-2">Доделена набавка</Badge>
            <h1 className="text-xl md:text-2xl font-bold">
              {award.winner} ја доби набавката
            </h1>
            <p className="text-muted-foreground">{award.title || `Набавка ${award.tender_id}`}</p>
          </div>
        </div>
      </div>

      {/* Teaser Insights — visible to everyone */}
      <Card className="border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30">
        <CardContent className="py-5">
          <h2 className="font-semibold text-lg mb-3">Клучни увиди</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
            {award.winner && (
              <div className="flex items-start gap-2">
                <Trophy className="h-4 w-4 text-green-600 mt-0.5 shrink-0" />
                <span>
                  Победник: <strong>{award.winner}</strong>
                </span>
              </div>
            )}
            {(award.actual_value_mkd || award.estimated_value_mkd) && (
              <div className="flex items-start gap-2">
                <Tag className="h-4 w-4 text-blue-500 mt-0.5 shrink-0" />
                <span>
                  {award.actual_value_mkd ? 'Договорена' : 'Проценета'} вредност: <strong>{formatCurrency(award.actual_value_mkd || award.estimated_value_mkd || 0)}</strong>
                </span>
              </div>
            )}
            {award.num_bidders != null && award.num_bidders > 0 && (
              <div className="flex items-start gap-2">
                <Users className="h-4 w-4 text-purple-500 mt-0.5 shrink-0" />
                <span>
                  <strong>{award.num_bidders} компании</strong> поднеле понуда {award.num_bidders === 1 ? '— без конкуренција' : '— конкурентна постапка'}
                </span>
              </div>
            )}
            {award.procuring_entity && (
              <div className="flex items-start gap-2">
                <Building2 className="h-4 w-4 text-orange-500 mt-0.5 shrink-0" />
                <span>
                  Нарачувач: <strong>{award.procuring_entity}</strong>
                </span>
              </div>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            Регистрирајте се за целосни детали: документи, постапка, датуми и AI анализа на тендерот.
          </p>
        </CardContent>
      </Card>

      {/* Details Grid */}
      <SignupGate message="Регистрирајте се за да ги видите деталите, документи и AI анализа">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Procuring Entity */}
        {award.procuring_entity && (
          <Card>
            <CardContent className="flex items-start gap-3 pt-6">
              <Building2 className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Договорен орган</p>
                <p className="text-sm font-medium">{award.procuring_entity}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Winner */}
        <Card>
          <CardContent className="flex items-start gap-3 pt-6">
            <Trophy className="h-5 w-5 text-green-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-xs text-muted-foreground">Победник</p>
              <p className="text-sm font-semibold text-green-600">{award.winner}</p>
            </div>
          </CardContent>
        </Card>

        {/* Value */}
        {(award.actual_value_mkd || award.estimated_value_mkd) && (
          <Card>
            <CardContent className="flex items-start gap-3 pt-6">
              <Tag className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">
                  {award.actual_value_mkd ? "Договорена вредност" : "Проценета вредност"}
                </p>
                <p className="text-sm font-bold">
                  {formatCurrency(award.actual_value_mkd || award.estimated_value_mkd || 0)}
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Num Bidders */}
        {award.num_bidders && (
          <Card>
            <CardContent className="flex items-start gap-3 pt-6">
              <Users className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Број на понудувачи</p>
                <p className="text-sm font-medium">{award.num_bidders}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Publication Date */}
        {award.publication_date && (
          <Card>
            <CardContent className="flex items-start gap-3 pt-6">
              <Calendar className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Датум на објава</p>
                <p className="text-sm font-medium">{formatDate(award.publication_date)}</p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Procedure Type */}
        {award.procedure_type && (
          <Card>
            <CardContent className="flex items-start gap-3 pt-6">
              <FileText className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Тип на постапка</p>
                <Badge variant="secondary">{award.procedure_type}</Badge>
              </div>
            </CardContent>
          </Card>
        )}

        {/* CPV Code */}
        {award.cpv_code && (
          <Card>
            <CardContent className="flex items-start gap-3 pt-6">
              <Award className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">CPV Код</p>
                <p className="text-sm font-mono">{award.cpv_code}</p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Link to Full Tender Detail */}
      <Card className="border-primary/50">
        <CardContent className="flex items-center justify-between pt-6">
          <div>
            <p className="text-sm font-medium">Погледнете ги сите детали за овој тендер</p>
            <p className="text-xs text-muted-foreground">
              Документи, понудувачи, AI анализа и повеќе
            </p>
          </div>
          <Button asChild>
            <Link href={`/tenders/${paramId}`}>
              Отвори тендер
              <ArrowRight className="h-4 w-4 ml-2" />
            </Link>
          </Button>
        </CardContent>
      </Card>
      </SignupGate>
    </div>
  );
}
