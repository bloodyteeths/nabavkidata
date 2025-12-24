'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Check, Zap, Users, Building2, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Switch } from '@/components/ui/switch';
import { api } from '@/lib/api';

type Currency = 'mkd' | 'eur';
type Interval = 'monthly' | 'yearly';

interface PlanFeature {
  text: string;
  included: boolean;
}

interface Plan {
  id: string;
  name: string;
  description: string;
  price: { mkd: number; eur: number };
  yearlyPrice: { mkd: number; eur: number };
  features: PlanFeature[];
  popular?: boolean;
  cta: string;
  icon: React.ReactNode;
}

const plans: Plan[] = [
  {
    id: 'start',
    name: 'Стартуј',
    description: 'За фриленсери и мали бизниси',
    price: { mkd: 1990, eur: 39 },
    yearlyPrice: { mkd: 19900, eur: 390 },
    icon: <Zap className="h-6 w-6" />,
    cta: 'Започни',
    features: [
      { text: '15 AI прашања дневно', included: true },
      { text: '10 зачувани известувања', included: true },
      { text: 'CSV извоз', included: true },
      { text: 'Основна аналитика', included: true },
      { text: '5 известувања за конкуренти', included: true },
      { text: 'Поддршка преку е-пошта', included: true },
      { text: 'PDF извоз', included: false },
      { text: 'Анализа на ризик', included: false },
      { text: 'API пристап', included: false },
    ],
  },
  {
    id: 'pro',
    name: 'Про',
    description: 'За растечки компании',
    price: { mkd: 5990, eur: 99 },
    yearlyPrice: { mkd: 59900, eur: 990 },
    icon: <Users className="h-6 w-6" />,
    cta: 'Надградете на Про',
    popular: true,
    features: [
      { text: '50 AI прашања дневно', included: true },
      { text: '50 зачувани известувања', included: true },
      { text: 'CSV и PDF извоз', included: true },
      { text: 'Целосна аналитика', included: true },
      { text: 'Анализа на ризик', included: true },
      { text: '20 известувања за конкуренти', included: true },
      { text: 'Приоритетна поддршка', included: true },
      { text: 'API пристап', included: false },
      { text: 'Тимски функции', included: false },
    ],
  },
  {
    id: 'team',
    name: 'Тим',
    description: 'За тимови и одделенија',
    price: { mkd: 12990, eur: 199 },
    yearlyPrice: { mkd: 129900, eur: 1990 },
    icon: <Building2 className="h-6 w-6" />,
    cta: 'Контактирајте не',
    features: [
      { text: 'Неограничени AI прашања', included: true },
      { text: 'Неограничени известувања', included: true },
      { text: 'Неограничен извоз', included: true },
      { text: 'Целосна аналитика и ризик', included: true },
      { text: 'До 5 членови на тим', included: true },
      { text: 'Основен API пристап', included: true },
      { text: 'Приоритетна поддршка', included: true },
      { text: 'Неограничени конкуренти', included: true },
      { text: 'Тимски дашборд', included: true },
    ],
  },
];

