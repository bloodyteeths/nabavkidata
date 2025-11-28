'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
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
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  MessageSquare
} from 'lucide-react';
import { api, EPazarTenderDetail, EPazarItem, EPazarOffer, EPazarDocument, EPazarAwardedItem, RAGQueryResponse } from '@/lib/api';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatCurrency, formatDate } from '@/lib/utils';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { PriceHistoryChart } from '@/components/charts/PriceHistoryChart';

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

function ItemsTable({ items }: { items: EPazarItem[] }) {
  if (!items || items.length === 0) {
    return <p className="text-gray-500 text-center py-8">No items found</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b">
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">#</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Item Name</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Quantity</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Unit</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Unit Price</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Total</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, idx) => (
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
              <td className="py-3 px-4 text-right text-sm">{formatCurrency(item.estimated_unit_price_mkd)}</td>
              <td className="py-3 px-4 text-right text-sm font-medium">{formatCurrency(item.estimated_total_price_mkd)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OffersTable({ offers }: { offers: EPazarOffer[] }) {
  if (!offers || offers.length === 0) {
    return <p className="text-gray-500 text-center py-8">No offers submitted</p>;
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
                      Winner
                    </Badge>
                  )}
                  {offer.disqualified && (
                    <Badge variant="destructive">
                      <XCircle className="h-3 w-3 mr-1" />
                      Disqualified
                    </Badge>
                  )}
                </div>
                {offer.supplier_tax_id && (
                  <p className="text-sm text-gray-500">Tax ID: {offer.supplier_tax_id}</p>
                )}
                {offer.supplier_city && (
                  <p className="text-sm text-gray-500">{offer.supplier_city}</p>
                )}
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold">{formatCurrency(offer.total_bid_mkd)}</div>
                {offer.ranking && (
                  <p className="text-sm text-gray-500">Rank: #{offer.ranking}</p>
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
    return <p className="text-gray-500 text-center py-8">No awarded items</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b">
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Supplier</th>
            <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Item</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Quantity</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Unit Price</th>
            <th className="text-right py-3 px-4 text-sm font-medium text-gray-500">Total</th>
            <th className="text-center py-3 px-4 text-sm font-medium text-gray-500">Status</th>
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

function DocumentsList({ documents }: { documents: EPazarDocument[] }) {
  if (!documents || documents.length === 0) {
    return <p className="text-gray-500 text-center py-8">No documents available</p>;
  }

  return (
    <div className="space-y-2">
      {documents.map((doc, idx) => (
        <Card key={doc.doc_id || idx}>
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-gray-400" />
                <div>
                  <p className="font-medium">{doc.file_name || 'Document'}</p>
                  <div className="flex gap-2 text-xs text-gray-500">
                    {doc.doc_type && <span>{doc.doc_type}</span>}
                    {doc.file_size_bytes && (
                      <span>{(doc.file_size_bytes / 1024).toFixed(1)} KB</span>
                    )}
                  </div>
                </div>
              </div>
              {doc.file_url && (
                <a href={doc.file_url} target="_blank" rel="noopener noreferrer">
                  <Button variant="outline" size="sm">
                    <Download className="h-4 w-4 mr-1" />
                    Download
                  </Button>
                </a>
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [itemPriceHistory, setItemPriceHistory] = useState<Array<{ date: string; price_mkd?: number }>>([]);
  const [itemPriceLoading, setItemPriceLoading] = useState(false);
  const [itemPriceError, setItemPriceError] = useState<string | null>(null);
  const [supplierStats, setSupplierStats] = useState<any | null>(null);
  const [supplierStatsLoading, setSupplierStatsLoading] = useState(false);
  const [supplierStatsError, setSupplierStatsError] = useState<string | null>(null);

  useEffect(() => {
    loadTender();
  }, [tenderId]);

  async function loadTender() {
    setLoading(true);
    setError(null);

    try {
      const data = await api.getEPazarTender(tenderId);
      setTender(data);
      if (data.items && data.items.length > 0 && data.items[0].item_id) {
        void loadItemPriceHistory(data.items[0].item_id);
      }
      const winnerOffer = data.offers?.find((o) => (o as any).supplier_id || o.is_winner) as any;
      if (winnerOffer?.supplier_id) {
        void loadSupplierStats(winnerOffer.supplier_id);
      }
      // Generate summary after tender data is loaded
      void generateSummaryWithData(data);
    } catch (err) {
      console.error('Failed to load tender:', err);
      setError('Failed to load tender details');
    } finally {
      setLoading(false);
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
      const result = await api.queryRAG(message, tenderId);
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

  async function loadItemPriceHistory(itemId: string) {
    try {
      setItemPriceLoading(true);
      setItemPriceError(null);
      const result = await api.getEpazarItemPriceHistory(itemId);
      setItemPriceHistory(result.points || []);
    } catch (error) {
      console.error("Failed to load item price history:", error);
      setItemPriceHistory([]);
      setItemPriceError("Историјата на цени за овој артикл не е достапна.");
    } finally {
      setItemPriceLoading(false);
    }
  }

  async function loadSupplierStats(supplierId: string) {
    try {
      setSupplierStatsLoading(true);
      setSupplierStatsError(null);
      const result = await api.getEpazarSupplierStats(supplierId);
      setSupplierStats(result.stats || result);
    } catch (error) {
      console.error("Failed to load supplier stats:", error);
      setSupplierStats(null);
      setSupplierStatsError("Статистиките за добавувачот не се достапни.");
    } finally {
      setSupplierStatsLoading(false);
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
          <p className="text-red-500">{error || 'Tender not found'}</p>
          <Button variant="outline" className="mt-4" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Go Back
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
              Back to e-Pazar
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
                View Original
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
                  <p className="text-sm text-gray-500">Contracting Authority</p>
                  <p className="font-medium">{tender.contracting_authority || 'N/A'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <DollarSign className="h-5 w-5 text-green-500" />
                <div>
                  <p className="text-sm text-gray-500">Estimated Value</p>
                  <p className="font-medium">{formatCurrency(tender.estimated_value_mkd)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <Calendar className="h-5 w-5 text-orange-500" />
                <div>
                  <p className="text-sm text-gray-500">Closing Date</p>
                  <p className="font-medium">{formatDate(tender.closing_date)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-purple-500" />
                <div>
                  <p className="text-sm text-gray-500">Procedure Type</p>
                  <p className="font-medium">{tender.procedure_type || 'N/A'}</p>
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
              <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-700 whitespace-pre-wrap">{tender.description}</p>
            </CardContent>
          </Card>
        )}

        {/* Tabs for Items, Offers, Documents, AI Agent */}
        <Card>
          <Tabs defaultValue="items">
            <CardHeader>
              <div className="w-full overflow-x-auto pb-2">
                <TabsList className="w-full justify-start inline-flex min-w-max">
                  <TabsTrigger value="items" className="flex items-center gap-2">
                    <Package className="h-4 w-4" />
                    Items ({tender.items?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="offers" className="flex items-center gap-2">
                    <Users className="h-4 w-4" />
                    Offers ({tender.offers?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="awarded" className="flex items-center gap-2">
                    <Trophy className="h-4 w-4" />
                    Awarded ({tender.awarded_items?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="documents" className="flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Documents ({tender.documents?.length || 0})
                  </TabsTrigger>
                  <TabsTrigger value="chat" className="flex items-center gap-2">
                    <MessageSquare className="h-4 w-4" />
                    AI Асистент
                  </TabsTrigger>
                </TabsList>
              </div>
            </CardHeader>
            <CardContent>
              <TabsContent value="items">
                {itemPriceLoading ? (
                  <p className="text-sm text-gray-500 mb-3">Се вчитува историја на цени за артиклите...</p>
                ) : itemPriceError ? (
                  <p className="text-sm text-red-600 mb-3">{itemPriceError}</p>
                ) : itemPriceHistory.length > 0 ? (
                  <div className="mb-4">
                    <PriceHistoryChart
                      data={itemPriceHistory.map((p) => ({ date: formatDate(p.date), price_mkd: p.price_mkd }))}
                      series={[{ key: "price_mkd", label: "Цена" }]}
                      title="Историја на цени за артиклите"
                    />
                  </div>
                ) : null}
                <ItemsTable items={tender.items || []} />
              </TabsContent>
              <TabsContent value="offers">
                <OffersTable offers={tender.offers || []} />
                {supplierStatsLoading ? (
                  <p className="text-sm text-gray-500 mt-3">Се вчитуваат статистики за добавувачот...</p>
                ) : supplierStatsError ? (
                  <p className="text-sm text-red-600 mt-3">{supplierStatsError}</p>
                ) : supplierStats ? (
                  <Card className="mt-4">
                    <CardHeader>
                      <CardTitle className="text-base">Статистика на добавувач</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-gray-700 space-y-1">
                      {Object.entries(supplierStats).map(([key, value]) => (
                        <div key={key} className="flex justify-between">
                          <span className="capitalize">{key.replace(/_/g, " ")}</span>
                          <span className="font-medium">{typeof value === "number" ? value.toLocaleString() : String(value)}</span>
                        </div>
                      ))}
                    </CardContent>
                  </Card>
                ) : null}
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

        {/* Additional Details */}
        <Card>
          <CardHeader>
            <CardTitle>Additional Details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-gray-500">Publication Date</p>
                <p className="font-medium">{formatDate(tender.publication_date)}</p>
              </div>
              <div>
                <p className="text-gray-500">Award Date</p>
                <p className="font-medium">{formatDate(tender.award_date)}</p>
              </div>
              <div>
                <p className="text-gray-500">Contract Date</p>
                <p className="font-medium">{formatDate(tender.contract_date)}</p>
              </div>
              <div>
                <p className="text-gray-500">Contract Number</p>
                <p className="font-medium">{tender.contract_number || 'N/A'}</p>
              </div>
              <div>
                <p className="text-gray-500">CPV Code</p>
                <p className="font-medium">{tender.cpv_code || 'N/A'}</p>
              </div>
              <div>
                <p className="text-gray-500">Category</p>
                <p className="font-medium">{tender.category || 'N/A'}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
