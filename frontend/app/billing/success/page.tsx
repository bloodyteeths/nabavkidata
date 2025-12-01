'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, UserSubscription } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle, ArrowRight } from 'lucide-react';
import { formatDate } from '@/lib/utils';

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

export const dynamic = 'force-dynamic';

export default function SuccessPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);

  useEffect(() => {
    // Track Google Ads conversion
    if (typeof window !== 'undefined' && window.gtag) {
      window.gtag('event', 'conversion', {
        'send_to': 'AW-17761825331/3BPRCLCdvMcbELPkv5VC',
      });
    }
    loadSubscription();
  }, []);

  const loadSubscription = async () => {
    try {
      setLoading(true);
      const data = await api.getCurrentSubscription();
      setSubscription(data);
    } catch (err) {
      console.error('Failed to load subscription:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Се вчитува...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-12 px-4 max-w-2xl">
      <Card className="text-center">
        <CardHeader>
          <div className="mx-auto mb-4">
            <CheckCircle className="h-16 w-16 text-green-500" />
          </div>
          <CardTitle className="text-3xl mb-2">Успешна претплата!</CardTitle>
          <CardDescription className="text-lg">
            Вашата претплата е успешно активирана
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {subscription && (
            <div className="bg-secondary/50 rounded-lg p-6">
              <h3 className="font-semibold text-lg mb-4">Детали на претплатата</h3>
              <div className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">План:</span>
                  <span className="font-medium">{subscription.plan.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Цена:</span>
                  <span className="font-medium">
                    {subscription.plan.price_mkd.toLocaleString()} ден / месечно
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Започнува:</span>
                  <span className="font-medium">
                    {formatDate(subscription.current_period_start, {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Следно обновување:</span>
                  <span className="font-medium">
                    {formatDate(subscription.current_period_end, {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                    })}
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-2">
            <p className="text-muted-foreground">
              Потврда за плаќањето е испратена на вашата е-пошта.
            </p>
            <p className="text-muted-foreground">
              Сега имате пристап до сите карактеристики на вашиот план!
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-4">
            <Button
              onClick={() => router.push('/')}
              className="flex-1"
            >
              Оди на контролна табла
              <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push('/billing')}
              className="flex-1"
            >
              Прегледај наплата
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
