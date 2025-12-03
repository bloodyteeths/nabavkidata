"use client";

import { Button } from "@/components/ui/button";
import {
  ClipboardList,
  DollarSign,
  Users,
  Calendar,
  AlertTriangle,
  FileText,
} from "lucide-react";

interface QuickActionsProps {
  tenderId: string;
  onAskQuestion: (question: string) => void;
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

export function QuickActions({
  tenderId,
  onAskQuestion,
  disabled = false,
}: QuickActionsProps) {
  const handleQuickAction = (question: string) => {
    if (!disabled) {
      onAskQuestion(question);
    }
  };

  return (
    <div className="w-full">
      <div className="mb-3">
        <h3 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
          <FileText className="h-4 w-4" />
          ПРАШАЈ AI ЗА ТЕНДЕРОТ
        </h3>
      </div>
      <div className="flex flex-wrap gap-2">
        {QUICK_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <Button
              key={action.id}
              variant="outline"
              size="sm"
              onClick={() => handleQuickAction(action.question)}
              disabled={disabled}
              className="transition-all hover:bg-primary/10 hover:border-primary/50"
            >
              <Icon className="h-4 w-4 mr-2" />
              {action.label}
            </Button>
          );
        })}
      </div>
    </div>
  );
}
