"use client";

import { useState, useRef, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Bot,
  MessageCircle,
  Send,
  X,
  Sparkles,
  Trash2,
  Loader2,
  Maximize2,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

const SUGGESTED_QUESTIONS = [
  "Кои се најголемите тендери?",
  "Покажи ми ИТ тендери",
  "Најнови тендери денес",
];

export function GlobalChatWidget() {
  const pathname = usePathname();
  const router = useRouter();
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [charCount, setCharCount] = useState(0);
  const [remainingQueries, setRemainingQueries] = useState<number | null>(null);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const MAX_CHARS = 500;
  const STORAGE_KEY = "nabavkidata_global_chat";

  // Hide widget on /chat page
  if (pathname === "/chat") {
    return null;
  }

  // Load messages from sessionStorage on mount
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        const messagesWithDates = parsed.map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        }));
        setMessages(messagesWithDates);
      }
    } catch (error) {
      console.error("Failed to load chat history:", error);
    }
  }, []);

  // Save messages to sessionStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
      } catch (error) {
        console.error("Failed to save chat history:", error);
      }
    }
  }, [messages]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);

  // Load usage status when widget opens
  useEffect(() => {
    if (isOpen && user) {
      loadUsageStatus();
    }
  }, [isOpen, user]);

  const loadUsageStatus = async () => {
    try {
      const status = await api.getSubscriptionStatus();
      const remaining = Math.max(0, status.daily_queries_limit - status.daily_queries_used);
      setRemainingQueries(remaining);
    } catch (error) {
      console.error("Failed to load usage status:", error);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    if (!user) {
      setMessages((prev) => [
        ...prev,
        userMessage,
        {
          role: "assistant",
          content: "За да го користите AI асистентот, потребно е да се најавите.",
          timestamp: new Date(),
        },
      ]);
      setInput("");
      setCharCount(0);
      toast.error("Најавете се за да го користите AI асистентот");
      return;
    }

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setCharCount(0);
    setIsLoading(true);

    try {
      // Build conversation history from previous messages for context
      const conversationHistory = messages.slice(-10).map(msg => ({
        role: msg.role,
        content: msg.content
      }));

      const response = await api.queryRAG(userMessage.content, undefined, conversationHistory);

      const assistantMessage: Message = {
        role: "assistant",
        content: response.answer,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      await loadUsageStatus();
    } catch (error: any) {
      console.error("Failed to get AI response:", error);

      let errorContent = "Се извинуваме, настана грешка. Обидете се повторно.";

      if (error?.message?.includes("401") || error?.message?.includes("authenticated")) {
        errorContent = "Сесијата истече. Најавете се повторно.";
      } else if (error?.message?.includes("429")) {
        errorContent = "Дневен лимит достигнат. Надградете го планот.";
      }

      const errorMessage: Message = {
        role: "assistant",
        content: errorContent,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    sessionStorage.removeItem(STORAGE_KEY);
    toast.success("Конверзацијата е избришана");
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    if (value.length <= MAX_CHARS) {
      setInput(value);
      setCharCount(value.length);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestedQuestion = (question: string) => {
    setInput(question);
  };

  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat("mk-MK", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };

  const goToFullChat = () => {
    setIsOpen(false);
    router.push("/chat");
  };

  return (
    <>
      {/* Floating Button */}
      <div className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-50">
        {!isOpen && (
          <Button
            size="lg"
            className="h-12 w-12 sm:h-14 sm:w-14 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-110"
            onClick={() => setIsOpen(true)}
          >
            <div className="relative">
              <MessageCircle className="h-5 w-5 sm:h-6 sm:w-6" />
              <Sparkles className="h-2.5 w-2.5 sm:h-3 sm:w-3 absolute -top-1 -right-1 text-yellow-400" />
            </div>
          </Button>
        )}
      </div>

      {/* Chat Window */}
      {isOpen && (
        <div className="fixed inset-0 sm:inset-auto sm:bottom-6 sm:right-6 z-50 sm:w-full sm:max-w-md animate-in slide-in-from-bottom-5 duration-300">
          <Card className="h-full sm:h-auto shadow-2xl border-2 rounded-none sm:rounded-lg flex flex-col">
            {/* Header */}
            <CardHeader className="pb-3 border-b bg-gradient-to-r from-primary/10 to-primary/5 flex-shrink-0">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                    <Bot className="h-5 w-5 text-primary-foreground" />
                  </div>
                  <span className="hidden xs:inline">AI Асистент</span>
                  <span className="xs:hidden">AI</span>
                </CardTitle>
                <div className="flex items-center gap-1">
                  {remainingQueries !== null && (
                    <Badge variant="outline" className="text-xs mr-1 hidden sm:flex">
                      <Zap className="h-3 w-3 mr-1" />
                      {remainingQueries}
                    </Badge>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={goToFullChat}
                    title="Отвори целосен чат"
                  >
                    <Maximize2 className="h-4 w-4" />
                  </Button>
                  {messages.length > 0 && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={handleClearChat}
                      title="Избриши"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={() => setIsOpen(false)}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>

            {/* Messages */}
            <CardContent className="p-0 flex-1 overflow-hidden flex flex-col min-h-0">
              <div className="flex-1 overflow-y-auto p-4 h-[calc(100vh-180px)] sm:h-[350px]" ref={scrollAreaRef}>
                <div className="space-y-4">
                  {messages.length === 0 ? (
                    <div className="text-center py-6">
                      <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-3">
                        <Sparkles className="h-6 w-6 text-primary" />
                      </div>
                      <p className="text-sm text-muted-foreground mb-4">
                        Како можам да помогнам?
                      </p>
                      <div className="space-y-2">
                        {SUGGESTED_QUESTIONS.map((q, i) => (
                          <button
                            key={i}
                            onClick={() => handleSuggestedQuestion(q)}
                            className="block w-full text-left text-xs p-2 rounded-lg bg-muted/50 hover:bg-muted transition-colors"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    messages.map((message, idx) => (
                      <div
                        key={idx}
                        className={cn(
                          "flex gap-2",
                          message.role === "user" ? "justify-end" : "justify-start"
                        )}
                      >
                        {message.role === "assistant" && (
                          <div className="h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                            <Bot className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary" />
                          </div>
                        )}

                        <div className={cn("max-w-[85%] sm:max-w-[80%] space-y-1", message.role === "user" && "flex flex-col items-end")}>
                          <div
                            className={cn(
                              "rounded-lg px-3 py-2 text-sm",
                              message.role === "user"
                                ? "bg-primary text-primary-foreground"
                                : "bg-muted"
                            )}
                          >
                            <p className="whitespace-pre-wrap break-words text-xs sm:text-sm">{message.content}</p>
                          </div>
                          <p className="text-[10px] sm:text-xs text-muted-foreground px-1">
                            {formatTime(message.timestamp)}
                          </p>
                        </div>

                        {message.role === "user" && (
                          <div className="h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
                            <span className="text-[10px] sm:text-xs font-semibold">Вие</span>
                          </div>
                        )}
                      </div>
                    ))
                  )}

                  {/* Typing Indicator */}
                  {isLoading && (
                    <div className="flex gap-2 items-start">
                      <div className="h-7 w-7 sm:h-8 sm:w-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                        <Bot className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-primary" />
                      </div>
                      <div className="bg-muted rounded-lg px-3 py-2">
                        <div className="flex gap-1">
                          <div className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: "0ms" }} />
                          <div className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: "150ms" }} />
                          <div className="h-2 w-2 rounded-full bg-muted-foreground/50 animate-bounce" style={{ animationDelay: "300ms" }} />
                        </div>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              </div>

              {/* Input Area */}
              <div className="border-t p-3 space-y-2 flex-shrink-0">
                <div className="flex gap-2">
                  <Input
                    value={input}
                    onChange={handleInputChange}
                    onKeyPress={handleKeyPress}
                    placeholder="Напишете прашање..."
                    disabled={isLoading}
                    className="flex-1 text-sm"
                  />
                  <Button
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading}
                    size="icon"
                  >
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>

                {/* Character Counter - only show when typing */}
                {charCount > 0 && (
                  <div className="flex items-center justify-end text-xs text-muted-foreground px-1">
                    <Badge variant={charCount > MAX_CHARS * 0.9 ? "destructive" : "outline"} className="text-xs">
                      {charCount}/{MAX_CHARS}
                    </Badge>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
