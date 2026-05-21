"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TenderCard } from "@/components/tenders/TenderCard";
import { api, type Tender } from "@/lib/api";
import {
  ArrowLeft,
  ArrowRight,
  Tag,
  TrendingUp,
  FileText,
  Building2,
} from "lucide-react";
import Link from "next/link";
import { formatCurrency } from "@/lib/utils";
import { Breadcrumb } from "@/components/Breadcrumb";

interface SectorClientProps {
  sectorSlug: string;
  sectorName: string;
  searchQuery: string;
}

export default function SectorClient({
  sectorSlug,
  sectorName,
  searchQuery,
}: SectorClientProps) {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    loadTenders();
  }, [searchQuery]);

  async function loadTenders() {
    setLoading(true);
    try {
      const keywords = searchQuery.split(" ").slice(0, 3);
      const result = await api.getTenders({
        search: keywords.join(" "),
        limit: 20,
        offset: 0,
      });
      setTenders(result.items || []);
      setTotal(result.total || 0);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }

  const activeTenders = tenders.filter(
    (t) => t.status?.toLowerCase() === "open"
  ).length;
  const totalValue = tenders.reduce(
    (sum, t) => sum + (t.estimated_value_mkd || 0),
    0
  );

  return (
    <div className="container mx-auto py-8 px-4">
      <Breadcrumb
        items={[{ label: "Тендери", href: "/tenders" }]}
        currentPage={sectorName}
      />

      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Tag className="h-8 w-8 text-primary" />
          <h1 className="text-3xl md:text-4xl font-bold">{sectorName}</h1>
        </div>
        <p className="text-muted-foreground">
          Тендери и јавни набавки во секторот {sectorName.toLowerCase()} во
          Македонија.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Вкупно тендери</p>
                <p className="text-2xl font-bold">{total}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <TrendingUp className="h-8 w-8 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Активни</p>
                <p className="text-2xl font-bold text-green-600">
                  {activeTenders}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Building2 className="h-8 w-8 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Вкупна вредност</p>
                <p className="text-xl font-bold">
                  {formatCurrency(totalValue)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Последни тендери</h2>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center gap-2">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
              <span>Се вчитува...</span>
            </div>
          </div>
        ) : tenders.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Tag className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
              <p className="text-muted-foreground">
                Нема пронајдени тендери во овој сектор.
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="space-y-4">
              {tenders.map((tender) => (
                <TenderCard key={tender.tender_id} tender={tender} />
              ))}
            </div>

            <div className="flex justify-center pt-4">
              <Link
                href={`/tenders?search=${encodeURIComponent(searchQuery.split(" ")[0])}`}
              >
                <Button variant="outline">
                  Види ги сите тендери за {sectorName.toLowerCase()}
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </div>
          </>
        )}
      </div>

      <Card className="mt-8 bg-primary/5 border-primary/20">
        <CardContent className="py-6 text-center">
          <h3 className="font-semibold text-lg mb-2">
            Добивајте известувања за нови тендери
          </h3>
          <p className="text-muted-foreground text-sm mb-4">
            Поставете алерт за секторот {sectorName.toLowerCase()} и добивајте
            мејл штом излезе нов тендер.
          </p>
          <Link href="/auth/register">
            <Button>
              Регистрирајте се бесплатно
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
