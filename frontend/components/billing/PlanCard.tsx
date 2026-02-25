'use client';

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Check, ArrowUp, ArrowDown } from 'lucide-react';
import { SubscriptionPlan } from '@/lib/api';

const TIER_ORDER: Record<string, number> = {
  FREE: 0,
  free: 0,
  starter: 1,
  professional: 2,
  enterprise: 3,
};

interface PlanCardProps {
  plan: SubscriptionPlan;
  currentPlanId?: string;
  onSubscribe: (planId: string) => void;
  onChangePlan?: (planId: string) => void;
  loading?: boolean;
}

export function PlanCard({ plan, currentPlanId, onSubscribe, onChangePlan, loading }: PlanCardProps) {
  const isCurrentPlan = currentPlanId === plan.id;
  const isFree = plan.id === 'FREE' || plan.id === 'free';
  const hasSubscription = currentPlanId && currentPlanId !== 'FREE' && currentPlanId !== 'free';

  const currentTierLevel = TIER_ORDER[currentPlanId || 'free'] ?? 0;
  const planTierLevel = TIER_ORDER[plan.id] ?? 0;
  const isUpgrade = planTierLevel > currentTierLevel;
  const isDowngrade = planTierLevel < currentTierLevel;

  const getButtonContent = () => {
    if (loading) return 'Се вчитува...';
    if (isFree) return 'Бесплатно';
    if (!hasSubscription) return 'Претплати се';
    if (isUpgrade) return (
      <span className="flex items-center gap-1.5">
        <ArrowUp className="h-4 w-4" />
        Надгради
      </span>
    );
    if (isDowngrade) return (
      <span className="flex items-center gap-1.5">
        <ArrowDown className="h-4 w-4" />
        Намали план
      </span>
    );
    return 'Промени план';
  };

  const handleClick = () => {
    if (hasSubscription && onChangePlan && !isFree) {
      onChangePlan(plan.id);
    } else {
      onSubscribe(plan.id);
    }
  };

  return (
    <Card className={`relative ${plan.is_popular ? 'border-primary shadow-lg' : ''}`}>
      {plan.is_popular && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <Badge variant="default">Најпопуларно</Badge>
        </div>
      )}

      <CardHeader className="text-center">
        <CardTitle className="text-2xl">{plan.name}</CardTitle>
        <CardDescription>
          <div className="mt-4 flex flex-col items-center gap-1">
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-bold text-foreground">
                {plan.price_mkd.toLocaleString()}
              </span>
              <span className="text-muted-foreground">ден</span>
            </div>
            <div className="text-sm text-muted-foreground">
              ({plan.price_eur} EUR) / месечно
            </div>
          </div>
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <ul className="space-y-3">
          {plan.features.map((feature, index) => (
            <li key={index} className="flex items-start gap-3">
              <Check className="h-5 w-5 shrink-0 text-primary mt-0.5" />
              <span className="text-sm">{feature}</span>
            </li>
          ))}
        </ul>
      </CardContent>

      <CardFooter className="flex flex-col gap-2">
        {isCurrentPlan ? (
          <Badge variant="success" className="w-full justify-center py-2">
            Тековен план
          </Badge>
        ) : (
          <Button
            onClick={handleClick}
            disabled={loading || isFree}
            className="w-full"
            variant={isDowngrade ? 'outline' : plan.is_popular ? 'default' : 'outline'}
          >
            {getButtonContent()}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
