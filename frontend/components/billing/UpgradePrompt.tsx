'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Zap, ArrowRight, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface UpgradePromptProps {
  feature: string;
  currentTier: string;
  tierRequired?: string;
  message?: string;
  creditsUsed?: number;
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
};

const TIER_LABELS: Record<string, string> = {
  free: 'Бесплатен',
  trial: 'Пробен период',
  starter: 'Стартуј',
  professional: 'Про',
  enterprise: 'Претпријатие',
};

const TIER_PRICES: Record<string, string> = {
  starter: '1,990 МКД/месец',
  professional: '5,990 МКД/месец',
  enterprise: '12,990 МКД/месец',
};

export function UpgradePrompt({
  feature,
  currentTier,
  tierRequired,
  message,
  creditsUsed,
  creditsTotal,
  onClose,
  variant = 'inline',
}: UpgradePromptProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  const featureLabel = FEATURE_LABELS[feature] || feature;
  const requiredTierLabel = tierRequired ? TIER_LABELS[tierRequired] : 'Стартуј';
  const requiredTierPrice = tierRequired ? TIER_PRICES[tierRequired] : TIER_PRICES.start;

  const handleUpgrade = () => {
    setLoading(true);
    router.push('/settings#plans');
  };

  if (variant === 'banner') {
    return (
      <div className="bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-lg p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-amber-100 rounded-full">
            <AlertTriangle className="h-5 w-5 text-amber-600" />
          </div>
          <div>
            <p className="font-medium text-amber-900">
              {creditsUsed !== undefined && creditsTotal !== undefined
                ? `Искористивте ${creditsUsed}/${creditsTotal} кредити за ${featureLabel}`
                : `${featureLabel} не е достапна на вашиот план`}
            </p>
            <p className="text-sm text-amber-700">
              {message || `Надградете на ${requiredTierLabel} за неограничен пристап`}
            </p>
          </div>
        </div>
        <Button
          onClick={handleUpgrade}
          disabled={loading}
          className="bg-amber-600 hover:bg-amber-700 text-white"
        >
          {loading ? 'Се вчитува...' : 'Надогради'}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
    );
  }

  if (variant === 'modal') {
    return (
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
        <Card className="max-w-md w-full relative">
          {onClose && (
            <button
              onClick={onClose}
              className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          )}
          <CardHeader className="text-center pb-2">
            <div className="mx-auto w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center mb-4">
              <Zap className="h-8 w-8 text-white" />
            </div>
            <CardTitle className="text-xl">Надградете го вашиот план</CardTitle>
          </CardHeader>
          <CardContent className="text-center space-y-4">
            <div className="space-y-2">
              <Badge variant="secondary" className="bg-amber-100 text-amber-700">
                {featureLabel}
              </Badge>
              <p className="text-gray-600">
                {creditsUsed !== undefined && creditsTotal !== undefined
                  ? `Ги искористивте сите ${creditsTotal} кредити за ${featureLabel}.`
                  : `Оваа функција не е достапна на ${TIER_LABELS[currentTier] || currentTier} план.`}
              </p>
            </div>

            <div className="bg-gray-50 rounded-lg p-4">
              <p className="font-semibold text-gray-900">
                {requiredTierLabel} план
              </p>
              <p className="text-2xl font-bold text-blue-600 mt-1">
                {requiredTierPrice}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                Добијте пристап до сите Pro функции
              </p>
            </div>

            <div className="flex gap-3">
              {onClose && (
                <Button variant="outline" onClick={onClose} className="flex-1">
                  Можеби подоцна
                </Button>
              )}
              <Button
                onClick={handleUpgrade}
                disabled={loading}
                className="flex-1 bg-blue-600 hover:bg-blue-700"
              >
                {loading ? 'Се вчитува...' : 'Надогради сега'}
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Default inline variant
  return (
    <div className="bg-gradient-to-r from-gray-50 to-blue-50 border border-gray-200 rounded-lg p-6 text-center">
      <div className="mx-auto w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mb-4">
        <Zap className="h-6 w-6 text-blue-600" />
      </div>
      <h3 className="font-semibold text-gray-900 mb-2">
        {creditsUsed !== undefined
          ? 'Кредитите се искористени'
          : 'Надградете за пристап'}
      </h3>
      <p className="text-sm text-gray-600 mb-4">
        {message ||
          `${featureLabel} е достапна од ${requiredTierLabel} план (${requiredTierPrice})`}
      </p>
      <Button
        onClick={handleUpgrade}
        disabled={loading}
        size="sm"
        className="bg-blue-600 hover:bg-blue-700"
      >
        {loading ? 'Се вчитува...' : 'Преглед на планови'}
        <ArrowRight className="ml-2 h-4 w-4" />
      </Button>
    </div>
  );
}

/**
 * Credit usage display component
 */
interface CreditDisplayProps {
  creditType: string;
  used: number;
  total: number;
  daysRemaining?: number;
}

export function CreditDisplay({ creditType, used, total, daysRemaining }: CreditDisplayProps) {
  const remaining = total - used;
  const percentage = Math.round((used / total) * 100);
  const isLow = percentage >= 80;
  const isDepleted = remaining <= 0;

  const label = FEATURE_LABELS[creditType] || creditType;

  return (
    <div className="space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className={`text-sm font-semibold ${isDepleted ? 'text-red-600' : isLow ? 'text-amber-600' : 'text-green-600'}`}>
          {remaining}/{total}
        </span>
      </div>
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all ${isDepleted ? 'bg-red-500' : isLow ? 'bg-amber-500' : 'bg-green-500'}`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
      {daysRemaining !== undefined && daysRemaining > 0 && (
        <p className="text-xs text-gray-500">
          Истекува за {daysRemaining} {daysRemaining === 1 ? 'ден' : 'дена'}
        </p>
      )}
      {isDepleted && (
        <p className="text-xs text-red-600 font-medium">
          Кредитите се искористени - надградете за да продолжите
        </p>
      )}
    </div>
  );
}
