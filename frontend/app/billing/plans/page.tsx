'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, SubscriptionPlan, UserSubscription } from '@/lib/api';
import { PlanCard } from '@/components/billing/PlanCard';
import { Card, CardContent } from '@/components/ui/card';
import { Check, AlertCircle } from 'lucide-react';

export default function PlansPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [subscribing, setSubscribing] = useState(false);
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [currentSubscription, setCurrentSubscription] = useState<UserSubscription | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [plansData, subscriptionData] = await Promise.all([
        api.getPlans(),
        api.getCurrentSubscription().catch(() => null),
      ]);

      setPlans(plansData);
      setCurrentSubscription(subscriptionData);
    } catch (err: any) {
      setError(err.message || 'Грешка при вчитување на планови');
    } finally {
      setLoading(false);
    }
  };

  const handleSubscribe = async (planId: string) => {
    if (planId === 'FREE') {
      return;
    }

    try {
      setSubscribing(true);
      setError(null);

      const { url } = await api.createCheckoutSession(planId);
      window.location.href = url;
    } catch (err: any) {
      setError(err.message || 'Грешка при креирање на сесија');
      setSubscribing(false);
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
    <div className="container mx-auto py-12 px-4 max-w-7xl">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold mb-4">Изберете го вашиот план</h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Најдете го совршениот план за вашите потреби. Надградете или откажете во секое време.
        </p>
      </div>

      {error && (
        <Card className="mb-8 border-destructive max-w-2xl mx-auto">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <p>{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4 mb-12">
        {plans.map((plan) => (
          <PlanCard
            key={plan.id}
            plan={plan}
            currentPlanId={currentSubscription?.plan.id}
            onSubscribe={handleSubscribe}
            loading={subscribing}
          />
        ))}
      </div>

      <Card className="max-w-5xl mx-auto">
        <CardContent className="pt-6">
          <h2 className="text-2xl font-bold mb-6 text-center">
            Споредба на карактеристики
          </h2>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-4 px-4">Карактеристика</th>
                  {plans.map((plan) => (
                    <th key={plan.id} className="text-center py-4 px-4">
                      <div className="font-bold">{plan.name}</div>
                      <div className="text-sm font-normal text-muted-foreground">
                        {plan.price_mkd === 0 ? 'Бесплатно' : `${plan.price_mkd.toLocaleString()} ден/мес`}
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">Пристап до тендери</td>
                  {plans.map((plan) => (
                    <td key={plan.id} className="text-center py-4 px-4">
                      <Check className="h-5 w-5 text-primary mx-auto" />
                    </td>
                  ))}
                </tr>

                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">Основно пребарување</td>
                  {plans.map((plan) => (
                    <td key={plan.id} className="text-center py-4 px-4">
                      <Check className="h-5 w-5 text-primary mx-auto" />
                    </td>
                  ))}
                </tr>

                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">Напредно филтрирање</td>
                  <td className="text-center py-4 px-4">-</td>
                  {plans.slice(1).map((plan) => (
                    <td key={plan.id} className="text-center py-4 px-4">
                      <Check className="h-5 w-5 text-primary mx-auto" />
                    </td>
                  ))}
                </tr>

                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">Персонализирани препораки</td>
                  <td className="text-center py-4 px-4">-</td>
                  {plans.slice(1).map((plan) => (
                    <td key={plan.id} className="text-center py-4 px-4">
                      <Check className="h-5 w-5 text-primary mx-auto" />
                    </td>
                  ))}
                </tr>

                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">Известувања по е-пошта</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                </tr>

                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">Следење на конкуренција</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                </tr>

                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">RAG AI асистент</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                </tr>

                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">Приоритетна поддршка</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                </tr>

                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">API пристап</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                </tr>

                <tr className="border-b">
                  <td className="py-4 px-4 text-sm">Извештаи и аналитика</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">-</td>
                  <td className="text-center py-4 px-4">
                    <Check className="h-5 w-5 text-primary mx-auto" />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="mt-12 text-center">
        <p className="text-muted-foreground mb-4">
          Сите планови вклучуваат 14-дневна гаранција за враќање на пари
        </p>
        <p className="text-sm text-muted-foreground">
          Цените се во МКД. Автоматски се конвертираат во EUR според тековниот курс.
        </p>
      </div>
    </div>
  );
}
