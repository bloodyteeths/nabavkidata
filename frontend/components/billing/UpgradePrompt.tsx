'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { ArrowRight, FileText, HeartHandshake, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useAuth } from '@/lib/auth';
import { canAccessPortal } from '@/lib/portal';

/**
 * Service prompt (formerly a plan-upgrade prompt).
 *
 * NabavkiData is now a done-for-you bid-writing + tender-monitoring service,
 * so anything that used to be gated behind a paid plan now points the user to
 * the service page instead. The props are kept identical to the old
 * plan-based component so existing call sites keep compiling; the tier and
 * credit props are accepted but no longer drive the copy.
 */
interface UpgradePromptProps {
  feature: string;
  /** @deprecated kept for call-site compatibility; ignored. */
  currentTier: string;
  /** @deprecated kept for call-site compatibility; ignored. */
  tierRequired?: string;
  message?: string;
  /** @deprecated kept for call-site compatibility; ignored. */
  creditsUsed?: number;
  /** @deprecated kept for call-site compatibility; ignored. */
  creditsTotal?: number;
  onClose?: () => void;
  variant?: 'modal' | 'inline' | 'banner';
}

const FEATURE_LABELS: Record<string, string> = {
  ai_messages: 'AI прашања',
  ai_summary: 'AI резиме на тендер',
  doc_extractions: 'Екстракција на документи',
  exports: 'Извоз на податоци',
  competitor_alerts: 'Следење конкуренти',
  risk_analysis: 'Анализа на ризик',
  price_intelligence: 'Ценовна анализа',
};

export const SERVICE_HEADLINE = 'Ова го правиме ние за вас';
export const SERVICE_BODY =
  'Ние ја правиме анализата и ја пишуваме понудата за вас. Вие ја прегледувате, ја потпишувате со ваш сертификат и ја поднесувате на е-набавки.';
const SERVICE_PRICE_NOTE =
  'AI алатките, ценовните анализи и известувањата се вклучени за клиентите за кои подготвуваме понуди. Подготовката на понуда е платена услуга, со договорен надомест пред да почне работата.';

/**
 * Messages coming from the backend or older call sites may still talk about
 * plans/upgrades. Those must never reach the user; anything else (e.g.
 * "Регистрирајте се за да видите цени...") is shown as useful context.
 */
const PLAN_LANGUAGE = /надград|надгради|план|претплат|кредит|upgrade|plan|subscri|stripe/i;

export function serviceContextMessage(message?: string): string | null {
  const trimmed = message?.trim();
  if (!trimmed) return null;
  return PLAN_LANGUAGE.test(trimmed) ? null : trimmed;
}

export function serviceHref(feature?: string): string {
  const params = new URLSearchParams({ src: 'paywall' });
  if (feature && feature !== 'premium') params.set('feature', feature);
  return `/usluga?${params.toString()}`;
}

