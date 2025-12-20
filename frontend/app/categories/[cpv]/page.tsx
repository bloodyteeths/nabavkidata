"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TenderCard } from "@/components/tenders/TenderCard";
import { api, type Tender } from "@/lib/api";
import { ArrowLeft, Tag, TrendingUp, Building2, Calendar } from "lucide-react";
import Link from "next/link";
import { formatCurrency } from "@/lib/utils";

// CPV Code to Macedonian name mapping (common categories)
const CPV_CATEGORIES: Record<string, string> = {
  "45000000": "Градежни работи",
  "30000000": "Канцелариска и компјутерска опрема",
  "31000000": "Електрична опрема и апарати",
  "32000000": "Радио, телевизиска, комуникациска и телекомуникациска опрема",
  "33000000": "Медицинска опрема",
  "34000000": "Транспортна опрема",
  "35000000": "Безбедносна опрема",
  "39000000": "Мебел, подни и други покривки",
  "44000000": "Конструкциски материјали",
  "48000000": "Софтверски пакети и информациски системи",
  "50000000": "Услуги за поправка и одржување",
  "60000000": "Транспортни услуги",
  "70000000": "Услуги поврзани со недвижен имот",
  "71000000": "Архитектонски, инженерски и градежни услуги",
  "72000000": "ИТ услуги",
  "73000000": "Истражување и развој",
  "75000000": "Јавна администрација",
  "76000000": "Услуги поврзани со нафтена и гасна индустрија",
  "77000000": "Услуги поврзани со земјоделство, шумарство и рибарство",
  "79000000": "Деловни услуги",
  "80000000": "Образовни и обучни услуги",
  "85000000": "Здравствени и социјални услуги",
  "90000000": "Услуги за отстранување на отпад и канализација",
  "92000000": "Рекреативни, културни и спортски услуги",
  "98000000": "Други услуги",
};

interface CategoryStats {
  total_tenders: number;
  avg_value_mkd: number;
  total_value_mkd: number;
  active_tenders: number;
}

export default function CPVCategoryPage() {
  const params = useParams();
  const cpvCode = params?.cpv ? decodeURIComponent(params.cpv as string) : null;

  const [tenders, setTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<CategoryStats | null>(null);

  const categoryName = cpvCode ? (CPV_CATEGORIES[cpvCode] || `CPV ${cpvCode}`) : "Непозната категорија";

  useEffect(() => {
    if (!cpvCode) return;
    loadCategoryTenders();
  }, [cpvCode]);

  async function loadCategoryTenders() {
    if (!cpvCode) return;
    try {
      setLoading(true);
      // Search for tenders with this CPV code
      const result = await api.searchTenders({
        cpv_code: cpvCode,
        limit: 20,
        offset: 0
      });

      setTenders(result.items || []);

      // Calculate stats
      const totalTenders = result.items?.length || 0;
      const activeTenders = result.items?.filter((t: Tender) => t.status?.toLowerCase() === 'open').length || 0;
      const totalValue = result.items?.reduce((sum: number, t: Tender) => sum + (t.estimated_value_mkd || 0), 0) || 0;
      const avgValue = totalTenders > 0 ? totalValue / totalTenders : 0;

      setStats({
        total_tenders: totalTenders,
        avg_value_mkd: avgValue,
        total_value_mkd: totalValue,
        active_tenders: activeTenders
      });
    } catch (error) {
      console.error("Failed to load category tenders:", error);
    } finally {
      setLoading(false);
    }
  }

  if (!cpvCode) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Категоријата не е пронајдена</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* JSON-LD Schema for Category */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": `${categoryName} - Јавни набавки`,
            "description": `Тендери и јавни набавки во категоријата ${categoryName} (CPV ${cpvCode}) во Република Македонија`,
            "url": `https://nabavkidata.com/categories/${cpvCode}`,
            "breadcrumb": {
              "@type": "BreadcrumbList",
              "itemListElement": [
                {
                  "@type": "ListItem",
                  "position": 1,
                  "name": "Почетна",
                  "item": "https://nabavkidata.com"
                },
                {
                  "@type": "ListItem",
                  "position": 2,
                  "name": "Категории",
                  "item": "https://nabavkidata.com/categories"
                },
                {
                  "@type": "ListItem",
                  "position": 3,
                  "name": categoryName,
                  "item": `https://nabavkidata.com/categories/${cpvCode}`
                }
              ]
            },
            "inLanguage": "mk",
            "about": {
              "@type": "Thing",
              "name": categoryName,
              "identifier": cpvCode
            }
          })
        }}
      />

      <div className="p-4 md:p-8 space-y-6">
        {/* Header */}
        <div className="flex flex-col gap-4">
          <Button asChild variant="ghost" size="sm" className="w-fit pl-0 hover:bg-transparent">
            <Link href="/tenders" className="flex items-center text-muted-foreground hover:text-foreground">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Назад на тендери
            </Link>
          </Button>

          <div>
            <div className="flex items-center gap-3 mb-2">
              <Tag className="h-8 w-8 text-primary" />
              <h1 className="text-3xl md:text-4xl font-bold">{categoryName}</h1>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="font-mono">CPV {cpvCode}</Badge>
              {stats && stats.active_tenders > 0 && (
                <Badge variant="default">{stats.active_tenders} активни тендери</Badge>
              )}
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <Calendar className="h-4 w-4" />
                  ВКУПНО ТЕНДЕРИ
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold">{stats.total_tenders}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <TrendingUp className="h-4 w-4" />
                  АКТИВНИ
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold text-green-600">{stats.active_tenders}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <Tag className="h-4 w-4" />
                  ПРОСЕЧНА ВРЕДНОСТ
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-lg font-bold">{formatCurrency(stats.avg_value_mkd)}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                  <Building2 className="h-4 w-4" />
                  ВКУПНА ВРЕДНОСТ
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-lg font-bold text-primary">{formatCurrency(stats.total_value_mkd)}</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Category Description */}
        <Card>
          <CardHeader>
            <CardTitle>За категоријата</CardTitle>
            <CardDescription>
              CPV код {cpvCode} ги вклучува сите јавни набавки поврзани со {categoryName.toLowerCase()} во Република Македонија.
              Оваа категорија ги опфаќа тендерите објавени на платформата за е-набавки.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>
                На оваа страница можете да ги прегледате сите тендери класифицирани под CPV код {cpvCode}.
                Користете ги филтрите за да ги најдете тендерите што одговараат на вашите потреби.
              </p>
              <p>
                CPV (Common Procurement Vocabulary) кодот е стандарден класификациски систем користен во јавните набавки
                во Европската Унија и земјите кои го применуваат истиот систем.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Tenders List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold">Тендери во оваа категорија</h2>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-muted-foreground">Се вчитуваат тендери...</p>
            </div>
          ) : tenders.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Tag className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                <p className="text-muted-foreground">Нема пронајдени тендери во оваа категорија</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {tenders.map((tender) => (
                <TenderCard key={tender.tender_id} tender={tender} />
              ))}
            </div>
          )}

          {/* View All Link */}
          {!loading && tenders.length > 0 && (
            <div className="flex justify-center pt-4">
              <Button asChild variant="outline">
                <Link href={`/tenders?cpv_code=${cpvCode}`}>
                  Види ги сите тендери во оваа категорија
                </Link>
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
