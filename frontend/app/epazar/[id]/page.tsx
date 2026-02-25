'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  ArrowLeft,
  Building2,
  Calendar,
  DollarSign,
  FileText,
  Package,
  Users,
  ExternalLink,
  Download,
  Sparkles,
  Trophy,
  XCircle,
  AlertCircle,
  File,
  FileSpreadsheet,
  FileType,
  TrendingUp,
} from 'lucide-react';
import { api, EPazarTenderDetail, EPazarItem, EPazarOffer, EPazarDocument, EPazarAwardedItem, EPazarEvaluation, EPazarEvaluationItem, EPazarPriceHints } from '@/lib/api';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatCurrency, formatDate } from '@/lib/utils';
import { TenderChatWidget } from '@/components/ai/TenderChatWidget';

// ============================================================================
// STATUS HELPERS
// ============================================================================

function getStatusLabel(status: string): string {
  switch (status?.toLowerCase()) {
    case 'active': return 'Активен';
    case 'awarded': return 'Доделен';
    case 'signed': return 'Потпишан';
    case 'cancelled': return 'Откажан';
    case 'completed': return 'Завршен';
    default: return status || 'Непознат';
  }
}

function getStatusBadgeVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status?.toLowerCase()) {
    case 'active': return 'default';
    case 'awarded':
    case 'signed': return 'secondary';
    case 'cancelled': return 'destructive';
    default: return 'outline';
  }
}

// ============================================================================
// FILE HELPERS
// ============================================================================

function getFileIcon(fileName?: string, mimeType?: string) {
  const extension = fileName?.split('.').pop()?.toLowerCase();
  const mime = mimeType?.toLowerCase();
  if (extension === 'pdf' || mime?.includes('pdf'))
    return <FileText className="h-5 w-5 text-red-500 flex-shrink-0" />;
  if (extension === 'doc' || extension === 'docx' || mime?.includes('word') || mime?.includes('msword'))
    return <FileType className="h-5 w-5 text-blue-500 flex-shrink-0" />;
  if (extension === 'xls' || extension === 'xlsx' || mime?.includes('excel') || mime?.includes('spreadsheet'))
    return <FileSpreadsheet className="h-5 w-5 text-green-600 flex-shrink-0" />;
  return <File className="h-5 w-5 text-muted-foreground flex-shrink-0" />;
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return "";
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}

// ============================================================================
// PRICE INDICATOR
// ============================================================================

function getPriceIndicator(itemPrice: number | undefined, marketMin?: number, marketMax?: number) {
  if (!itemPrice || !marketMin || !marketMax) return null;
  if (itemPrice < marketMin * 0.9)
    return <span className="text-green-600 text-xs ml-1">↓ Ниска</span>;
  if (itemPrice > marketMax * 1.1)
    return <span className="text-red-600 text-xs ml-1">↑ Висока</span>;
  return <span className="text-muted-foreground text-xs ml-1">✓ Просек</span>;
}

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

interface MarketPrice {
  min: number;
  max: number;
  avg: number;
  count: number;
}

