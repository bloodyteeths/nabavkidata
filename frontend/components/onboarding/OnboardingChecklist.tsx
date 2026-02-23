"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import {
  CheckCircle2,
  Circle,
  Bell,
  Search,
  Users,
  Settings,
  Sparkles,
  X
} from "lucide-react";
import Link from "next/link";

interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  icon: React.ReactNode;
  href: string;
  completed: boolean;
}

interface OnboardingChecklistProps {
  hasAlerts: boolean;
  hasSearches: boolean;
  hasTrackedCompetitors: boolean;
  hasSetPreferences: boolean;
  onDismiss?: () => void;
}

export function OnboardingChecklist({
  hasAlerts,
  hasSearches,
  hasTrackedCompetitors,
  hasSetPreferences,
  onDismiss,
}: OnboardingChecklistProps) {
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    // Check if user has dismissed the checklist
    const isDismissed = localStorage.getItem("onboarding_dismissed") === "true";
    setDismissed(isDismissed);
  }, []);

  const handleDismiss = () => {
    localStorage.setItem("onboarding_dismissed", "true");
    setDismissed(true);
    onDismiss?.();
  };

  const steps: OnboardingStep[] = [
    {
      id: "preferences",
      title: "Поставете ги вашите преференци",
      description: "Изберете индустрија, буџет и региони",
      icon: <Settings className="h-5 w-5" />,
      href: "/settings",
      completed: hasSetPreferences,
    },
    {
      id: "alert",
      title: "Креирајте прв алерт",
      description: "Добивајте известувања за нови тендери",
      icon: <Bell className="h-5 w-5" />,
      href: "/alerts?tab=create",
      completed: hasAlerts,
    },
    {
      id: "search",
      title: "Зачувајте пребарување",
      description: "Брз пристап до често пребарувани тендери",
      icon: <Search className="h-5 w-5" />,
      href: "/tenders",
      completed: hasSearches,
    },
    {
      id: "competitors",
      title: "Следете конкурент",
      description: "Анализирајте ги понудите на конкурентите",
      icon: <Users className="h-5 w-5" />,
      href: "/competitors",
      completed: hasTrackedCompetitors,
    },
  ];

  const completedCount = steps.filter((s) => s.completed).length;
  const progress = (completedCount / steps.length) * 100;

  // Don't show if dismissed or all complete
  if (dismissed || completedCount === steps.length) {
    return null;
  }

  return (
    <Card className="border-primary/30 bg-gradient-to-r from-primary/5 via-purple-500/5 to-primary/5">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            <CardTitle className="text-base md:text-lg">
              Започнете со NabavkiData
            </CardTitle>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-muted-foreground hover:text-foreground"
            onClick={handleDismiss}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="flex items-center gap-3 mt-2">
          <Progress value={progress} className="flex-1 h-2" />
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {completedCount}/{steps.length} завршено
          </span>
        </div>
      </CardHeader>
      <CardContent className="pt-2">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {steps.map((step) => (
            <Link
              key={step.id}
              href={step.href}
              className={`group flex items-start gap-3 p-3 rounded-lg border transition-all ${
                step.completed
                  ? "bg-green-500/5 border-green-500/20"
                  : "bg-background/50 border-border hover:border-primary/30 hover:bg-foreground/5"
              }`}
            >
              <div
                className={`flex-shrink-0 mt-0.5 ${
                  step.completed ? "text-green-500" : "text-muted-foreground group-hover:text-primary"
                }`}
              >
                {step.completed ? (
                  <CheckCircle2 className="h-5 w-5" />
                ) : (
                  step.icon
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p
                  className={`text-sm font-medium ${
                    step.completed ? "text-green-500 line-through" : "text-foreground"
                  }`}
                >
                  {step.title}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {step.description}
                </p>
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
