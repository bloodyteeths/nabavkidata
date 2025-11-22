"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { ChatInput } from "@/components/chat/ChatInput";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { MessageSquare, Sparkles, Trash2 } from "lucide-react";
import { api } from "@/lib/api";

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

const SUGGESTED_QUESTIONS = [
  "Кои се најголемите тендери овој месец?",
  "Покажи ми ИТ тендери",
  "Која институција објавува најмногу тендери?",
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (content: string) => {
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

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Header */}
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
                      className="p-4 cursor-pointer hover:bg-accent transition-colors"
                      onClick={() => handleSuggestedQuestion(question)}
                    >
                      <div className="flex items-start gap-3">
                        <MessageSquare className="h-5 w-5 text-muted-foreground mt-0.5 flex-shrink-0" />
                        <p className="text-sm">{question}</p>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
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
            disabled={isLoading}
            placeholder="Постави прашање за тендерите..."
          />
          <p className="text-xs text-muted-foreground mt-2 text-center">
            AI асистентот користи напредна обработка на природен јазик за одговарање на вашите прашања
          </p>
        </div>
      </div>
    </div>
  );
}