function ItemsTable({ items, tenderId }: { items: EPazarItem[]; tenderId?: string }) {
  const [marketPrices, setMarketPrices] = useState<Record<string, MarketPrice>>({});
  const [pricesLoading, setPricesLoading] = useState(false);

  useEffect(() => {
    if (items && items.length > 0) loadMarketPrices();
  }, [items]);

  async function loadMarketPrices() {
    setPricesLoading(true);
    try {
      const itemNames = items.filter(i => i.item_name).map(i => i.item_name);
      if (itemNames.length === 0) return;

      const data = await api.getEPazarItemsAggregationsBatch(itemNames, tenderId);
      const prices: Record<string, MarketPrice> = {};

      for (const item of items) {
        const agg = data.aggregations[item.item_name];
        if (agg) {
          prices[item.item_id || item.item_name] = {
            min: agg.min_price || 0,
            max: agg.max_price || 0,
            avg: agg.avg_price || 0,
            count: agg.tender_count || 0,
          };
        }
      }
      setMarketPrices(prices);
    } catch {
      /* market prices are non-critical */
    } finally {
      setPricesLoading(false);
    }
  }

  if (!items || items.length === 0)
    return <p className="text-muted-foreground text-center py-8">Нема пронајдени ставки</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">#</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Назив</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">Количина</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Единица</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">Ед. цена</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">Вкупно</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground" title="Пазарни цени од претходни тендери">Пазар*</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => {
            const market = marketPrices[item.item_id || item.item_name];
            return (
              <tr key={item.item_id || idx} className="border-b hover:bg-muted/50">
                <td className="py-3 px-4 text-sm">{item.line_number}</td>
                <td className="py-3 px-4">
                  <div className="font-medium">{item.item_name}</div>
                  {item.item_description && (
                    <div className="text-xs text-muted-foreground mt-1 line-clamp-2">{item.item_description}</div>
                  )}
                </td>
                <td className="py-3 px-4 text-right text-sm">{item.quantity ? parseFloat(String(item.quantity)).toLocaleString() : '-'}</td>
                <td className="py-3 px-4 text-sm">{item.unit || '-'}</td>
                <td className="py-3 px-4 text-right text-sm">
                  {formatCurrency(item.estimated_unit_price_mkd)}
                  {getPriceIndicator(item.estimated_unit_price_mkd, market?.min, market?.max)}
                </td>
                <td className="py-3 px-4 text-right text-sm font-medium">{formatCurrency(item.estimated_total_price_mkd)}</td>
                <td className="py-3 px-4 text-right text-sm text-muted-foreground">
                  {pricesLoading ? (
                    <span className="animate-pulse">...</span>
                  ) : market ? (
                    <div className="text-xs">
                      <div>{formatCurrency(market.min)} - {formatCurrency(market.max)}</div>
                      <div className="text-muted-foreground">({market.count} тенд.)</div>
                    </div>
                  ) : '-'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-xs text-muted-foreground mt-2">* Пазарни цени базирани на претходни е-Пазар тендери</p>
    </div>
  );
}

function EvaluationItemsTable({ items }: { items: EPazarEvaluationItem[] }) {
  if (!items || items.length === 0)
    return <p className="text-muted-foreground text-center py-8">Нема податоци од евалуација</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">#</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Производ</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-muted-foreground">Понудено</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">Кол.</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">Ед. цена</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground">Вкупно</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-muted-foreground" title="Пазарни цени од други тендери">Пазар*</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={idx} className="border-b hover:bg-muted/50">
              <td className="py-3 px-4 text-sm">{item.line_number}</td>
              <td className="py-3 px-4">
                <div className="font-medium text-sm">{item.item_subject}</div>
                {item.winner_name && (
                  <div className="text-xs text-green-600 flex items-center gap-1">
                    <Trophy className="h-3 w-3" />
                    {item.winner_name}
                  </div>
                )}
              </td>
              <td className="py-3 px-4 text-sm">
                {item.offered_brand ? (
                  <Badge variant="secondary" className="text-xs">{item.offered_brand}</Badge>
                ) : '-'}
              </td>
              <td className="py-3 px-4 text-right text-sm">
                {item.quantity ? parseFloat(String(item.quantity)).toLocaleString() : '-'} {item.unit}
              </td>
              <td className="py-3 px-4 text-right text-sm font-medium text-primary">
                {formatCurrency(item.unit_price_without_vat)}
                {getPriceIndicator(item.unit_price_without_vat, item.market_min, item.market_max)}
              </td>
              <td className="py-3 px-4 text-right text-sm font-semibold">
                {formatCurrency(item.total_without_vat)}
              </td>
              <td className="py-3 px-4 text-right text-sm text-muted-foreground">
                {item.market_min && item.market_max ? (
                  <div className="text-xs">
                    <div>{formatCurrency(item.market_min)} - {formatCurrency(item.market_max)}</div>
                    {item.market_count && <div className="text-muted-foreground">({item.market_count} тенд.)</div>}
                  </div>
                ) : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-muted-foreground mt-2">* Пазарни цени базирани на победнички понуди од други е-Пазар тендери</p>
    </div>
  );
}

function OffersTable({ offers }: { offers: EPazarOffer[] }) {
  if (!offers || offers.length === 0)
    return <p className="text-muted-foreground text-center py-8">Нема поднесени понуди</p>;

  return (
    <div className="space-y-3">
      {offers.map((offer, idx) => (
        <div
          key={offer.offer_id || idx}
          className={`flex items-start justify-between p-4 rounded-lg border ${offer.is_winner ? 'border-green-500 bg-green-500/5' : 'bg-card'}`}
        >
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold">{offer.supplier_name}</span>
              {offer.is_winner && (
                <Badge variant="default" className="bg-green-500">
                  <Trophy className="h-3 w-3 mr-1" />
                  Победник
                </Badge>
              )}
              {offer.disqualified && (
                <Badge variant="destructive">
                  <XCircle className="h-3 w-3 mr-1" />
                  Дисквалификувано
                </Badge>
              )}
            </div>
            <div className="flex gap-3 text-xs text-muted-foreground mt-1">
              {offer.supplier_tax_id && <span>ДБ: {offer.supplier_tax_id}</span>}
              {offer.supplier_city && <span>{offer.supplier_city}</span>}
              {offer.ranking && <span>Место: #{offer.ranking}</span>}
            </div>
            {offer.rejection_reason && (
              <div className="mt-2 p-2 bg-destructive/10 rounded text-sm text-destructive">
                <AlertCircle className="h-3 w-3 inline mr-1" />
                {offer.rejection_reason}
              </div>
            )}
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-xl font-bold">{formatCurrency(offer.total_bid_mkd)}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function DocumentsList({ documents }: { documents: EPazarDocument[] }) {
  if (!documents || documents.length === 0)
    return <p className="text-muted-foreground text-center py-8">Нема достапни документи</p>;

  return (
    <div className="space-y-2">
      {documents.map((doc, idx) => (
        <div key={doc.doc_id || idx} className="flex items-center justify-between p-3 rounded-lg border">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            {getFileIcon(doc.file_name, doc.mime_type)}
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate text-sm">{doc.file_name || 'Document'}</p>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                {doc.doc_type && <span>{doc.doc_type}</span>}
                {doc.file_size_bytes && <><span>·</span><span>{formatFileSize(doc.file_size_bytes)}</span></>}
              </div>
            </div>
          </div>
          {doc.file_url ? (
            <a href={doc.file_url} target="_blank" rel="noopener noreferrer">
              <Button variant="outline" size="sm" className="flex-shrink-0">
                <Download className="h-4 w-4 mr-1" />
                Преземи
              </Button>
            </a>
          ) : (
            <Button variant="ghost" size="sm" disabled className="flex-shrink-0">
              Недостапно
            </Button>
          )}
        </div>
      ))}
    </div>
  );
}

function PriceHintsSection({ priceHints }: { priceHints: EPazarPriceHints }) {
  if (!priceHints || priceHints.hints_count === 0) return null;

  return (
    <div className="mt-6 pt-6 border-t">
      <div className="flex items-center gap-2 mb-3">
        <TrendingUp className="h-4 w-4 text-blue-600" />
        <span className="font-semibold text-sm">Историски цени за слични артикли</span>
        <span className="text-xs text-muted-foreground">— од претходни тендери</span>
      </div>
      <div className="space-y-2">
        {priceHints.hints.slice(0, 5).map((hint, idx) => (
          <div key={idx} className="rounded-lg p-3 border bg-muted/30 hover:bg-muted/50 transition-colors">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm">{hint.item_name}</div>
                {hint.estimated_price && (
                  <div className="text-xs text-muted-foreground">Проценето: {formatCurrency(hint.estimated_price)}</div>
                )}
              </div>
              {hint.historical.sample_count > 0 && (
                <div className="text-right flex-shrink-0">
                  <div className="text-sm font-bold">
                    {formatCurrency(hint.historical.min_price || 0)} - {formatCurrency(hint.historical.max_price || 0)}
                  </div>
                  <div className="text-xs text-muted-foreground">од {hint.historical.sample_count} продажби</div>
                </div>
              )}
            </div>
            {hint.historical.brands && hint.historical.brands.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {hint.historical.brands.slice(0, 3).map((brand, bIdx) => (
                  <Badge key={bIdx} variant="secondary" className="text-xs">{brand}</Badge>
                ))}
              </div>
            )}
            {hint.historical.examples && hint.historical.examples.length > 0 && (
              <div className="mt-2 text-xs text-muted-foreground space-y-1">
                {hint.historical.examples.slice(0, 2).map((ex, eIdx) => (
                  <div key={eIdx} className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-foreground">{formatCurrency(ex.price)}</span>
                    {ex.brand && <span>· {ex.brand}</span>}
                    {ex.winner && <span className="truncate max-w-[200px]">· {ex.winner}</span>}
                    {ex.tender_id && (
                      <Link href={`/epazar/${ex.tender_id}`} className="text-primary hover:underline font-medium">{ex.tender_id}</Link>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
        {priceHints.hints_count > 5 && (
          <p className="text-xs text-muted-foreground text-center">
            + уште {priceHints.hints_count - 5} артикли со историски цени
          </p>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// MAIN PAGE
// ============================================================================

export default function EPazarDetailPage() {
  const params = useParams();
  const router = useRouter();
  const tenderId = decodeURIComponent(params.id as string);

  const [tender, setTender] = useState<EPazarTenderDetail | null>(null);
  const [evaluation, setEvaluation] = useState<EPazarEvaluation | null>(null);
  const [priceHints, setPriceHints] = useState<EPazarPriceHints | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // AI Summary — click-to-load
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  useEffect(() => {
    loadTender();
    loadEvaluation();
    loadPriceHints();
  }, [tenderId]);

  async function loadTender() {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getEPazarTender(tenderId);
      setTender(data);
    } catch (err) {
      console.error('Failed to load tender:', err);
      setError('Грешка при вчитување на тендерот');
    } finally {
      setLoading(false);
    }
  }

  async function loadEvaluation() {
    try {
      const data = await api.getEPazarEvaluation(tenderId);
      if (data.has_evaluation) setEvaluation(data);
    } catch { /* not critical */ }
  }

  async function loadPriceHints() {
    try {
      const data = await api.getEPazarPriceHints(tenderId);
      if (data.hints_count > 0) setPriceHints(data);
    } catch { /* not critical */ }
  }

  async function generateSummary() {
    if (!tender) return;
    setSummaryLoading(true);
    try {
      const result = await api.summarizeEPazarTender(tenderId);
      if (result.summary) {
        setSummary(result.summary);
      } else {
        // Fallback: local summary
        const parts: string[] = [];
        if (tender.contracting_authority) parts.push(`Набавка од ${tender.contracting_authority}.`);
        if (tender.estimated_value_mkd) parts.push(`Проценета вредност: ${tender.estimated_value_mkd.toLocaleString()} МКД.`);
        if (tender.items?.length) parts.push(`Вклучува ${tender.items.length} артикли.`);
        if (tender.offers?.length) {
          const winner = tender.offers.find(o => o.is_winner);
          parts.push(`${tender.offers.length} понуди.`);
          if (winner) parts.push(`Победник: ${winner.supplier_name} (${winner.total_bid_mkd?.toLocaleString()} МКД).`);
        }
        setSummary(parts.join(' ') || 'Нема доволно информации за резиме.');
      }
    } catch {
      try {
        const ragResult = await api.queryRAG(
          "Дај краток резиме на овој тендер во 3-4 реченици.",
          tenderId
        );
        setSummary(ragResult.answer);
      } catch {
        setSummary('Не може да се генерира резиме во моментов.');
      }
    } finally {
      setSummaryLoading(false);
    }
  }

  // ========================================================================
  // LOADING / ERROR
  // ========================================================================

  if (loading) {
    return (
      <DashboardLayout>
        <div className="p-6 space-y-4">
          <div className="h-6 bg-muted rounded w-1/4 animate-pulse" />
          <div className="h-10 bg-muted rounded w-3/4 animate-pulse" />
          <div className="h-12 bg-muted rounded animate-pulse" />
          <div className="h-64 bg-muted rounded animate-pulse" />
        </div>
      </DashboardLayout>
    );
  }

  if (error || !tender) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <p className="text-destructive">{error || 'Тендерот не е пронајден'}</p>
          <Button variant="outline" className="mt-4" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  const hasEvaluation = !!evaluation?.has_evaluation;
  const itemsCount = hasEvaluation ? (evaluation.items?.length || 0) : (tender.items?.length || 0);

  return (
    <DashboardLayout>
      <div className="space-y-4 p-6">
        {/* Breadcrumb + Header */}
        <div>
          <Link href="/epazar" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors mb-2">
            <ArrowLeft className="h-3 w-3" />
            е-Пазар
          </Link>

          <div className="flex flex-col md:flex-row md:items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <Badge variant={getStatusBadgeVariant(tender.status)}>
                  {getStatusLabel(tender.status)}
                </Badge>
                <span className="text-sm text-muted-foreground">{tender.tender_id}</span>
              </div>
              <h1 className="text-xl md:text-2xl font-bold break-words">{tender.title}</h1>
            </div>
            {tender.source_url && (
              <a href={tender.source_url} target="_blank" rel="noopener noreferrer" className="flex-shrink-0">
                <Button variant="outline" size="sm">
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Оригинал
                </Button>
              </a>
            )}
          </div>
        </div>

        {/* Compact Metrics Strip */}
        <div className="flex flex-wrap gap-4 p-3 rounded-lg border bg-card">
          {tender.contracting_authority && (
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-blue-500" />
              <div>
                <p className="text-xs text-muted-foreground">Институција</p>
                <p className="text-sm font-medium">{tender.contracting_authority}</p>
              </div>
            </div>
          )}
          <div className="flex items-center gap-2">
            <DollarSign className="h-4 w-4 text-green-500" />
            <div>
              <p className="text-xs text-muted-foreground">Вредност</p>
              <p className="text-sm font-bold">
                {tender.estimated_value_mkd ? formatCurrency(tender.estimated_value_mkd)
                  : tender.awarded_value_mkd ? <span className="text-green-600">{formatCurrency(tender.awarded_value_mkd)}</span>
                  : '-'}
              </p>
            </div>
          </div>
          {tender.closing_date && (
            <div className="flex items-center gap-2">
              <Calendar className="h-4 w-4 text-orange-500" />
              <div>
                <p className="text-xs text-muted-foreground">Краен рок</p>
                <p className="text-sm font-bold">{formatDate(tender.closing_date)}</p>
              </div>
            </div>
          )}
          {(tender.offers?.length ?? 0) > 0 && (
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-purple-500" />
              <div>
                <p className="text-xs text-muted-foreground">Понуди</p>
                <p className="text-sm font-bold">{tender.offers?.length}</p>
              </div>
            </div>
          )}
          {tender.procedure_type && (
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <div>
                <p className="text-xs text-muted-foreground">Постапка</p>
                <p className="text-sm font-medium">{tender.procedure_type}</p>
              </div>
            </div>
          )}
        </div>

        {/* Description */}
        {tender.description && (
          <div className="text-sm text-muted-foreground p-3 rounded-lg border bg-muted/30">
            {tender.description}
          </div>
        )}

        {/* Tabs — 4 tabs */}
        <Card>
          <Tabs defaultValue="products">
            <CardHeader className="pb-0">
              <div className="w-full overflow-x-auto pb-2">
                <TabsList className="w-full justify-start inline-flex min-w-max">
                  <TabsTrigger value="products" className="flex items-center gap-2">
                    <Package className="h-4 w-4" />
                    Производи ({itemsCount})
                  </TabsTrigger>
                  <TabsTrigger value="offers" className="flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    Понуди ({tender.offers?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="documents" className="flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Документи ({tender.documents?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="ai" className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4" />
                    AI Резиме
                  </TabsTrigger>
                </TabsList>
              </div>
            </CardHeader>
            <CardContent>
              {/* Products Tab — merged Evaluation + Items + Price Hints + Awarded */}
              <TabsContent value="products">
                <div>
                  {/* Winner banner if evaluation exists */}
                  {hasEvaluation && evaluation.bidders && evaluation.bidders.length > 0 && (
                    <div className="flex flex-wrap items-center gap-2 mb-4 p-3 bg-green-500/5 border border-green-500/20 rounded-lg">
                      <Trophy className="h-4 w-4 text-green-600" />
                      <span className="text-sm font-medium">Победници:</span>
                      {evaluation.bidders.map((bidder, idx) => (
                        <Badge
                          key={idx}
                          variant={bidder.is_winner ? 'default' : bidder.is_rejected ? 'destructive' : 'outline'}
                          className={bidder.is_winner ? 'bg-green-500' : ''}
                        >
                          {bidder.is_winner && <Trophy className="h-3 w-3 mr-1" />}
                          {bidder.name}
                        </Badge>
                      ))}
                      {evaluation.total_value > 0 && (
                        <span className="text-sm font-bold text-green-700 ml-auto">
                          {formatCurrency(evaluation.total_value)}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Show evaluation table if available, otherwise items table */}
                  {hasEvaluation ? (
                    <EvaluationItemsTable items={evaluation.items} />
                  ) : (
                    <ItemsTable items={tender.items || []} tenderId={tenderId} />
                  )}

                  {/* Awarded Items summary (if different from evaluation) */}
                  {!hasEvaluation && tender.awarded_items && tender.awarded_items.length > 0 && (
                    <div className="mt-6 pt-6 border-t">
                      <div className="flex items-center gap-2 mb-3">
                        <Trophy className="h-4 w-4 text-green-600" />
                        <span className="font-semibold text-sm">Доделени ставки</span>
                      </div>
                      <div className="overflow-x-auto">
                        <table className="w-full">
                          <thead>
                            <tr className="border-b bg-muted/50">
                              <th className="text-left py-2 px-4 text-sm font-medium text-muted-foreground">Добавувач</th>
                              <th className="text-left py-2 px-4 text-sm font-medium text-muted-foreground">Ставка</th>
                              <th className="text-right py-2 px-4 text-sm font-medium text-muted-foreground">Кол.</th>
                              <th className="text-right py-2 px-4 text-sm font-medium text-muted-foreground">Ед. цена</th>
                              <th className="text-right py-2 px-4 text-sm font-medium text-muted-foreground">Вкупно</th>
                            </tr>
                          </thead>
                          <tbody>
                            {tender.awarded_items.map((item, idx) => (
                              <tr key={item.awarded_item_id || idx} className="border-b hover:bg-muted/50">
                                <td className="py-2 px-4 text-sm font-medium">{item.supplier_name}</td>
                                <td className="py-2 px-4 text-sm">{item.item_name || '-'}</td>
                                <td className="py-2 px-4 text-right text-sm">{item.contracted_quantity ? parseFloat(String(item.contracted_quantity)).toLocaleString() : '-'}</td>
                                <td className="py-2 px-4 text-right text-sm">{formatCurrency(item.contracted_unit_price_mkd)}</td>
                                <td className="py-2 px-4 text-right text-sm font-medium">{formatCurrency(item.contracted_total_mkd)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Price Hints — inline below items */}
                  {priceHints && <PriceHintsSection priceHints={priceHints} />}
                </div>
              </TabsContent>

              {/* Offers Tab */}
              <TabsContent value="offers">
                <OffersTable offers={tender.offers || []} />
              </TabsContent>

              {/* Documents Tab */}
              <TabsContent value="documents">
                <DocumentsList documents={tender.documents || []} />
              </TabsContent>

              {/* AI Summary Tab — click-to-load */}
              <TabsContent value="ai">
                <div className="space-y-4">
                  {!summary && !summaryLoading && (
                    <div className="text-center py-8">
                      <Sparkles className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
                      <p className="text-muted-foreground mb-4">Генерирај AI резиме за овој тендер</p>
                      <Button onClick={generateSummary}>
                        <Sparkles className="h-4 w-4 mr-2" />
                        Генерирај резиме
                      </Button>
                    </div>
                  )}
                  {summaryLoading && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground py-8 justify-center">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary" />
                      Генерирање на AI резиме...
                    </div>
                  )}
                  {summary && (
                    <div className="prose prose-sm max-w-none">
                      <p className="whitespace-pre-wrap">{summary}</p>
                    </div>
                  )}
                </div>
              </TabsContent>
            </CardContent>
          </Tabs>
        </Card>

        {/* Floating AI Chat Widget */}
        <TenderChatWidget tenderId={tenderId} tenderTitle={tender.title} />
      </div>
    </DashboardLayout>
  );
}
