"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  ClipboardList,
  DollarSign,
  Users,
  Calendar,
  AlertTriangle,
  FileText,
  Sparkles,
  Loader2,
  CheckCircle2,
} from "lucide-react";

interface QuickActionsProps {
  tenderId: string;
  onAskQuestion?: (question: string) => void;
  disabled?: boolean;
}

const QUICK_ACTIONS = [
  {
    id: "requirements",
    icon: ClipboardList,
    label: "Барања",
    question: "Кои се главните барања и критериуми за овој тендер?",
  },
  {
    id: "price",
    icon: DollarSign,
    label: "Цена",
    question:
      "Колкава е проценетата вредност и какви цени се вообичаени за слични тендери?",
  },
  {
    id: "competitors",
    icon: Users,
    label: "Конкуренти",
    question: "Кои компании обично учествуваат и добиваат слични тендери?",
  },
  {
    id: "deadlines",
    icon: Calendar,
    label: "Рокови",
    question: "Кои се клучните датуми и рокови за овој тендер?",
  },
  {
    id: "risks",
    icon: AlertTriangle,
    label: "Ризици",
    question: "Кои се потенцијалните ризици и предизвици за учество?",
  },
  {
    id: "summary",
    icon: FileText,
    label: "Резиме",
    question: "Дај ми кратко резиме на овој тендер и документите.",
  },
];

interface CachedResponse {
  question: string;
  answer: string;
  label: string;
}

export function QuickActions({
  tenderId,
  onAskQuestion,
  disabled = false,
}: QuickActionsProps) {
  const [loading, setLoading] = useState<string | null>(null);
  // Store all responses by action ID - persists when switching between tabs
  const [responses, setResponses] = useState<Record<string, CachedResponse>>({});
  // Track which action is currently selected for display
  const [activeAction, setActiveAction] = useState<string | null>(null);

  const handleQuickAction = async (actionId: string, question: string, label: string) => {
    // If we already have a cached response for this action, just show it
    if (responses[actionId]) {
      setActiveAction(actionId);
      return;
    }

    if (loading) return;

    setLoading(actionId);
    setActiveAction(actionId);

    // Show loading toast
    const loadingToast = toast.loading(`AI анализира: ${label}...`, {
      description: "Ова може да потрае 20-30 секунди",
    });

    try {
      const result = await api.queryRAG(question, tenderId);

      // Dismiss loading toast
      toast.dismiss(loadingToast);

      // Show success
      toast.success(`${label} - AI одговор готов!`);

      // Store the response in cache
      setResponses(prev => ({
        ...prev,
        [actionId]: {
          question,
          answer: result.answer,
          label,
        }
      }));

      // Also call parent handler if provided
      if (onAskQuestion) {
        onAskQuestion(question);
      }
    } catch (error: any) {
      toast.dismiss(loadingToast);

      if (error?.message?.includes("401") || error?.message?.includes("credentials")) {
        toast.error("Сесијата истече. Најавете се повторно.");
      } else if (error?.message?.includes("429")) {
        toast.error("Дневен лимит достигнат. Надградете го планот.");
      } else {
        toast.error("AI одговорот не успеа. Обидете се повторно.");
      }
      setActiveAction(null);
    } finally {
      setLoading(null);
    }
  };

  const currentResponse = activeAction ? responses[activeAction] : null;
  const isCurrentlyLoading = loading === activeAction;

  return (
    <div className="w-full space-y-4">
      <div className="mb-3">
        <h3 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
          <Sparkles className="h-4 w-4" />
          ПРАШАЈ AI ЗА ТЕНДЕРОТ
        </h3>
      </div>
      <div className="flex flex-wrap gap-2">
        {QUICK_ACTIONS.map((action) => {
          const Icon = action.icon;
          const isLoading = loading === action.id;
          const hasResponse = !!responses[action.id];
          const isActive = activeAction === action.id;

          return (
            <Button
              key={action.id}
              variant={isActive ? "default" : "outline"}
              size="sm"
              onClick={() => handleQuickAction(action.id, action.question, action.label)}
              disabled={disabled || (loading !== null && loading !== action.id)}
              className={`transition-all ${
                isActive
                  ? "bg-primary text-primary-foreground"
                  : hasResponse
                    ? "border-primary/50 text-primary hover:bg-primary/10"
                    : "hover:bg-primary/10 hover:border-primary/50"
              }`}
            >
              {isLoading ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : hasResponse ? (
                <CheckCircle2 className="h-4 w-4 mr-2" />
              ) : (
                <Icon className="h-4 w-4 mr-2" />
              )}
              {action.label}
            </Button>
          );
        })}
      </div>

      {/* AI Response Display - Shows loading state or cached response */}
      {activeAction && (
        <Card className="mt-4 border-primary/30 bg-gradient-to-br from-primary/5 to-primary/10">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <CardTitle className="text-base flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                {isCurrentlyLoading ? (
                  <>AI анализира...</>
                ) : (
                  <>AI Одговор: {currentResponse?.label}</>
                )}
              </CardTitle>
            </div>
            {currentResponse && (
              <p className="text-xs text-muted-foreground mt-1">
                Прашање: {currentResponse.question}
              </p>
            )}
          </CardHeader>
          <CardContent>
            {isCurrentlyLoading ? (
              <div className="flex items-center gap-3 py-8">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <span className="text-sm text-muted-foreground">
                  AI ги анализира документите... Ова може да потрае 20-30 секунди.
                </span>
              </div>
            ) : currentResponse ? (
              <div
                className="text-sm whitespace-pre-wrap leading-relaxed overflow-y-auto max-h-[500px] pr-2"
                style={{ scrollbarWidth: 'thin' }}
              >
                {currentResponse.answer}
              </div>
            ) : null}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
