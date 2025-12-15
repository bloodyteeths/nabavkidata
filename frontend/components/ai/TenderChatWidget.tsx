"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import {
  Bot,
  MessageCircle,
  Send,
  X,
  Sparkles,
  Trash2,
  FileText,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  sources?: Array<{
    doc_id: string;
    file_name: string;
    excerpt: string;
  }>;
}

interface TenderChatWidgetProps {
  tenderId: string;
  tenderTitle?: string;
}

export function TenderChatWidget({ tenderId, tenderTitle }: TenderChatWidgetProps) {
  const { user } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [charCount, setCharCount] = useState(0);
  const scrollAreaRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const MAX_CHARS = 500;
  const STORAGE_KEY = `tender_chat_${tenderId}`;

  // Load messages from sessionStorage on mount
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        // Convert timestamp strings back to Date objects
        const messagesWithDates = parsed.map((msg: any) => ({
          ...msg,
          timestamp: new Date(msg.timestamp),
        }));
        setMessages(messagesWithDates);
      } else {
        // Add welcome message if no history
        setMessages([
          {
            role: "assistant",
            content: "Здраво! Јас сум вашиот AI асистент за тендери. Како можам да помогнам со овој тендер?",
            timestamp: new Date(),
          },
        ]);
      }
    } catch (error) {
      console.error("Failed to load chat history:", error);
    }
  }, [tenderId]);

  // Save messages to sessionStorage whenever they change
  useEffect(() => {
    if (messages.length > 0) {
      try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
      } catch (error) {
        console.error("Failed to save chat history:", error);
      }
    }
  }, [messages, STORAGE_KEY]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isLoading]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      role: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    // Check if user is authenticated
    if (!user) {
      setMessages((prev) => [
        ...prev,
        userMessage,
        {
          role: "assistant",
          content: "За да го користите AI асистентот, потребно е да се најавите. Кликнете на 'Најава' за да продолжите.",
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
      // Build conversation history for context (last 10 messages)
      const conversationHistory = messages.slice(-10).map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      const response = await api.queryRAG(userMessage.content, tenderId, conversationHistory);

      const assistantMessage: Message = {
        role: "assistant",
        content: response.answer,
        timestamp: new Date(),
        sources: response.sources?.slice(0, 3).map((source) => ({
          doc_id: source.doc_id || "",
          file_name: source.doc_id ? `Документ ${source.doc_id.slice(-8)}` : "Документ",
          excerpt: source.chunk_text.slice(0, 150),
        })),
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error: any) {
      console.error("Failed to get AI response:", error);

      // Check for specific error types
      let errorContent = "Се извинуваме, настана грешка при обработка на вашето прашање. Ве молиме обидете се повторно.";

      if (error?.message?.includes("401") || error?.message?.includes("credentials") || error?.message?.includes("authenticated")) {
        errorContent = "Сесијата истече. Ве молиме најавете се повторно.";
        toast.error("Сесијата истече. Најавете се повторно.");
      } else if (error?.message?.includes("429")) {
        errorContent = "Го достигнавте дневниот лимит на прашања. Надградете го планот за повеќе прашања.";
        toast.error("Дневен лимит достигнат");
      } else {
        toast.error("Грешка при комуникација со AI асистентот");
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
    setMessages([
      {
        role: "assistant",
        content: "Конверзацијата е избришана. Како можам да помогнам?",
        timestamp: new Date(),
      },
    ]);
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

  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat("mk-MK", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  };

  return (
    <>
      {/* Floating Button */}
      <div className="fixed bottom-6 right-6 z-50">
        {!isOpen && (
          <Button
            size="lg"
            className="h-14 w-14 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-110"
            onClick={() => setIsOpen(true)}
          >
            <div className="relative">
              <MessageCircle className="h-6 w-6" />
              <Sparkles className="h-3 w-3 absolute -top-1 -right-1 text-yellow-400" />
            </div>
          </Button>
        )}
      </div>

      {/* Chat Window */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 w-full max-w-md animate-in slide-in-from-bottom-5 duration-300">
          <Card className="shadow-2xl border-2">
            {/* Header */}
            <CardHeader className="pb-3 border-b bg-gradient-to-r from-primary/10 to-primary/5">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center">
                    <Bot className="h-5 w-5 text-primary-foreground" />
                  </div>
                  AI Асистент за Тендер
                </CardTitle>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    onClick={handleClearChat}
                    title="Избриши конверзација"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
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
              {tenderTitle && (
                <p className="text-xs text-muted-foreground line-clamp-1 mt-1">
                  {tenderTitle}
                </p>
              )}
            </CardHeader>

            {/* Messages */}
            <CardContent className="p-0">
              <ScrollArea className="h-[400px] p-4" ref={scrollAreaRef}>
                <div className="space-y-4">
                  {messages.map((message, idx) => (
                    <div
                      key={idx}
                      className={cn(
                        "flex gap-2",
                        message.role === "user" ? "justify-end" : "justify-start"
                      )}
                    >
                      {message.role === "assistant" && (
                        <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                          <Bot className="h-4 w-4 text-primary" />
                        </div>
                      )}

                      <div className={cn("max-w-[80%] space-y-1", message.role === "user" && "flex flex-col items-end")}>
                        <div
                          className={cn(
                            "rounded-lg px-3 py-2 text-sm",
                            message.role === "user"
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted"
                          )}
                        >
                          <p className="whitespace-pre-wrap break-words">{message.content}</p>
                        </div>

                        {/* Sources */}
                        {message.sources && message.sources.length > 0 && (
                          <div className="space-y-1">
                            {message.sources.map((source, sourceIdx) => (
                              <div
                                key={sourceIdx}
                                className="text-xs bg-muted/50 rounded px-2 py-1.5 flex items-start gap-1.5"
                              >
                                <FileText className="h-3 w-3 text-muted-foreground mt-0.5 flex-shrink-0" />
                                <div className="flex-1 min-w-0">
                                  <p className="font-medium text-muted-foreground truncate">
                                    {source.file_name}
                                  </p>
                                  <p className="text-muted-foreground line-clamp-2">
                                    {source.excerpt}...
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        <p className="text-xs text-muted-foreground px-1">
                          {formatTime(message.timestamp)}
                        </p>
                      </div>

                      {message.role === "user" && (
                        <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center flex-shrink-0">
                          <span className="text-xs font-semibold">Вие</span>
                        </div>
                      )}
                    </div>
                  ))}

                  {/* Typing Indicator */}
                  {isLoading && (
                    <div className="flex gap-2 items-start">
                      <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                        <Bot className="h-4 w-4 text-primary" />
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
              </ScrollArea>

              {/* Input Area */}
              <div className="border-t p-3 space-y-2">
                <div className="flex gap-2">
                  <Input
                    value={input}
                    onChange={handleInputChange}
                    onKeyPress={handleKeyPress}
                    placeholder="Напишете прашање..."
                    disabled={isLoading}
                    className="flex-1"
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

                {/* Character Counter */}
                <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
                  <span>Прашајте за документи, барања, услови...</span>
                  <Badge variant={charCount > MAX_CHARS * 0.9 ? "destructive" : "outline"} className="text-xs">
                    {charCount}/{MAX_CHARS}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </>
  );
}