export function UpgradePrompt({
  feature,
  message,
  onClose,
  variant = 'inline',
}: UpgradePromptProps) {
  const featureLabel = FEATURE_LABELS[feature];
  const context = serviceContextMessage(message);
  // Prospects already went through the assessment and have a portal: their
  // next step is starting a bid there, not a second assessment request.
  const { user } = useAuth();
  const inPortal = canAccessPortal(user);
  const href = inPortal ? '/portal/tenders' : serviceHref(feature);
  const ctaLabel = inPortal ? 'Започнете понуда' : 'Нарачајте понуда';

  // Close the modal with Escape.
  useEffect(() => {
    if (variant !== 'modal' || !onClose) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [variant, onClose]);

  if (variant === 'banner') {
    return (
      <div className="glass border border-primary/20 rounded-lg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-start sm:items-center gap-3">
          <div className="p-2 bg-primary/10 rounded-full shrink-0">
            <HeartHandshake className="h-5 w-5 text-primary" />
          </div>
          <div>
            <p className="font-medium text-foreground">{SERVICE_HEADLINE}</p>
            <p className="text-sm text-muted-foreground">
              {context || 'Ние ја правиме анализата и ја пишуваме понудата за вас.'}
            </p>
          </div>
        </div>
        <Button asChild className="shrink-0">
          <Link href={href}>
            {ctaLabel}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
    );
  }

  if (variant === 'modal') {
    return (
      <div
        className="fixed inset-0 bg-background/70 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, y: 12, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.2 }}
          className="max-w-md w-full"
          role="dialog"
          aria-modal="true"
          aria-labelledby="service-prompt-title"
          onClick={(e) => e.stopPropagation()}
        >
          <Card className="relative glass">
            {onClose && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Затвори"
                className="absolute top-4 right-4 text-muted-foreground hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            )}
            <CardHeader className="text-center pb-2">
              <div className="mx-auto w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                <FileText className="h-8 w-8 text-primary" />
              </div>
              <CardTitle id="service-prompt-title" className="text-xl">
                <span className="text-gradient">{SERVICE_HEADLINE}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="text-center space-y-4">
              {featureLabel && (
                <Badge variant="secondary">{featureLabel}</Badge>
              )}
              {context && <p className="text-sm text-foreground">{context}</p>}
              <p className="text-muted-foreground">{SERVICE_BODY}</p>

              <ul className="bg-muted/60 rounded-lg p-4 text-left text-sm space-y-1.5 text-foreground">
                <li>Следење и избор на тендери за вас, вклучено за клиентите</li>
                <li>Анализа на условите и цените на конкуренцијата</li>
                <li>Целосна понуда, подготвена за поднесување</li>
              </ul>
              <p className="text-xs text-muted-foreground">{SERVICE_PRICE_NOTE}</p>

              <div className="flex flex-col-reverse sm:flex-row gap-3">
                {onClose && (
                  <Button variant="outline" onClick={onClose} className="flex-1">
                    Затвори
                  </Button>
                )}
                <Button asChild className="flex-1">
                  <Link href={href} onClick={onClose}>
                    {ctaLabel}
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    );
  }

  // Default inline variant
  return (
    <div className="glass border border-primary/20 rounded-lg p-6 text-center">
      <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
        <HeartHandshake className="h-6 w-6 text-primary" />
      </div>
      <h3 className="font-semibold text-foreground mb-2">{SERVICE_HEADLINE}</h3>
      {context && <p className="text-sm text-foreground mb-2">{context}</p>}
      <p className="text-sm text-muted-foreground mb-4 max-w-lg mx-auto">{SERVICE_BODY}</p>
      <Button asChild size="sm">
        <Link href={href}>
          {ctaLabel}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Link>
      </Button>
    </div>
  );
}

/**
 * Usage display component (kept for compatibility; no plan/upgrade language).
 */
interface CreditDisplayProps {
  creditType: string;
  used: number;
  total: number;
  daysRemaining?: number;
}

export function CreditDisplay({ creditType, used, total, daysRemaining }: CreditDisplayProps) {
  const remaining = total - used;
  const percentage = total > 0 ? Math.round((used / total) * 100) : 100;
  const isLow = percentage >= 80;
  const isDepleted = remaining <= 0;

  const label = FEATURE_LABELS[creditType] || creditType;

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium text-foreground">{label}</span>
        <span className={`text-sm font-semibold ${isDepleted ? 'text-red-600' : isLow ? 'text-amber-600' : 'text-green-600'}`}>
          {remaining}/{total}
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={`h-full transition-all ${isDepleted ? 'bg-red-500' : isLow ? 'bg-amber-500' : 'bg-green-500'}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      {daysRemaining !== undefined && daysRemaining > 0 && (
        <p className="text-xs text-muted-foreground">
          Се обновува за {daysRemaining} {daysRemaining === 1 ? 'ден' : 'дена'}
        </p>
      )}
      {isDepleted && (
        <p className="text-xs text-muted-foreground">
          Дневниот лимит е искористен.{' '}
          <Link href={serviceHref(creditType)} className="underline font-medium text-primary">
            Ние ја правиме анализата за вас
          </Link>
        </p>
      )}
    </div>
  );
}
