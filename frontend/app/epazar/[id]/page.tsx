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
  MessageSquare,
  File,
  FileSpreadsheet,
  FileType,
  TrendingUp,
} from 'lucide-react';
import { api, EPazarTenderDetail, EPazarItem, EPazarOffer, EPazarDocument, EPazarAwardedItem, EPazarEvaluation, EPazarEvaluationItem, EPazarPriceHints, EPazarPriceHint, RAGQueryResponse } from '@/lib/api';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatCurrency, formatDate } from '@/lib/utils';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  sources?: RAGQueryResponse["sources"];
}

function getStatusBadgeVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status?.toLowerCase()) {
    case 'active':
      return 'default';
    case 'awarded':
      return 'secondary';
    case 'cancelled':
      return 'destructive';
    default:
      return 'outline';
  }
}

interface MarketPrice {
  min: number;
  max: number;
  avg: number;
  count: number;
}

function ItemsTable({ items }: { items: EPazarItem[] }) {
  const [marketPrices, setMarketPrices] = useState<Record<string, MarketPrice>>({});
  const [pricesLoading, setPricesLoading] = useState(false);

  useEffect(() => {
    if (items && items.length > 0) {
      loadMarketPrices();
    }
  }, [items]);

  async function loadMarketPrices() {
    setPricesLoading(true);
    const prices: Record<string, MarketPrice> = {};

    // Fetch market prices for first 5 items to avoid too many requests
    const itemsToCheck = items.slice(0, 5);

    for (const item of itemsToCheck) {
      if (!item.item_name) continue;
      try {
        // Extract first 2-3 words for search (more specific = better match)
        const searchTerm = item.item_name.split(' ').slice(0, 3).join(' ');
        const data = await api.getEPazarItemsAggregations(searchTerm);
        if (data.aggregations && data.aggregations.length > 0) {
          const agg = data.aggregations[0];
          prices[item.item_id || item.item_name] = {
            min: agg.min_unit_price || 0,
            max: agg.max_unit_price || 0,
            avg: agg.avg_unit_price || 0,
            count: agg.tender_count || 0
          };
        }
      } catch (err) {
        // Ignore errors for individual items
      }
    }

    setMarketPrices(prices);
    setPricesLoading(false);
  }

  if (!items || items.length === 0) {
    return <p className="text-gray-500 text-center py-8">Нема пронајдени ставки</p>;
  }

  function getPriceIndicator(itemPrice: number | undefined, marketPrice: MarketPrice | undefined) {
    if (!itemPrice || !marketPrice || marketPrice.count === 0) return null;

    if (itemPrice < marketPrice.min * 0.9) {
      return <span className="text-green-600 text-xs">↓ Ниска</span>;
    } else if (itemPrice > marketPrice.max * 1.1) {
      return <span className="text-red-600 text-xs">↑ Висока</span>;
    }
    return <span className="text-gray-500 text-xs">✓ Во просек</span>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b">
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">#</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Назив</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Количина</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Единица</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Ед. цена</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Вкупно</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500" title="Пазарни цени од претходни тендери">
              Пазар*
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => {
            const market = marketPrices[item.item_id || item.item_name];
            return (
              <tr key={item.item_id || idx} className="border-b hover:bg-gray-50">
                <td className="py-3 px-4 text-sm">{item.line_number}</td>
                <td className="py-3 px-4">
                  <div className="font-medium">{item.item_name}</div>
                  {item.item_description && (
                    <div className="text-xs text-gray-500 mt-1 line-clamp-2">{item.item_description}</div>
                  )}
                </td>
                <td className="py-3 px-4 text-right text-sm">{item.quantity?.toLocaleString()}</td>
                <td className="py-3 px-4 text-sm">{item.unit || '-'}</td>
                <td className="py-3 px-4 text-right text-sm">
                  {formatCurrency(item.estimated_unit_price_mkd)}
                  {getPriceIndicator(item.estimated_unit_price_mkd, market)}
                </td>
                <td className="py-3 px-4 text-right text-sm font-medium">{formatCurrency(item.estimated_total_price_mkd)}</td>
                <td className="py-3 px-4 text-right text-sm text-gray-500">
                  {pricesLoading && idx < 5 ? (
                    <span className="animate-pulse">...</span>
                  ) : market ? (
                    <div className="text-xs">
                      <div>{formatCurrency(market.min)} - {formatCurrency(market.max)}</div>
                      <div className="text-gray-400">({market.count} тенд.)</div>
                    </div>
                  ) : (
                    '-'
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="text-xs text-gray-400 mt-2">* Пазарни цени базирани на претходни е-Пазар тендери</p>
    </div>
  );
}

function OffersTable({ offers }: { offers: EPazarOffer[] }) {
  if (!offers || offers.length === 0) {
    return <p className="text-gray-500 text-center py-8">Нема поднесени понуди</p>;
  }

  return (
    <div className="space-y-4">
      {offers.map((offer, idx) => (
        <Card key={offer.offer_id || idx} className={offer.is_winner ? 'border-green-500 border-2' : ''}>
          <CardContent className="pt-6">
            <div className="flex justify-between items-start">
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold">{offer.supplier_name}</h3>
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
                {offer.supplier_tax_id && (
                  <p className="text-sm text-gray-500">ДБ: {offer.supplier_tax_id}</p>
                )}
                {offer.supplier_city && (
                  <p className="text-sm text-gray-500">{offer.supplier_city}</p>
                )}
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold">{formatCurrency(offer.total_bid_mkd)}</div>
                {offer.ranking && (
                  <p className="text-sm text-gray-500">Место: #{offer.ranking}</p>
                )}
              </div>
            </div>
            {offer.rejection_reason && (
              <div className="mt-3 p-2 bg-red-50 rounded text-sm text-red-700">
                <AlertCircle className="h-4 w-4 inline mr-1" />
                {offer.rejection_reason}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function AwardedItemsTable({ items }: { items: EPazarAwardedItem[] }) {
  if (!items || items.length === 0) {
    return <p className="text-gray-500 text-center py-8">Нема доделени ставки</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b">
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Добавувач</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Ставка</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Количина</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Ед. цена</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Вкупно</th>
            <th className="text-center py-3 px-4 text-sm font-medium text-gray-500">Статус</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={item.awarded_item_id || idx} className="border-b hover:bg-gray-50">
              <td className="py-3 px-4">
                <div className="font-medium">{item.supplier_name}</div>
                {item.supplier_tax_id && (
                  <div className="text-xs text-gray-500">{item.supplier_tax_id}</div>
                )}
              </td>
              <td className="py-3 px-4 text-sm">{item.item_name || '-'}</td>
              <td className="py-3 px-4 text-right text-sm">{item.contracted_quantity?.toLocaleString()}</td>
              <td className="py-3 px-4 text-right text-sm">{formatCurrency(item.contracted_unit_price_mkd)}</td>
              <td className="py-3 px-4 text-right text-sm font-medium">{formatCurrency(item.contracted_total_mkd)}</td>
              <td className="py-3 px-4 text-center">
                <Badge variant={item.status === 'awarded' ? 'default' : 'secondary'}>
                  {item.status}
                </Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EvaluationItemsTable({ items }: { items: EPazarEvaluationItem[] }) {
  if (!items || items.length === 0) {
    return <p className="text-gray-500 text-center py-8">Нема податоци од евалуација</p>;
  }

  function getPriceIndicator(itemPrice: number | undefined, marketMin?: number, marketMax?: number) {
    if (!itemPrice || !marketMin || !marketMax) return null;

    if (itemPrice < marketMin * 0.9) {
      return <span className="text-green-600 text-xs ml-1">↓ Ниска</span>;
    } else if (itemPrice > marketMax * 1.1) {
      return <span className="text-red-600 text-xs ml-1">↑ Висока</span>;
    }
    return <span className="text-gray-500 text-xs ml-1">✓ Просек</span>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-yellow-50">
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">#</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Производ</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-600">Бренд</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Кол.</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Ед. цена</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-600">Вкупно</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-600" title="Пазарни цени од други тендери">
              Пазар*
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
            <tr key={idx} className="border-b hover:bg-yellow-50/50">
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
                  <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                    {item.offered_brand}
                  </Badge>
                ) : '-'}
              </td>
              <td className="py-3 px-4 text-right text-sm">
                {item.quantity?.toLocaleString()} {item.unit}
              </td>
              <td className="py-3 px-4 text-right text-sm font-medium text-green-700">
                {formatCurrency(item.unit_price_without_vat)}
                {getPriceIndicator(item.unit_price_without_vat, item.market_min, item.market_max)}
              </td>
              <td className="py-3 px-4 text-right text-sm font-semibold">
                {formatCurrency(item.total_without_vat)}
              </td>
              <td className="py-3 px-4 text-right text-sm text-gray-500">
                {item.market_min && item.market_max ? (
                  <div className="text-xs">
                    <div>{formatCurrency(item.market_min)} - {formatCurrency(item.market_max)}</div>
                    {item.market_count && (
                      <div className="text-gray-400">({item.market_count} тенд.)</div>
                    )}
                  </div>
                ) : '-'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-gray-400 mt-2">* Пазарни цени базирани на победнички понуди од други е-Пазар тендери</p>
    </div>
  );
}

function getFileIcon(fileName?: string, mimeType?: string) {
  const extension = fileName?.split('.').pop()?.toLowerCase();
  const mime = mimeType?.toLowerCase();

  // Check by extension or mime type
  if (extension === 'pdf' || mime?.includes('pdf')) {
    return <FileText className="h-5 w-5 text-red-500 flex-shrink-0" />;
  }
  if (extension === 'doc' || extension === 'docx' || mime?.includes('word') || mime?.includes('msword')) {
    return <FileType className="h-5 w-5 text-blue-500 flex-shrink-0" />;
  }
  if (extension === 'xls' || extension === 'xlsx' || mime?.includes('excel') || mime?.includes('spreadsheet')) {
    return <FileSpreadsheet className="h-5 w-5 text-green-600 flex-shrink-0" />;
  }
  // Default file icon
  return <File className="h-5 w-5 text-gray-400 flex-shrink-0" />;
}

function formatFileSize(bytes?: number): string {
  if (!bytes) return "";
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}

function DocumentsList({ documents }: { documents: EPazarDocument[] }) {
  if (!documents || documents.length === 0) {
    return <p className="text-gray-500 text-center py-8">Нема достапни документи</p>;
  }

  return (
    <div className="space-y-2">
      {documents.map((doc, idx) => (
        <Card key={doc.doc_id || idx}>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3 flex-1 min-w-0">
                {getFileIcon(doc.file_name, doc.mime_type)}
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{doc.file_name || 'Document'}</p>
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    {doc.doc_type && <span>{doc.doc_type}</span>}
                    {doc.file_size_bytes && (
                      <>
                        <span>•</span>
                        <span>{formatFileSize(doc.file_size_bytes)}</span>
                      </>
                    )}
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
                  <XCircle className="h-4 w-4 mr-1" />
                  Недостапно
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function EPazarDetailPage() {
  const params = useParams();
  const router = useRouter();
  const tenderId = decodeURIComponent(params.id as string);

  const [tender, setTender] = useState<EPazarTenderDetail | null>(null);
  const [evaluation, setEvaluation] = useState<EPazarEvaluation | null>(null);
  const [priceHints, setPriceHints] = useState<EPazarPriceHints | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatLoading, setChatLoading] = useState(false);

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
      // Generate summary after tender data is loaded
      void generateSummaryWithData(data);
    } catch (err) {
      console.error('Failed to load tender:', err);
      setError('Failed to load tender details');
    } finally {
      setLoading(false);
    }
  }

  async function loadEvaluation() {
    try {
      const data = await api.getEPazarEvaluation(tenderId);
      if (data.has_evaluation) {
        setEvaluation(data);
      }
    } catch (err) {
      console.error('Failed to load evaluation:', err);
      // Not critical - don't show error, evaluation may not exist
    }
  }

  async function loadPriceHints() {
    try {
      const data = await api.getEPazarPriceHints(tenderId);
      if (data.hints_count > 0) {
        setPriceHints(data);
      }
    } catch (err) {
      console.error('Failed to load price hints:', err);
      // Not critical
    }
  }

  async function generateSummaryWithData(tenderData: EPazarTenderDetail) {
    if (!tenderId) return;

    setSummaryLoading(true);
    try {
      // First try to get the structured summary from the tender itself
      const result = await api.summarizeEPazarTender(tenderId);
      if (result.summary) {
        setSummary(result.summary);
      } else {
        // Generate local summary from tender data
        generateLocalSummary(tenderData);
      }
    } catch (err) {
      console.error('Failed to generate summary via API:', err);
      // Try RAG as fallback
      try {
        const ragResult = await api.queryRAG(
          "Дај ми краток резиме на овој тендер во 3-4 реченици. Вклучи информации за артиклите и понудите.",
          tenderId
        );
        setSummary(ragResult.answer);
      } catch (ragErr) {
        console.error('RAG also failed:', ragErr);
        // Final fallback - generate local summary from loaded data
        generateLocalSummary(tenderData);
      }
    } finally {
      setSummaryLoading(false);
    }
  }

  // For the button click (when tender is already in state)
  async function generateSummary() {
    if (!tenderId || !tender) return;
    await generateSummaryWithData(tender);
  }

  function generateLocalSummary(tenderData: EPazarTenderDetail) {
    if (!tenderData) {
      setSummary("Нема достапни информации за генерирање на резиме.");
      return;
    }

    const parts: string[] = [];

    if (tenderData.contracting_authority) {
      parts.push(`Набавка од ${tenderData.contracting_authority}.`);
    }

    if (tenderData.estimated_value_mkd) {
      parts.push(`Проценета вредност: ${tenderData.estimated_value_mkd.toLocaleString()} МКД.`);
    }

    if (tenderData.items && tenderData.items.length > 0) {
      parts.push(`Вклучува ${tenderData.items.length} артикли.`);
    }

    if (tenderData.offers && tenderData.offers.length > 0) {
      const winningOffer = tenderData.offers.find(o => o.is_winner);
      parts.push(`Добиени ${tenderData.offers.length} понуди.`);
      if (winningOffer) {
        parts.push(`Победник: ${winningOffer.supplier_name} со понуда од ${winningOffer.total_bid_mkd?.toLocaleString()} МКД.`);
      }
    }

    if (tenderData.status) {
      parts.push(`Статус: ${tenderData.status}.`);
    }

    setSummary(parts.join(' ') || "Нема доволно информации за резиме.");
  }

  async function handleChatSend(message: string) {
    setChatMessages((prev) => [...prev, { role: "user", content: message }]);
    setChatLoading(true);

    try {
      // Build conversation history for context
      const conversationHistory = chatMessages.slice(-10).map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const result = await api.queryRAG(message, tenderId, conversationHistory);
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.answer,
          sources: result.sources,
        },
      ]);
    } catch (error) {
      console.error("Failed to get AI response:", error);
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Грешка при добивање одговор. Ве молиме обидете се повторно.",
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  const quickPrompts = [
    "Кои артикли се бараат?",
    "Кои се понудувачите и нивните цени?",
    "Кој е победникот?",
  ];

  if (loading) {
    return (
      <DashboardLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4" />
          <div className="h-12 bg-gray-200 rounded w-3/4" />
          <div className="h-64 bg-gray-200 rounded" />
        </div>
      </DashboardLayout>
    );
  }

  if (error || !tender) {
    return (
      <DashboardLayout>
        <div className="text-center py-12">
          <p className="text-red-500">{error || 'Тендерот не е пронајден'}</p>
          <Button variant="outline" className="mt-4" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад
          </Button>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <Button variant="ghost" size="sm" onClick={() => router.back()} className="mb-2 pl-0 hover:bg-transparent">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Назад на е-Пазар
            </Button>
            <div className="flex items-center gap-3">
              <Badge variant={getStatusBadgeVariant(tender.status)} className="text-sm">
                {tender.status}
              </Badge>
              <span className="text-gray-500 text-sm">{tender.tender_id}</span>
            </div>
            <h1 className="text-xl md:text-2xl font-bold mt-2 break-words">{tender.title}</h1>
          </div>
          {tender.source_url && (
            <a href={tender.source_url} target="_blank" rel="noopener noreferrer" className="w-full md:w-auto">
              <Button variant="outline" className="w-full md:w-auto">
                <ExternalLink className="h-4 w-4 mr-2" />
                Отвори оригинал
              </Button>
            </a>
          )}
        </div>

        {/* Overview Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <Building2 className="h-5 w-5 text-blue-500" />
                <div>
                  <p className="text-sm text-gray-500">Договорен орган</p>
                  <p className="font-medium">{tender.contracting_authority || 'Непознато'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <DollarSign className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm text-gray-500">Проценета вредност</p>
                  <p className="font-medium">{tender.estimated_value_mkd ? formatCurrency(tender.estimated_value_mkd) : (tender.awarded_value_mkd ? formatCurrency(tender.awarded_value_mkd) + ' (доделено)' : 'Не е наведено')}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <Calendar className="h-5 w-5 text-orange-500" />
                <div>
                  <p className="text-sm text-gray-500">Краен рок</p>
                  <p className="font-medium">{tender.closing_date ? formatDate(tender.closing_date) : 'Не е наведено'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-purple-500" />
                <div>
                  <p className="text-sm text-gray-500">Вид на постапка</p>
                  <p className="font-medium">{tender.procedure_type || 'Не е наведено'}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* AI Summary */}
        <Card className="border-primary/50 bg-primary/5">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-yellow-500" />
                AI Резиме
              </CardTitle>
              {!summary && !summaryLoading && (
                <Button onClick={generateSummary} disabled={summaryLoading} size="sm">
                  Генерирај резиме
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {summaryLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                Генерирање на AI резиме...
              </div>
            ) : summary ? (
              <p className="text-gray-700 whitespace-pre-wrap">{summary}</p>
            ) : (
              <p className="text-gray-500 text-sm">
                Кликни на "Генерирај резиме" за AI анализа на овој тендер, вклучувајќи детали за артиклите и конкуренцијата.
              </p>
            )}
          </CardContent>
        </Card>


        {/* Description */}
        {tender.description && (
          <Card>
            <CardHeader>
              <CardTitle>Опис</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-700 whitespace-pre-wrap">{tender.description}</p>
            </CardContent>
          </Card>
        )}

        {/* Price Hints Widget - Historical prices for similar items */}
        {priceHints && priceHints.hints_count > 0 && (
          <Card className="border-green-200 bg-green-50/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-green-600" />
                Историски цени за слични артикли
              </CardTitle>
              <CardDescription>
                Цени од претходни тендери за артикли кои се бараат во овој тендер
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {priceHints.hints.slice(0, 5).map((hint, idx) => (
                  <div key={idx} className="bg-white rounded-lg p-3 border border-green-100">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm truncate">{hint.item_name}</div>
                        {hint.estimated_price && (
                          <div className="text-xs text-gray-500">
                            Проценето: {formatCurrency(hint.estimated_price)}
                          </div>
                        )}
                      </div>
                      {hint.historical.sample_count > 0 && (
                        <div className="text-right flex-shrink-0">
                          <div className="text-sm font-semibold text-green-700">
                            {formatCurrency(hint.historical.min_price || 0)} - {formatCurrency(hint.historical.max_price || 0)}
                          </div>
                          <div className="text-xs text-gray-500">
                            од {hint.historical.sample_count} продажби
                          </div>
                        </div>
                      )}
                    </div>
                    {/* Winning brands */}
                    {hint.historical.brands && hint.historical.brands.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {hint.historical.brands.slice(0, 3).map((brand, bIdx) => (
                          <Badge key={bIdx} variant="outline" className="text-xs bg-blue-50 border-blue-200 text-blue-700">
                            {brand}
                          </Badge>
                        ))}
                      </div>
                    )}
                    {/* Example past sales */}
                    {hint.historical.examples && hint.historical.examples.length > 0 && (
                      <div className="mt-2 text-xs text-gray-500 space-y-1">
                        {hint.historical.examples.slice(0, 2).map((ex, eIdx) => (
                          <div key={eIdx} className="flex items-center gap-2">
                            <span className="text-green-600 font-medium">{formatCurrency(ex.price)}</span>
                            {ex.brand && <span>• {ex.brand}</span>}
                            {ex.winner && <span>• од {ex.winner}</span>}
                            {ex.tender_id && (
                              <Link href={`/epazar/${ex.tender_id}`} className="text-blue-600 hover:underline">
                                #{ex.tender_id}
                              </Link>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {priceHints.hints_count > 5 && (
                  <p className="text-xs text-gray-500 text-center">
                    + уште {priceHints.hints_count - 5} артикли со историски цени
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tabs for Items, Offers, Documents, AI Agent */}
        <Card>
          <Tabs defaultValue={evaluation?.has_evaluation ? "evaluation" : "items"}>
            <CardHeader>
              <div className="w-full overflow-x-auto pb-2">
                <TabsList className="w-full justify-start inline-flex min-w-max">
                  {evaluation?.has_evaluation && (
                    <TabsTrigger value="evaluation" className="flex items-center gap-2 bg-yellow-100 data-[state=active]:bg-yellow-200">
                      <Sparkles className="h-4 w-4 text-yellow-600" />
                      <span className="text-yellow-700">Победници ({evaluation.items_count})</span>
                    </TabsTrigger>
                  )}
                  <TabsTrigger value="items" className="flex items-center gap-2">
                    <Package className="h-4 w-4" />
                    Ставки ({tender.items?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="offers" className="flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    Понуди ({tender.offers?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="awarded" className="flex items-center gap-2">
                    <Trophy className="h-4 w-4" />
                    Доделено ({tender.awarded_items?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="documents" className="flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Документи ({tender.documents?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="chat" className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4" />
                    AI Асистент
                  </TabsTrigger>
                </TabsList>
              </div>
            </CardHeader>
            <CardContent>
              {evaluation?.has_evaluation && (
                <TabsContent value="evaluation">
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm text-yellow-700 bg-yellow-50 p-3 rounded-lg">
                      <Sparkles className="h-4 w-4" />
                      <span>Податоци од евалуационен извештај - реални победнички цени и брендови</span>
                    </div>
                    {evaluation.bidders && evaluation.bidders.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-4">
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
                      </div>
                    )}
                    <EvaluationItemsTable items={evaluation.items} />
                    {evaluation.total_value > 0 && (
                      <div className="text-right text-sm text-gray-600 mt-2">
                        Вкупна победничка вредност: <span className="font-bold text-green-700">{formatCurrency(evaluation.total_value)}</span>
                      </div>
                    )}
                  </div>
                </TabsContent>
              )}
              <TabsContent value="items">
                <ItemsTable items={tender.items || []} />
              </TabsContent>
              <TabsContent value="offers">
                <OffersTable offers={tender.offers || []} />
              </TabsContent>
              <TabsContent value="awarded">
                <AwardedItemsTable items={tender.awarded_items || []} />
              </TabsContent>
              <TabsContent value="documents">
                <DocumentsList documents={tender.documents || []} />
              </TabsContent>
              <TabsContent value="chat">
                <div className="space-y-4">
                  <CardDescription>
                    Постави прашања за овој тендер - за артикли, цени, понудувачи и повеќе
                  </CardDescription>

                  {/* Chat Messages */}
                  <div className="space-y-4 min-h-[300px] max-h-[400px] overflow-y-auto border rounded-lg p-4 bg-gray-50">
                    {chatMessages.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-full text-center text-gray-500 py-8">
                        <MessageSquare className="h-12 w-12 mb-2 opacity-20" />
                        <p className="text-sm">Постави прашање за да започнеш</p>
                      </div>
                    ) : (
                      chatMessages.map((msg, idx) => (
                        <ChatMessage
                          key={idx}
                          role={msg.role}
                          content={msg.content}
                          sources={msg.sources}
                        />
                      ))
                    )}
                    {chatLoading && (
                      <div className="text-sm text-gray-500">AI пишува...</div>
                    )}
                  </div>

                  {/* Quick Prompts */}
                  <div className="flex flex-wrap gap-2">
                    {quickPrompts.map((prompt) => (
                      <Button
                        key={prompt}
                        variant="outline"
                        size="sm"
                        onClick={() => handleChatSend(prompt)}
                        disabled={chatLoading}
                      >
                        {prompt}
                      </Button>
                    ))}
                  </div>

                  {/* Chat Input */}
                  <ChatInput
                    onSend={handleChatSend}
                    disabled={chatLoading}
                    placeholder="Прашај нешто за овој тендер..."
                  />
                </div>
              </TabsContent>
            </CardContent>
          </Tabs>
        </Card>

        {/* Additional Details - Only show fields that have data */}
        <Card>
          <CardHeader>
            <CardTitle>Детали за тендерот</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-gray-500">Датум на објава</p>
                <p className="font-medium">{tender.publication_date ? formatDate(tender.publication_date) : '-'}</p>
              </div>
              <div>
                <p className="text-gray-500">Краен рок</p>
                <p className="font-medium">{tender.closing_date ? formatDate(tender.closing_date) : '-'}</p>
              </div>
              {tender.contract_date && (
                <div>
                  <p className="text-gray-500">Датум на договор</p>
                  <p className="font-medium">{formatDate(tender.contract_date)}</p>
                </div>
              )}
              <div>
                <p className="text-gray-500">Број на договор</p>
                <p className="font-medium">{tender.contract_number || tender.tender_id}</p>
              </div>
              {tender.category && (
                <div>
                  <p className="text-gray-500">Категорија</p>
                  <p className="font-medium">{tender.category}</p>
                </div>
              )}
              <div>
                <p className="text-gray-500">Вид на постапка</p>
                <p className="font-medium">{tender.procedure_type || '-'}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
