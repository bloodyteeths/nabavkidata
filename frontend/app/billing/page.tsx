'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api, UserSubscription, Invoice, UsageStats } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { CreditCard, Download, Calendar, TrendingUp, AlertCircle } from 'lucide-react';
import { formatDate } from '@/lib/utils';

export default function BillingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [subscription, setSubscription] = useState<UserSubscription | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    loadBillingData();
  }, []);

  const loadBillingData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [subscriptionData, invoicesData, usageData] = await Promise.all([
        api.getCurrentSubscription(),
        api.getInvoices(),
        api.getUsage(),
      ]);

      setSubscription(subscriptionData);
      setInvoices(invoicesData);
      setUsage(usageData);
    } catch (err: any) {
      setError(err.message || 'Грешка при вчитување на податоци');
    } finally {
      setLoading(false);
    }
  };

  const handleManagePayment = async () => {
    try {
      const { url } = await api.createPortalSession();
      window.location.href = url;
    } catch (err: any) {
      setError(err.message || 'Грешка при отворање на порталот');
    }
  };

  const handleCancelSubscription = async () => {
    if (!confirm('Дали сте сигурни дека сакате да ја откажете претплатата?')) {
      return;
    }

    try {
      setCancelling(true);
      await api.cancelSubscription();
      await loadBillingData();
    } catch (err: any) {
      setError(err.message || 'Грешка при откажување на претплатата');
    } finally {
      setCancelling(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, any> = {
      active: 'success',
      canceled: 'destructive',
      past_due: 'warning',
      incomplete: 'secondary',
    };

    const labels: Record<string, string> = {
      active: 'Активна',
      canceled: 'Откажана',
      past_due: 'Задоцнета',
      incomplete: 'Некомплетна',
    };

    return (
      <Badge variant={variants[status] || 'default'}>
        {labels[status] || status}
      </Badge>
    );
  };

  const formatDateDisplay = (date: string) =>
    formatDate(date, { year: 'numeric', month: 'long', day: 'numeric' });

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
    <div className="container mx-auto py-8 px-4 max-w-6xl">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold mb-2">Наплата</h1>
          <p className="text-muted-foreground">
            Управувајте со вашата претплата и наплата
          </p>
        </div>
        <Button onClick={() => router.push('/billing/plans')}>
          Прегледај планови
        </Button>
      </div>

      {error && (
        <Card className="mb-6 border-destructive">
          <CardContent className="pt-6">
            <div className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              <p>{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 md:grid-cols-2 mb-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5" />
              Тековна претплата
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {subscription ? (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-2xl font-bold">{subscription.plan.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {subscription.plan.price_mkd.toLocaleString()} ден / месечно
                    </p>
                  </div>
                  {getStatusBadge(subscription.status)}
                </div>

                <div className="space-y-2 pt-4 border-t">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Започнува:</span>
                    <span>{formatDateDisplay(subscription.current_period_start)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Обновување:</span>
                    <span>{formatDateDisplay(subscription.current_period_end)}</span>
                  </div>
                  {subscription.cancel_at_period_end && (
                    <div className="flex items-center gap-2 text-sm text-destructive">
                      <AlertCircle className="h-4 w-4" />
                      <span>Ќе биде откажана на крајот на периодот</span>
                    </div>
                  )}
                </div>

                <div className="flex gap-2 pt-4">
                  <Button
                    variant="outline"
                    onClick={handleManagePayment}
                    className="flex-1"
                  >
                    Управувај наплата
                  </Button>
                  {subscription.status === 'active' && !subscription.cancel_at_period_end && (
                    <Button
                      variant="destructive"
                      onClick={handleCancelSubscription}
                      disabled={cancelling}
                      className="flex-1"
                    >
                      {cancelling ? 'Се откажува...' : 'Откажи'}
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center py-8">
                <p className="text-muted-foreground mb-4">
                  Немате активна претплата
                </p>
                <Button onClick={() => router.push('/billing/plans')}>
                  Изберете план
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Користење
            </CardTitle>
            <CardDescription>За периодот: {usage?.period}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {usage ? (
              <>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-muted-foreground">Прегледани тендери</span>
                      <span className="font-medium">
                        {usage.tenders_viewed} / {usage.limit === -1 ? '∞' : usage.limit}
                      </span>
                    </div>
                    <div className="w-full bg-secondary rounded-full h-2">
                      <div
                        className="bg-primary h-2 rounded-full transition-all"
                        style={{
                          width: usage.limit === -1 ? '0%' : `${Math.min((usage.tenders_viewed / usage.limit) * 100, 100)}%`,
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-muted-foreground">Пребарувања</span>
                      <span className="font-medium">{usage.searches_made}</span>
                    </div>
                  </div>
                </div>

                {usage.limit !== -1 && usage.tenders_viewed >= usage.limit * 0.8 && (
                  <div className="flex items-start gap-2 p-3 bg-warning/10 rounded-lg border border-warning">
                    <AlertCircle className="h-5 w-5 text-warning mt-0.5" />
                    <div className="text-sm">
                      <p className="font-medium text-warning">Близу до лимитот</p>
                      <p className="text-muted-foreground">
                        Надградете го планот за неограничено користење
                      </p>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-center text-muted-foreground py-8">
                Нема податоци за користење
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Историја на наплата
          </CardTitle>
        </CardHeader>
        <CardContent>
          {invoices.length > 0 ? (
            <div className="space-y-2">
              <div className="grid grid-cols-4 gap-4 pb-3 border-b text-sm font-medium text-muted-foreground">
                <div>Датум</div>
                <div>Износ</div>
                <div>Статус</div>
                <div>Фактура</div>
              </div>
              {invoices.map((invoice) => (
                <div
                  key={invoice.id}
                  className="grid grid-cols-4 gap-4 py-3 border-b last:border-0 text-sm"
                >
                  <div>{formatDateDisplay(invoice.created_at)}</div>
                  <div className="font-medium">
                    {invoice.amount.toLocaleString()} ден
                  </div>
                  <div>
                    <Badge variant={invoice.status === 'paid' ? 'success' : 'warning'}>
                      {invoice.status === 'paid' ? 'Платена' : 'Неплатена'}
                    </Badge>
                  </div>
                  <div>
                    {invoice.invoice_pdf && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => window.open(invoice.invoice_pdf, '_blank')}
                      >
                        <Download className="h-4 w-4 mr-1" />
                        Преземи
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center text-muted-foreground py-8">
              Нема историја на наплата
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