export default function PlansPage() {
  const router = useRouter();
  const [currency, setCurrency] = useState<Currency>('mkd');
  const [interval, setInterval] = useState<Interval>('monthly');
  const [loading, setLoading] = useState<string | null>(null);

  const formatPrice = (price: number, curr: Currency) => {
    if (curr === 'mkd') {
      return `${price.toLocaleString('mk-MK')} МКД`;
    }
    return `€${price}`;
  };

  const handleSubscribe = async (planId: string) => {
    setLoading(planId);
    try {
      // Use the existing createCheckoutSession API method
      const response = await api.createCheckoutSession(planId, interval);

      if (response.checkout_url) {
        window.location.href = response.checkout_url;
      }
    } catch (error: any) {
      console.error('Checkout error:', error);
      // Handle not logged in
      if (error.message?.includes('401') || error.status === 401) {
        router.push('/login?redirect=/plans');
      }
    } finally {
      setLoading(null);
    }
  };

  const handleStartTrial = async () => {
    setLoading('trial');
    try {
      // Redirect to login with trial param - trial is started after login/signup
      router.push('/signup?trial=true');
    } catch (error: any) {
      console.error('Trial start error:', error);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            Изберете го вашиот план
          </h1>
          <p className="text-xl text-gray-600 max-w-2xl mx-auto">
            Добијте пристап до македонски тендери со AI-базирано пребарување и анализа
          </p>
        </div>

        {/* Trial Banner */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 mb-8 text-center">
          <h3 className="text-lg font-semibold text-blue-900 mb-2">
            🎁 7-дневна бесплатна проба на Про план
          </h3>
          <p className="text-blue-700 mb-4">
            50 AI пораки • 15 екстракции на документи • 5 извози • 20 конкурентски известувања
          </p>
          <Button
            onClick={handleStartTrial}
            disabled={loading === 'trial'}
            className="bg-blue-600 hover:bg-blue-700"
          >
            {loading === 'trial' ? 'Се вчитува...' : 'Започни бесплатна проба'}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>

        {/* Controls */}
        <div className="flex flex-col sm:flex-row justify-center items-center gap-6 mb-10">
          {/* Currency Toggle */}
          <div className="flex items-center gap-3 bg-white rounded-lg border p-2">
            <span className={`text-sm ${currency === 'mkd' ? 'font-semibold text-gray-900' : 'text-gray-500'}`}>
              МКД
            </span>
            <Switch
              checked={currency === 'eur'}
              onCheckedChange={(checked) => setCurrency(checked ? 'eur' : 'mkd')}
            />
            <span className={`text-sm ${currency === 'eur' ? 'font-semibold text-gray-900' : 'text-gray-500'}`}>
              EUR
            </span>
          </div>

          {/* Interval Toggle */}
          <div className="flex items-center gap-3 bg-white rounded-lg border p-2">
            <span className={`text-sm ${interval === 'monthly' ? 'font-semibold text-gray-900' : 'text-gray-500'}`}>
              Месечно
            </span>
            <Switch
              checked={interval === 'yearly'}
              onCheckedChange={(checked) => setInterval(checked ? 'yearly' : 'monthly')}
            />
            <span className={`text-sm ${interval === 'yearly' ? 'font-semibold text-gray-900' : 'text-gray-500'}`}>
              Годишно
              <Badge variant="secondary" className="ml-2 bg-green-100 text-green-700">
                -17%
              </Badge>
            </span>
          </div>
        </div>

        {/* Payment Methods Note */}
        {currency === 'eur' && (
          <p className="text-center text-sm text-gray-500 mb-8">
            💳 Картичка или SEPA директна дебитација
          </p>
        )}

        {/* Plans Grid */}
        <div className="grid md:grid-cols-3 gap-8 mb-16">
          {plans.map((plan) => {
            const price = interval === 'yearly' ? plan.yearlyPrice : plan.price;
            const displayPrice = price[currency];
            const monthlyEquivalent = interval === 'yearly' ? Math.round(displayPrice / 12) : displayPrice;

            return (
              <Card
                key={plan.id}
                className={`relative flex flex-col ${
                  plan.popular
                    ? 'border-2 border-blue-500 shadow-lg scale-105'
                    : 'border border-gray-200'
                }`}
              >
                {plan.popular && (
                  <Badge className="absolute -top-3 left-1/2 -translate-x-1/2 bg-blue-500">
                    Најпопуларен
                  </Badge>
                )}

                <CardHeader>
                  <div className="flex items-center gap-3 mb-2">
                    <div className={`p-2 rounded-lg ${plan.popular ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-600'}`}>
                      {plan.icon}
                    </div>
                    <CardTitle className="text-xl">{plan.name}</CardTitle>
                  </div>
                  <CardDescription>{plan.description}</CardDescription>
                </CardHeader>

                <CardContent className="flex-grow">
                  <div className="mb-6">
                    <span className="text-4xl font-bold text-gray-900">
                      {formatPrice(monthlyEquivalent, currency)}
                    </span>
                    <span className="text-gray-500">/месец</span>
                    {interval === 'yearly' && (
                      <p className="text-sm text-gray-500 mt-1">
                        Наплаќање {formatPrice(displayPrice, currency)} годишно
                      </p>
                    )}
                  </div>

                  <ul className="space-y-3">
                    {plan.features.map((feature, index) => (
                      <li key={index} className="flex items-start gap-2">
                        <Check
                          className={`h-5 w-5 flex-shrink-0 mt-0.5 ${
                            feature.included ? 'text-green-500' : 'text-gray-300'
                          }`}
                        />
                        <span className={feature.included ? 'text-gray-700' : 'text-gray-400'}>
                          {feature.text}
                        </span>
                      </li>
                    ))}
                  </ul>
                </CardContent>

                <CardFooter>
                  <Button
                    className={`w-full ${plan.popular ? 'bg-blue-600 hover:bg-blue-700' : ''}`}
                    variant={plan.popular ? 'default' : 'outline'}
                    onClick={() => handleSubscribe(plan.id)}
                    disabled={loading === plan.id}
                  >
                    {loading === plan.id ? 'Се вчитува...' : plan.cta}
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>

        {/* Enterprise CTA */}
        <div className="bg-gray-900 rounded-2xl p-8 text-center text-white mb-16">
          <h2 className="text-2xl font-bold mb-4">Претпријатие</h2>
          <p className="text-gray-300 mb-6 max-w-2xl mx-auto">
            Прилагодено решение за големи организации. Неограничен пристап, API интеграција,
            посветен менаџер на сметка и SLA гаранција.
          </p>
          <Button
            variant="outline"
            className="bg-transparent border-white text-white hover:bg-white hover:text-gray-900"
            onClick={() => router.push('/contact?plan=enterprise')}
          >
            Контактирајте не
          </Button>
        </div>

        {/* FAQ */}
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-center mb-8">Често поставувани прашања</h2>
          <div className="space-y-6">
            <div className="bg-white rounded-lg border p-6">
              <h3 className="font-semibold text-lg mb-2">Што е вклучено во бесплатната проба?</h3>
              <p className="text-gray-600">
                7-дневен пристап до сите Про функции со ограничени кредити: 50 AI пораки,
                15 екстракции на документи, 5 извози и 20 конкурентски известувања.
              </p>
            </div>
            <div className="bg-white rounded-lg border p-6">
              <h3 className="font-semibold text-lg mb-2">Можам ли да го променам планот?</h3>
              <p className="text-gray-600">
                Да, можете да надградите или деградирате во секое време. Промените ќе
                бидат пропорционално пресметани.
              </p>
            </div>
            <div className="bg-white rounded-lg border p-6">
              <h3 className="font-semibold text-lg mb-2">Кои начини на плаќање се поддржани?</h3>
              <p className="text-gray-600">
                За МКД: картичка. За EUR: картичка или SEPA директна дебитација.
                Сите плаќања се обработуваат сигурно преку Stripe.
              </p>
            </div>
            <div className="bg-white rounded-lg border p-6">
              <h3 className="font-semibold text-lg mb-2">Како да ја откажам претплатата?</h3>
              <p className="text-gray-600">
                Можете да ја откажете претплатата во секое време од вашиот профил.
                Ќе имате пристап до крајот на тековниот период на плаќање.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
