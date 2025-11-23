"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MessageSquare, Sparkles, Trash2, AlertCircle, ArrowRight, Zap } from "lucide-react";
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

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [usageStatus, setUsageStatus] = useState<UsageStatus | null>(null);
  const [loadingUsage, setLoadingUsage] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

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

    if (usageStatus && usageStatus.daily_queries_used >= usageStatus.daily_queries_limit) {
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content,
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await api.queryRAG(content);

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.answer,
        sources: response.sources,
        confidence: response.confidence,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Reload usage status after successful query
      await loadUsageStatus();
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "Се случи грешка при обработката на вашето прашање. Ве молиме обидете се повторно.",
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
  };

  const handleSuggestedQuestion = (question: string) => {
    handleSendMessage(question);
  };

  const isLimitReached = usageStatus && usageStatus.daily_queries_used >= usageStatus.daily_queries_limit;
  const isBlocked = usageStatus?.is_blocked || usageStatus?.is_trial_expired;
  const remainingQueries = usageStatus ? Math.max(0, usageStatus.daily_queries_limit - usageStatus.daily_queries_used) : 0;

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header with Usage Stats */}
      <div className="border-b bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-primary flex items-center justify-center">
                <MessageSquare className="h-5 w-5 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-bold">AI Асистент</h1>
                <p className="text-sm text-muted-foreground">Поставете прашања за тендерите</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {/* Usage Indicator */}
              {!loadingUsage && usageStatus && (
                <div className="flex items-center gap-2 px-4 py-2 rounded-lg border border-primary/20 bg-primary/5">
                  <Zap className="h-4 w-4 text-primary" />
                  <div className="text-sm">
                    <span className="font-medium">{remainingQueries}</span>
                    <span className="text-muted-foreground"> / {usageStatus.daily_queries_limit} остануваат денес</span>
                  </div>
                  <Badge variant="outline" className="ml-2 bg-background capitalize">
                    {usageStatus.tier}
                  </Badge>
                </div>
              )}
              {messages.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearChat}
                  className="gap-2"
                >
                  <Trash2 className="h-4 w-4" />
                  Исчисти разговор
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Limit Reached Banner */}
      {(isLimitReached || isBlocked) && (
        <div className="border-b bg-orange-500/10 border-orange-500/20">
          <div className="container mx-auto px-4 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <AlertCircle className="h-5 w-5 text-orange-400" />
                <div>
                  <p className="text-sm font-medium text-orange-400">
                    {isBlocked
                      ? usageStatus?.is_trial_expired
                        ? "Вашиот пробен период истече. Надоградете за да продолжите."
                        : "Вашата сметка е блокирана."
                      : "Го достигнавте дневниот лимит на пребарувања."
                    }
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {isBlocked
                      ? "Одберете платен план за неограничен пристап."
                      : "Надоградете го вашиот план за повеќе дневни пребарувања."
                    }
                  </p>
                </div>
              </div>
              <Link href="/settings">
                <Button className="gap-2">
                  <ArrowRight className="h-4 w-4" />
                  Надогради сега
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto">
        <div className="container mx-auto px-4 py-6 max-w-4xl">
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full space-y-8">
              <div className="text-center space-y-4">
                <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto">
                  <Sparkles className="h-8 w-8 text-primary" />
                </div>
                <div>
                  <h2 className="text-2xl font-bold">Добредојдовте во AI Асистентот</h2>
                  <p className="text-muted-foreground mt-2">
                    Поставете прашање за тендерите или изберете од предлозите подолу
                  </p>
                </div>
              </div>

              <div className="w-full max-w-2xl space-y-3">
                <p className="text-sm font-medium text-muted-foreground">Предложени прашања:</p>
                <div className="grid gap-3">
                  {SUGGESTED_QUESTIONS.map((question, index) => (
                    <Card
                      key={index}
                      className={`p-4 transition-colors ${
                        isLimitReached || isBlocked
                          ? 'opacity-50 cursor-not-allowed'
                          : 'cursor-pointer hover:bg-accent'
                      }`}
                      onClick={() => !isLimitReached && !isBlocked && handleSuggestedQuestion(question)}
                    >
                      <div className="flex items-start gap-3">
                        <MessageSquare className="h-5 w-5 text-muted-foreground mt-0.5 flex-shrink-0" />
                        <p className="text-sm">{question}</p>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>

              {/* Current Plan Info */}
              {usageStatus && !loadingUsage && (
                <Card className="max-w-md p-4 bg-primary/5 border-primary/20">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium">Тековен план: <span className="capitalize">{usageStatus.tier}</span></p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {usageStatus.daily_queries_limit === -1 ? 'Неограничени' : usageStatus.daily_queries_limit} пребарувања дневно
                      </p>
                    </div>
                    {usageStatus.tier === 'free' && (
                      <Link href="/settings">
                        <Button size="sm" variant="outline">
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
                  />
                  {message.role === "assistant" && message.confidence && (
                    <div className="mt-2 ml-11">
                      <p className="text-xs text-muted-foreground">
                        Доверливост: <span className="font-medium">{message.confidence}</span>
                      </p>
                    </div>
                  )}
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-3">
                  <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                    <MessageSquare className="h-4 w-4 text-primary-foreground" />
                  </div>
                  <Card className="p-3 bg-muted">
                    <div className="flex gap-2">
                      <div className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "0ms" }} />
                      <div className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "150ms" }} />
                      <div className="h-2 w-2 rounded-full bg-muted-foreground animate-bounce" style={{ animationDelay: "300ms" }} />
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
        <div className="container mx-auto px-4 py-4 max-w-4xl">
          <ChatInput
            onSend={handleSendMessage}
            disabled={isLoading || isLimitReached || isBlocked}
            placeholder={
              isBlocked
                ? "Надоградете го вашиот план за да продолжите..."
                : isLimitReached
                ? "Дневен лимит достигнат. Надоградете за повеќе..."
                : "Постави прашање за тендерите..."
            }
          />
          <p className="text-xs text-muted-foreground mt-2 text-center">
            AI асистентот користи напредна обработка на природен јазик за одговарање на вашите прашања
          </p>
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
