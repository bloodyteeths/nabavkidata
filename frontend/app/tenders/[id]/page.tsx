"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { api, type Tender, type RAGQueryResponse } from "@/lib/api";
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
} from "lucide-react";
import Link from "next/link";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  sources?: RAGQueryResponse["sources"];
}

export default function TenderDetailPage() {
  const params = useParams();
  const tenderId = params.id as string;

  const [tender, setTender] = useState<Tender | null>(null);
  const [loading, setLoading] = useState(true);
  const [chatMessages, setChatMessages] = useState<ChatMsg[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [aiSummary, setAiSummary] = useState<string>("");
  const [summaryLoading, setSummaryLoading] = useState(false);

  useEffect(() => {
    loadTender();
    generateSummary();
  }, [tenderId]);

  async function loadTender() {
    try {
      setLoading(true);
      const result = await api.getTender(tenderId);
      setTender(result);
    } catch (error) {
      console.error("Failed to load tender:", error);
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
    } finally {
      setSummaryLoading(false);
    }
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

  const logBehavior = async (action: string) => {
    try {
      await api.logBehavior("demo-user-id", {
        tender_id: tenderId,
        action,
        duration_seconds: 0,
      });
    } catch (error) {
      console.error("Failed to log behavior:", error);
    }
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
          <h1 className="text-3xl font-bold">{tender.title}</h1>
          <div className="flex items-center gap-2 mt-2">
            {tender.status && <Badge>{tender.status}</Badge>}
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
          <Button>
            <ExternalLink className="h-4 w-4 mr-2" />
            Отвори
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
                  {tender.estimated_value_mkd && (
                    <div className="flex items-start gap-3">
                      <Tag className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">Проценета вредност</p>
                        <p className="text-sm text-muted-foreground">
                          {formatCurrency(tender.estimated_value_mkd)}
                        </p>
                      </div>
                    </div>
                  )}
                  {tender.cpv_code && (
                    <div className="flex items-start gap-3">
                      <FileText className="h-5 w-5 text-muted-foreground mt-0.5" />
                      <div>
                        <p className="text-sm font-medium">CPV Код</p>
                        <p className="text-sm text-muted-foreground">{tender.cpv_code}</p>
                      </div>
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
