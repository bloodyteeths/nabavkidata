"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { api, type Tender, type TenderDocument, type RAGQueryResponse, type TenderBidder, type TenderLot } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/utils";
import {
  ArrowLeft,
  Building2,
  Calendar,
  Tag,
  FileText,
  MessageSquare,
  Bookmark,
  ExternalLink,
  Sparkles,
  Download,
  File,
  User,
  Mail,
  Phone,
  Briefcase,
  Users,
  Package,
  Trophy,
  XCircle,
  Award,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  sources?: RAGQueryResponse["sources"];
}

export default function TenderDetailPage() {
  const params = useParams();
  const tenderId = decodeURIComponent(params.id as string);

  const [tender, setTender] = useState<Tender | null>(null);
  const [loading, setLoading] = useState(true);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [aiSummary, setAiSummary] = useState<string>("");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [notifyEnabled, setNotifyEnabled] = useState(false);
  const [documents, setDocuments] = useState<TenderDocument[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [bidders, setBidders] = useState<TenderBidder[]>([]);
  const [biddersLoading, setBiddersLoading] = useState(false);
  const [lots, setLots] = useState<TenderLot[]>([]);
  const [lotsLoading, setLotsLoading] = useState(false);
  const [hasLots, setHasLots] = useState(false);

  useEffect(() => {
    loadTender();
    generateSummary();
    loadNotifyPreference();
    loadDocuments();
    loadBidders();
    loadLots();
  }, [tenderId]);

  async function loadTender() {
    try {
      setLoading(true);
      const result = await api.getTender(tenderId);
      setTender(result);
    } catch (error) {
      console.error("Failed to load tender:", error);
      toast.error("Не успеавме да го вчитаме тендерот.");
    } finally {
      setLoading(false);
    }
  }

  async function generateSummary() {
    try {
      setSummaryLoading(true);
      const result = await api.queryRAG(
        "Дај ми краток резиме на овој тендер во 3-4 реченици.",
        tenderId
      );
      setAiSummary(result.answer);
    } catch (error) {
      console.error("Failed to generate summary:", error);
      setAiSummary("Неможе да се генерира резиме.");
      toast.error("AI резимето не може да се генерира моментално.");
    } finally {
      setSummaryLoading(false);
    }
  }

  async function loadDocuments() {
    try {
      setDocumentsLoading(true);
      const result = await api.getTenderDocuments(tenderId);
      setDocuments(result.documents || []);
    } catch (error) {
      console.error("Failed to load documents:", error);
      setDocuments([]);
    } finally {
      setDocumentsLoading(false);
    }
  }

  async function loadBidders() {
    try {
      // Parse tender ID (format: "12345/2025")
      const parts = tenderId.split('/');
      if (parts.length !== 2) {
        console.log("Invalid tender ID format for bidders");
        return;
      }
      const [tenderNumber, tenderYear] = parts;
      setBiddersLoading(true);
      const result = await api.getTenderBidders(tenderNumber, tenderYear);
      setBidders(result.bidders || []);
    } catch (error) {
      console.error("Failed to load bidders:", error);
      setBidders([]);
    } finally {
      setBiddersLoading(false);
    }
  }

  async function loadLots() {
    try {
      // Parse tender ID (format: "12345/2025")
      const parts = tenderId.split('/');
      if (parts.length !== 2) {
        console.log("Invalid tender ID format for lots");
        return;
      }
      const [tenderNumber, tenderYear] = parts;
      setLotsLoading(true);
      const result = await api.getTenderLots(tenderNumber, tenderYear);
      setLots(result.lots || []);
      setHasLots(result.has_lots || false);
    } catch (error) {
      console.error("Failed to load lots:", error);
      setLots([]);
      setHasLots(false);
    } finally {
      setLotsLoading(false);
    }
  }

  function formatFileSize(bytes?: number): string {
    if (!bytes) return "";
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
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
      toast.error("AI одговорот не успеа. Обидете се повторно.");
    } finally {
      setChatLoading(false);
    }
  }

  const logBehavior = async (action: string) => {
    try {
      // Get user ID from localStorage if authenticated
      const userId = typeof window !== 'undefined' ? localStorage.getItem('user_id') || 'anonymous' : 'anonymous';
      await api.logBehavior(userId, {
        tender_id: tenderId,
        action,
        duration_seconds: 0,
      });
    } catch (error) {
      console.error("Failed to log behavior:", error);
    }
  };

  const loadNotifyPreference = () => {
    try {
      const stored = localStorage.getItem("followed_tenders");
      if (!stored) return;
      const parsed: string[] = JSON.parse(stored);
      setNotifyEnabled(parsed.includes(tenderId));
    } catch {
      // ignore
    }
  };

  const toggleNotify = () => {
    try {
      const stored = localStorage.getItem("followed_tenders");
      const parsed: string[] = stored ? JSON.parse(stored) : [];
      let updated: string[];
      if (parsed.includes(tenderId)) {
        updated = parsed.filter((id) => id !== tenderId);
        setNotifyEnabled(false);
        toast.success("Известувањата се исклучени за овој тендер.");
      } else {
        updated = [...parsed, tenderId];
        setNotifyEnabled(true);
        toast.success("Ќе добивате известувања за овој тендер (само активни).");
      }
      localStorage.setItem("followed_tenders", JSON.stringify(updated));
      void logBehavior("notify_toggle");
    } catch {
      toast.error("Не може да се зачува поставката за известувања.");
    }
  };

  const quickPrompts = [
    "Кои се главните услови и документи?",
    "Какви се критериумите за евалуација?",
    "Постојат ли гаранции или депозити?",
  ];

  const handleOpenSource = () => {
    if (!tender?.source_url) return;
    void logBehavior("open_source");
    window.open(tender.source_url, "_blank", "noopener,noreferrer");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Се вчитува...</p>
      </div>
    );
  }

  if (!tender) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <p className="text-muted-foreground">Тендерот не е пронајден</p>
        <Button asChild variant="outline">
          <Link href="/tenders">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад на тендери
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <Button asChild variant="ghost" size="sm" className="mb-2">
            <Link href="/tenders">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Назад
            </Link>
          </Button>
          <h1 className="text-3xl font-bold">{tender.title || "Без наслов"}</h1>
          <div className="flex items-center gap-2 mt-2">
            {tender.status ? <Badge>{tender.status}</Badge> : <Badge variant="outline">активен</Badge>}
            {tender.category && <Badge variant="outline">{tender.category}</Badge>}
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => logBehavior("save")}
          >
            <Bookmark className="h-4 w-4 mr-2" />
            Зачувај
          </Button>
          <Button
            variant={notifyEnabled ? "default" : "outline"}
            onClick={toggleNotify}
          >
            <Sparkles className="h-4 w-4 mr-2" />
            {notifyEnabled ? "Известувања вклучени" : "Вклучи известувања"}
          </Button>
          <Button
            onClick={handleOpenSource}
            disabled={!tender.source_url}
            variant={tender.source_url ? "default" : "outline"}
          >
            <ExternalLink className="h-4 w-4 mr-2" />
            {tender.source_url ? "Отвори извор" : "Нема извор"}
          </Button>
        </div>
      </div>

      {/* AI Summary */}
      <Card className="border-primary/50 bg-primary/5">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            AI Резиме
          </CardTitle>
        </CardHeader>
        <CardContent>
          {summaryLoading ? (
            <p className="text-sm text-muted-foreground">Генерирање...</p>
          ) : (
            <p className="text-sm">{aiSummary}</p>
          )}
        </CardContent>
      </Card>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Details */}
        <div className="lg:col-span-2 space-y-6">
          <Tabs defaultValue="details">
            <TabsList>
              <TabsTrigger value="details">
                <FileText className="h-4 w-4 mr-2" />
                Детали
              </TabsTrigger>
              <TabsTrigger value="documents">
                <File className="h-4 w-4 mr-2" />
                Документи ({documents.length})
              </TabsTrigger>
              <TabsTrigger value="bidders">
                <Users className="h-4 w-4 mr-2" />
                Понудувачи ({bidders.length})
              </TabsTrigger>
              {hasLots && (
                <TabsTrigger value="lots">
                  <Package className="h-4 w-4 mr-2" />
                  Лотови ({lots.length})
                </TabsTrigger>
              )}
              <TabsTrigger value="chat">
                <MessageSquare className="h-4 w-4 mr-2" />
                AI Асистент
              </TabsTrigger>
            </TabsList>

            <TabsContent value="details" className="space-y-4 mt-4">
              {/* Description */}
              {tender.description && (
                <Card>
                  <CardHeader>
                    <CardTitle>Опис</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm whitespace-pre-wrap">{tender.description}</p>
                  </CardContent>
                </Card>
              )}

              {/* Metadata */}
              <Card>
                <CardHeader>
                  <CardTitle>Информации</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {tender.procuring_entity && (
                    <div className="flex items-start gap-3">
                      <Building2 className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Институција</p>
                        <p className="text-sm text-muted-foreground">{tender.procuring_entity}</p>
                      </div>
                    </div>
                  )}
                  {tender.procedure_type && (
                    <div className="flex items-start gap-3">
                      <Briefcase className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Тип на постапка</p>
                        <Badge variant="secondary">{tender.procedure_type}</Badge>
                      </div>
                    </div>
                  )}
                  {tender.evaluation_method && (
                    <div className="flex items-start gap-3">
                      <Award className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Метод на евалуација</p>
                        <p className="text-sm text-muted-foreground">{tender.evaluation_method}</p>
                      </div>
                    </div>
                  )}
                  {tender.estimated_value_mkd && (
                    <div className="flex items-start gap-3">
                      <Tag className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Проценета вредност</p>
                        <p className="text-sm font-semibold text-primary">
                          {formatCurrency(tender.estimated_value_mkd)}
                        </p>
                      </div>
                    </div>
                  )}
                  {tender.actual_value_mkd && (
                    <div className="flex items-start gap-3">
                      <Trophy className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Договорена вредност</p>
                        <p className="text-sm font-semibold text-green-600">
                          {formatCurrency(tender.actual_value_mkd)}
                        </p>
                      </div>
                    </div>
                  )}
                  {tender.cpv_code && (
                    <div className="flex items-start gap-3">
                      <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">CPV Код</p>
                        <p className="text-sm text-muted-foreground font-mono">{tender.cpv_code}</p>
                      </div>
                    </div>
                  )}
                  {tender.num_bidders !== undefined && tender.num_bidders !== null && (
                    <div className="flex items-start gap-3">
                      <Users className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Број на понудувачи</p>
                        <p className="text-sm text-muted-foreground">{tender.num_bidders}</p>
                      </div>
                    </div>
                  )}
                  {tender.winner && (
                    <div className="flex items-start gap-3">
                      <Trophy className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Добитник</p>
                        <p className="text-sm text-muted-foreground">{tender.winner}</p>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Contact Information */}
              {(tender.contact_person || tender.contact_email || tender.contact_phone) && (
                <Card>
                  <CardHeader>
                    <CardTitle>Контакт информации</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {tender.contact_person && (
                      <div className="flex items-start gap-3">
                        <User className="h-5 w-5 text-muted-foreground mt-0.5" />
                        <div>
                          <p className="text-sm font-medium">Контакт лице</p>
                          <p className="text-sm text-muted-foreground">{tender.contact_person}</p>
                        </div>
                      </div>
                    )}
                    {tender.contact_email && (
                      <div className="flex items-start gap-3">
                        <Mail className="h-5 w-5 text-muted-foreground mt-0.5" />
                        <div>
                          <p className="text-sm font-medium">Е-пошта</p>
                          <a
                            href={`mailto:${tender.contact_email}`}
                            className="text-sm text-primary hover:underline"
                          >
                            {tender.contact_email}
                          </a>
                        </div>
                      </div>
                    )}
                    {tender.contact_phone && (
                      <div className="flex items-start gap-3">
                        <Phone className="h-5 w-5 text-muted-foreground mt-0.5" />
                        <div>
                          <p className="text-sm font-medium">Телефон</p>
                          <a
                            href={`tel:${tender.contact_phone}`}
                            className="text-sm text-primary hover:underline"
                          >
                            {tender.contact_phone}
                          </a>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </TabsContent>

            <TabsContent value="documents" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Тендерска документација</CardTitle>
                  <CardDescription>
                    Преземете ги документите поврзани со овој тендер
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {documentsLoading ? (
                    <p className="text-sm text-muted-foreground">Се вчитуваат документи...</p>
                  ) : documents.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground">
                      <File className="h-12 w-12 mb-2 opacity-20" />
                      <p className="text-sm">Нема достапни документи</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {documents.map((doc) => (
                        <div
                          key={doc.doc_id}
                          className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                        >
                          <div className="flex items-center gap-3 flex-1 min-w-0">
                            <File className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium truncate">
                                {doc.file_name || "Непознат документ"}
                              </p>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                {doc.doc_type && <span>{doc.doc_type}</span>}
                                {doc.file_size_bytes && (
                                  <span>{formatFileSize(doc.file_size_bytes)}</span>
                                )}
                                {doc.page_count && <span>{doc.page_count} страници</span>}
                              </div>
                            </div>
                          </div>
                          {doc.file_url && (
                            <Button
                              variant="outline"
                              size="sm"
                              asChild
                            >
                              <a
                                href={doc.file_url}
                                target="_blank"
                                rel="noopener noreferrer"
                              >
                                <Download className="h-4 w-4 mr-1" />
                                Преземи
                              </a>
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="bidders" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Понудувачи</CardTitle>
                  <CardDescription>
                    Список на сите понудувачи кои аплицирале за овој тендер
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {biddersLoading ? (
                    <p className="text-sm text-muted-foreground">Се вчитуваат понудувачи...</p>
                  ) : bidders.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground">
                      <Users className="h-12 w-12 mb-2 opacity-20" />
                      <p className="text-sm">Нема понудувачи</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {bidders.map((bidder) => (
                        <div
                          key={bidder.bidder_id}
                          className="flex items-start justify-between p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
                        >
                          <div className="flex-1 space-y-2">
                            <div className="flex items-center gap-2">
                              <p className="text-sm font-semibold">{bidder.company_name}</p>
                              {bidder.is_winner && (
                                <Badge variant="default" className="bg-green-600">
                                  <Trophy className="h-3 w-3 mr-1" />
                                  Добитник
                                </Badge>
                              )}
                              {bidder.is_disqualified && (
                                <Badge variant="destructive">
                                  <XCircle className="h-3 w-3 mr-1" />
                                  Дисквалификуван
                                </Badge>
                              )}
                            </div>
                            {bidder.tax_id && (
                              <p className="text-xs text-muted-foreground">
                                Даночен број: {bidder.tax_id}
                              </p>
                            )}
                            <div className="flex items-center gap-4 text-sm">
                              {bidder.bid_amount_mkd && (
                                <div>
                                  <span className="text-muted-foreground">Понуда: </span>
                                  <span className="font-semibold text-primary">
                                    {formatCurrency(bidder.bid_amount_mkd)}
                                  </span>
                                </div>
                              )}
                              {bidder.rank && (
                                <div>
                                  <span className="text-muted-foreground">Ранг: </span>
                                  <span className="font-semibold">#{bidder.rank}</span>
                                </div>
                              )}
                            </div>
                            {bidder.is_disqualified && bidder.disqualification_reason && (
                              <p className="text-xs text-destructive">
                                Причина: {bidder.disqualification_reason}
                              </p>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="lots" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>Лотови</CardTitle>
                  <CardDescription>
                    Поделба на тендерот на лотови/ставки
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {lotsLoading ? (
                    <p className="text-sm text-muted-foreground">Се вчитуваат лотови...</p>
                  ) : lots.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground">
                      <Package className="h-12 w-12 mb-2 opacity-20" />
                      <p className="text-sm">Нема лотови</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {lots.map((lot) => (
                        <div
                          key={lot.lot_id}
                          className="p-4 rounded-lg border bg-card"
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div>
                              <div className="flex items-center gap-2 mb-1">
                                <Badge variant="outline">Лот #{lot.lot_number}</Badge>
                                {lot.winner && (
                                  <Badge variant="default" className="bg-green-600">
                                    <Trophy className="h-3 w-3 mr-1" />
                                    Доделен
                                  </Badge>
                                )}
                              </div>
                              <h4 className="text-sm font-semibold">{lot.title}</h4>
                            </div>
                          </div>
                          {lot.description && (
                            <p className="text-xs text-muted-foreground mb-2">
                              {lot.description}
                            </p>
                          )}
                          <div className="grid grid-cols-2 gap-3 text-sm">
                            {lot.estimated_value_mkd && (
                              <div>
                                <p className="text-xs text-muted-foreground">Проценета вредност</p>
                                <p className="font-semibold text-primary">
                                  {formatCurrency(lot.estimated_value_mkd)}
                                </p>
                              </div>
                            )}
                            {lot.actual_value_mkd && (
                              <div>
                                <p className="text-xs text-muted-foreground">Договорена вредност</p>
                                <p className="font-semibold text-green-600">
                                  {formatCurrency(lot.actual_value_mkd)}
                                </p>
                              </div>
                            )}
                            {lot.cpv_code && (
                              <div>
                                <p className="text-xs text-muted-foreground">CPV Код</p>
                                <p className="font-mono text-xs">{lot.cpv_code}</p>
                              </div>
                            )}
                            {lot.winner && (
                              <div>
                                <p className="text-xs text-muted-foreground">Добитник</p>
                                <p className="font-semibold text-xs">{lot.winner}</p>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="chat" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle>AI Асистент за Тендери</CardTitle>
                  <CardDescription>
                    Постави прашања за овој тендер
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Chat Messages */}
                  <div className="space-y-4 min-h-[400px] max-h-[500px] overflow-y-auto">
                    {chatMessages.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-full text-center text-muted-foreground">
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
                      <div className="text-sm text-muted-foreground">AI пишува...</div>
                    )}
                  </div>

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
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-4">
          {/* Dates */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Важни датуми</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {tender.opening_date && (
                <div className="flex items-start gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground mt-0.5" />
                  <div>
                    <p className="text-xs font-medium">Отворен</p>
                    <p className="text-sm">{formatDate(tender.opening_date)}</p>
                  </div>
                </div>
              )}
              {tender.closing_date && (
                <div className="flex items-start gap-2">
                  <Calendar className="h-4 w-4 text-muted-foreground mt-0.5" />
                  <div>
                    <p className="text-xs font-medium">Рок</p>
                    <p className="text-sm">{formatDate(tender.closing_date)}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Quick Actions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Акции</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => logBehavior("share")}
              >
                <ExternalLink className="h-4 w-4 mr-2" />
                Сподели
              </Button>
              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => logBehavior("save")}
              >
                <Bookmark className="h-4 w-4 mr-2" />
                Зачувај
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
