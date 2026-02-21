"use client";

import { useState, useRef, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MessageSquare, Sparkles, AlertCircle, ArrowRight, Zap, Bell, Plus } from "lucide-react";
import { api } from "@/lib/api";
import Link from "next/link";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Array<{
    tender_id?: string;
    doc_id?: string;
    chunk_text: string;
    similarity: number;
  }>;
  confidence?: string;
  timestamp?: Date;
}

interface UsageStatus {
  tier: string;
  daily_queries_used: number;
  daily_queries_limit: number;
  is_blocked: boolean;
  is_trial_expired: boolean;
  trial_ends_at?: string;
}

const SUGGESTED_QUESTIONS = [
  "Кои се најголемите тендери овој месец?",
  "Покажи ми ИТ тендери",
  "Која институција објавува најмногу тендери?",
];

const ALERTS_SUGGESTED_QUESTIONS = [
  "Сумирај ги моите алерти",
  "Кои тендери можам да учествувам?",
  "Покажи ми најголемите совпаѓања по вредност",
  "Кои рокови истекуваат наскоро?",
];

export default function ChatPageWrapper() {
  return (
    <Suspense fallback={
      <div className="flex flex-col h-screen bg-background items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    }>
      <ChatPage />
    </Suspense>
  );
}

function ChatPage() {
  const searchParams = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [usageStatus, setUsageStatus] = useState<UsageStatus | null>(null);
  const [loadingUsage, setLoadingUsage] = useState(true);
  const [isHydrated, setIsHydrated] = useState(false);
  const [alertsMode, setAlertsMode] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Hydration guard
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Load session from URL param or restore last session
  useEffect(() => {
    if (!isHydrated) return;
    const urlSessionId = searchParams.get('session');
    if (urlSessionId) {
      setSessionId(urlSessionId);
      // Load session messages from server
      api.getChatSession(urlSessionId)
        .then((data) => {
          if (data?.messages) {
            setMessages(
              data.messages.map((m) => ({
                id: m.message_id,
                role: m.role as 'user' | 'assistant',
                content: m.content,
                sources: m.sources,
                confidence: m.confidence || undefined,
                timestamp: m.created_at ? new Date(m.created_at) : undefined,
              }))
            );
          }
        })
        .catch((err) => console.error('Failed to load session:', err));
    }
  }, [isHydrated, searchParams]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    loadUsageStatus();
  }, []);

  const loadUsageStatus = async () => {
    try {
      setLoadingUsage(true);
      const status = await api.getSubscriptionStatus();
      setUsageStatus(status);
    } catch (error) {
      console.error("Failed to load usage status:", error);
      // Default to free tier if error
      setUsageStatus({
        tier: 'free',
        daily_queries_used: 0,
        daily_queries_limit: 3,
        is_blocked: false,
        is_trial_expired: false
      });
    } finally {
      setLoadingUsage(false);
    }
  };

  const handleSendMessage = async (content: string) => {
    // Check if user is blocked or exceeded limits
    if (usageStatus?.is_blocked || usageStatus?.is_trial_expired) {
      return;
    }

    if (usageStatus && usageStatus.daily_queries_limit !== -1 && usageStatus.daily_queries_used >= usageStatus.daily_queries_limit) {
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    scrollToBottom();

    try {
      // Server handles conversation history via session — no need to send from client
      const response = await api.queryRAG(
        content,
        undefined,
        undefined,
        alertsMode ? 'alerts' : undefined,
        sessionId || undefined
      );

      // Capture session_id from first response (auto-created on server)
      if (response.session_id && !sessionId) {
        setSessionId(response.session_id);
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.answer,
        sources: response.sources,
        confidence: response.confidence,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Reload usage status after successful query
      await loadUsageStatus();
    } catch (error: any) {
      console.error("RAG query error:", error);
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Се случи грешка: ${error?.message || error?.detail || 'Непозната грешка'}. Ве молиме обидете се повторно.`,
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setSessionId(null);
    // Clear URL session param if present
    if (searchParams.get('session')) {
      window.history.replaceState({}, '', '/chat');
    }
  };

  const handleSuggestedQuestion = (question: string) => {
    handleSendMessage(question);
  };

  const isLimitReached = usageStatus && usageStatus.daily_queries_limit !== -1 && usageStatus.daily_queries_used >= usageStatus.daily_queries_limit;
  const isBlocked = usageStatus?.is_blocked || usageStatus?.is_trial_expired;
  const remainingQueries = usageStatus ? Math.max(0, usageStatus.daily_queries_limit - usageStatus.daily_queries_used) : 0;
  const currentTier = usageStatus?.tier?.toLowerCase() || "free";
  const isFreeTier = currentTier === "free";

  // Show loading until hydrated
  if (!isHydrated) {
    return (
      <div className="flex flex-col h-screen bg-background items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header with Usage Stats */}
      <div className="border-b bg-card">
        <div className="container mx-auto px-3 md:px-4 py-3 md:py-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-0">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 md:h-10 md:w-10 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
                <MessageSquare className="h-4 w-4 md:h-5 md:w-5 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-lg md:text-xl font-bold">AI Асистент</h1>
                <p className="text-xs md:text-sm text-muted-foreground">Поставете прашања за тендерите</p>
              </div>
            </div>
            <div className="flex items-center justify-between sm:justify-end gap-2 md:gap-4 w-full sm:w-auto">
              {/* Usage Indicator */}
              {!loadingUsage && usageStatus && (
                <div className="flex items-center gap-2 px-2 py-1.5 md:px-4 md:py-2 rounded-lg border border-primary/20 bg-primary/5">
                  <Zap className="h-3 w-3 md:h-4 md:w-4 text-primary" />
                  <div className="text-xs md:text-sm">
                    <span className="font-medium">{remainingQueries}</span>
                    <span className="text-muted-foreground hidden sm:inline"> / {usageStatus.daily_queries_limit} остануваат денес</span>
                    <span className="text-muted-foreground sm:hidden"> / {usageStatus.daily_queries_limit}</span>
                  </div>
                  <Badge variant="outline" className="ml-1 md:ml-2 bg-background capitalize text-[10px] md:text-xs px-1.5 py-0">
                    {usageStatus.tier}
                  </Badge>
                </div>
              )}
              <Button
                variant={alertsMode ? 'default' : 'outline'}
                size="sm"
                onClick={() => setAlertsMode(!alertsMode)}
                className="gap-1 md:gap-2 h-8 md:h-9 text-xs md:text-sm px-2 md:px-3"
                title={alertsMode ? 'Алерт режим активен' : 'Анализирај ги моите алерти'}
              >
                <Bell className="h-3 w-3 md:h-4 md:w-4" />
                <span className="hidden sm:inline">{alertsMode ? 'Алерт режим' : 'Мои алерти'}</span>
              </Button>
              {messages.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleNewChat}
                  className="gap-1 md:gap-2 h-8 md:h-9 text-xs md:text-sm px-2 md:px-3"
                >
                  <Plus className="h-3 w-3 md:h-4 md:w-4" />
                  <span className="hidden sm:inline">Нов разговор</span>
                  <span className="sm:hidden">Нов</span>
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Limit Reached Banner */}
      {(isLimitReached || isBlocked) && (
        <div className="border-b bg-orange-500/10 border-orange-500/20">
          <div className="container mx-auto px-3 md:px-4 py-2 md:py-3">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 sm:gap-0">
              <div className="flex items-start sm:items-center gap-2 md:gap-3">
                <AlertCircle className="h-4 w-4 md:h-5 md:w-5 text-orange-400 mt-0.5 sm:mt-0 flex-shrink-0" />
                <div>
                  <p className="text-xs md:text-sm font-medium text-orange-400">
                    {isBlocked
                      ? usageStatus?.is_trial_expired
                        ? "Вашиот пробен период истече. Надоградете за да продолжите."
                        : "Вашата сметка е блокирана."
                      : "Го достигнавте дневниот лимит на пребарувања."
                    }
                  </p>
                  <p className="text-[10px] md:text-xs text-muted-foreground">
                    {isBlocked
                      ? "Одберете платен план за неограничен пристап."
                      : "Надоградете го вашиот план за повеќе дневни пребарувања."
                    }
                  </p>
                </div>
              </div>
              <Link href="/settings" className="w-full sm:w-auto">
                <Button className="gap-2 w-full sm:w-auto h-8 md:h-10 text-xs md:text-sm">
                  <ArrowRight className="h-3 w-3 md:h-4 md:w-4" />
                  Надогради сега
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="container mx-auto px-3 md:px-4 py-4 md:py-6 max-w-4xl">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full space-y-6 md:space-y-8 py-8">
              <div className="text-center space-y-3 md:space-y-4">
                <div className="h-12 w-12 md:h-16 md:w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                  <Sparkles className="h-6 w-6 md:h-8 md:w-8 text-primary" />
                </div>
                <div>
                  <h2 className="text-xl md:text-2xl font-bold">
                    {alertsMode ? 'Анализа на Алерти' : 'Добредојдовте во AI Асистентот'}
                  </h2>
                  <p className="text-sm md:text-base text-muted-foreground mt-1 md:mt-2 px-4">
                    {alertsMode
                      ? 'Прашајте за вашите совпаѓања со алерти'
                      : 'Поставете прашање за тендерите или изберете од предлозите подолу'}
                  </p>
                </div>
              </div>

              <div className="w-full max-w-2xl space-y-2 md:space-y-3">
                <p className="text-xs md:text-sm font-medium text-muted-foreground px-1">Предложени прашања:</p>
                <div className="grid gap-2 md:gap-3">
                  {(alertsMode ? ALERTS_SUGGESTED_QUESTIONS : SUGGESTED_QUESTIONS).map((question, index) => (
                    <Card
                      key={index}
                      className={`p-3 md:p-4 transition-colors ${isLimitReached || isBlocked
                          ? 'opacity-50 cursor-not-allowed'
                          : 'cursor-pointer hover:bg-accent'
                        }`}
                      onClick={() => !isLimitReached && !isBlocked && handleSuggestedQuestion(question)}
                    >
                      <div className="flex items-start gap-2 md:gap-3">
                        <MessageSquare className="h-4 w-4 md:h-5 md:w-5 text-muted-foreground mt-0.5 flex-shrink-0" />
                        <p className="text-xs md:text-sm">{question}</p>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>

              {/* Current Plan Info */}
              {usageStatus && !loadingUsage && (
                <Card className="max-w-md p-3 md:p-4 bg-primary/5 border-primary/20 w-full">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs md:text-sm font-medium">Тековен план: <span className="capitalize">{usageStatus.tier}</span></p>
                      <p className="text-[10px] md:text-xs text-muted-foreground mt-0.5 md:mt-1">
                        {usageStatus.daily_queries_limit === -1 ? 'Неограничени' : usageStatus.daily_queries_limit} пребарувања дневно
                      </p>
                    </div>
                    {usageStatus.tier === 'free' && (
                      <Link href="/settings">
                        <Button size="sm" variant="outline" className="h-7 md:h-9 text-xs">
                          Надогради
                        </Button>
                      </Link>
                    )}
                  </div>
                </Card>
              )}
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((message) => (
                <div key={message.id}>
                  <ChatMessage
                    role={message.role}
                    content={message.content}
                    sources={message.sources}
                    confidence={message.confidence}
                    timestamp={message.timestamp}
                    messageId={message.id}
                    onFeedback={async (msgId, helpful) => {
                      // Find the previous user message to get the question
                      const msgIndex = messages.findIndex(m => m.id === msgId);
                      if (msgIndex <= 0) return;

                      // Find the user question that preceded this answer
                      let questionMsg: Message | undefined;
                      for (let i = msgIndex - 1; i >= 0; i--) {
                        if (messages[i].role === 'user') {
                          questionMsg = messages[i];
                          break;
                        }
                      }

                      if (!questionMsg) return;

                      try {
                        await api.submitChatFeedback({
                          message_id: msgId,
                          question: questionMsg.content,
                          answer: message.content,
                          helpful,
                        });
                      } catch (error) {
                        console.error('Failed to submit feedback:', error);
                      }
                    }}
                  />
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-3 items-start">
                  <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                    <MessageSquare className="h-4 w-4 text-primary-foreground" />
                  </div>
                  <Card className="p-3 bg-muted/70 border-dashed w-full">
                    <p className="text-xs text-muted-foreground mb-2">AI одговара...</p>
                    <div className="space-y-2">
                      <div className="h-2 w-full rounded bg-muted-foreground/30 animate-pulse" />
                      <div className="h-2 w-5/6 rounded bg-muted-foreground/20 animate-pulse" />
                      <div className="h-2 w-2/3 rounded bg-muted-foreground/10 animate-pulse" />
                    </div>
                  </Card>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Input Area */}
      <div className="border-t bg-card">
        <div className="container mx-auto px-3 md:px-4 py-3 md:py-4 max-w-4xl">
          <ChatInput
            onSend={handleSendMessage}
            disabled={isLoading || isLimitReached || isBlocked || isFreeTier}
            placeholder={
              isBlocked
                ? "Надоградете го вашиот план за да продолжите..."
                : isLimitReached
                  ? "Дневен лимит достигнат. Надоградете за повеќе..."
                  : isFreeTier
                    ? "Free план: надоградете за да поставувате AI прашања..."
                    : "Постави прашање за тендерите..."
            }
          />
          <p className="text-[10px] md:text-xs text-muted-foreground mt-2 text-center px-2">
            AI асистентот користи напредна обработка на природен јазик за одговарање на вашите прашања
          </p>
          {isFreeTier && (
            <div className="mt-2 md:mt-3 rounded-md border border-amber-200 bg-amber-100 p-2 md:p-3 text-xs md:text-sm flex items-center justify-between">
              <span>Free план: надоградете за да користите AI чат.</span>
              <Link href="/settings">
                <Button size="sm" variant="outline" className="h-7 md:h-9 text-xs">Upgrade</Button>
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Badge({ children, variant, className }: { children: React.ReactNode; variant?: string; className?: string }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${className || ''}`}>
      {children}
    </span>
  );
}
