'use client';

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Check } from 'lucide-react';
import { SubscriptionPlan } from '@/lib/api';

interface PlanCardProps {
  plan: SubscriptionPlan;
  currentPlanId?: string;
  onSubscribe: (planId: string) => void;
  loading?: boolean;
}

export function PlanCard({ plan, currentPlanId, onSubscribe, loading }: PlanCardProps) {
  const isCurrentPlan = currentPlanId === plan.id;
  const isFree = plan.id === 'FREE';

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
            onClick={() => onSubscribe(plan.id)}
            disabled={loading || isFree}
            className="w-full"
            variant={plan.is_popular ? 'default' : 'outline'}
          >
            {loading ? 'Се вчитува...' : isFree ? 'Бесплатно' : 'Претплати се'}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
