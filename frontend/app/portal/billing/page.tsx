'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { CheckCircle2, CreditCard, Loader2, ShieldCheck } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { PageContainer } from '@/components/ui/page-container';
import { api } from '@/lib/api';
import type { BillingStatus } from '@/lib/bid-service-types';
import { formatDmy } from '@/components/bid-service/DeadlineWarning';

type Notice = { tone: 'ok' | 'warn'; text: string } | null;

function errMsg(e: unknown, fallback: string): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

function brandLabel(brand: string | null): string {
  if (!brand) return 'Картичка';
  const b = brand.toLowerCase();
  if (b === 'visa') return 'Visa';
  if (b === 'mastercard') return 'Mastercard';
  if (b === 'amex') return 'American Express';
  return brand.charAt(0).toUpperCase() + brand.slice(1);
}

/**
 * Client billing: the saved card (Stripe, setup mode) and whether the success
 * fee is authorised. The card is only charged for the success fee, no earlier
 * than seven days after our written notice; the invoice route stays available.
 */
export default function PortalBillingPage() {
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [busy, setBusy] = useState<'card' | 'terms' | 'confirming' | null>(null);
  const [ticked, setTicked] = useState(false);
  const handled = useRef(false);

  const load = useCallback(async () => {
    try {
      setStatus(await api.getServiceBillingStatus());
      setLoadError(null);
    } catch (e) {
      setLoadError(errMsg(e, 'Податоците за плаќање не се вчитаа.'));
    }
  }, []);

  useEffect(() => {
    if (handled.current || typeof window === 'undefined') return;
    handled.current = true;
    const setup = new URLSearchParams(window.location.search).get('setup');
    const strip = () => window.history.replaceState(window.history.state, '', window.location.pathname);
    if (setup === 'cancelled') {
      strip();
      setNotice({ tone: 'warn', text: 'Додавањето на картичката е откажано.' });
      void load();
      return;
    }
    if (setup && setup.startsWith('cs_')) {
      setBusy('confirming');
      (async () => {
        try {
          setStatus(await api.completeCardSetup(setup));
          setNotice({ tone: 'ok', text: 'Картичката е зачувана.' });
        } catch (e) {
          setNotice({ tone: 'warn', text: errMsg(e, 'Картичката не може да се потврди. Обидете се повторно.') });
          await load();
        } finally {
          strip();
          setBusy(null);
        }
      })();
      return;
    }
    void load();
  }, [load]);

  const addCard = async () => {
    setBusy('card');
    setNotice(null);
    try {
      const { url } = await api.startCardSetup();
      window.location.href = url;
    } catch (e) {
      setNotice({ tone: 'warn', text: errMsg(e, 'Додавањето картичка не може да започне. Обидете се повторно.') });
      setBusy(null);
    }
  };

  const acceptTerms = async () => {
    if (!status) return;
    setBusy('terms');
    setNotice(null);
    try {
      await api.acceptBidAgreement(status.current_version);
      await load();
      setTicked(false);
    } catch (e) {
      setNotice({ tone: 'warn', text: errMsg(e, 'Условите не се зачуваа. Обидете се повторно.') });
    } finally {
      setBusy(null);
    }
  };

  return (
    <PageContainer className="max-w-3xl">
      <div className="space-y-1">
        <h1 className="text-2xl font-bold">Плаќање</h1>
        <p className="text-sm text-muted-foreground">
          Надоместот за подготовка го плаќате со картичка или по фактура. Зачуваната картичка се користи
          само за надоместот за успех кога ќе ви биде доделена набавка.
        </p>
      </div>

      {notice && (
        <p
          className={
            notice.tone === 'ok'
              ? 'rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-800 dark:bg-green-950/40 dark:text-green-200'
              : 'rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100'
          }
        >
          {notice.text}
        </p>
      )}

      {loadError && !status && <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>}

      {!status ? (
        !loadError && (
          <div className="flex items-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {busy === 'confirming' ? 'Ја потврдуваме картичката…' : 'Се вчитува…'}
          </div>
        )
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <CreditCard className="h-4 w-4" />
                Платежна картичка
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {status.has_card ? (
                <p className="font-medium">
                  {brandLabel(status.card_brand)}
                  {status.card_last4 ? ` што завршува на ${status.card_last4}` : ''}
                </p>
              ) : (
                <p className="font-medium">Нема зачувана картичка</p>
              )}
              {status.card_payments_enabled ? (
                <>
                  <Button size="sm" variant={status.has_card ? 'outline' : 'default'} onClick={addCard} disabled={busy !== null}>
                    {busy === 'card' && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                    {status.has_card ? 'Замени картичка' : 'Додај картичка'}
                  </Button>
                  <p className="text-xs text-muted-foreground">
                    Податоците за картичката ги обработува Stripe. Ние не ги гледаме и не ги чуваме бројот и
                    кодот на картичката.
                  </p>
                </>
              ) : (
                <p className="text-muted-foreground">
                  Плаќањето со картичка моментално не е достапно. Може да платите по фактура.
                </p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <ShieldCheck className="h-4 w-4" />
                Надомест за успех
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {status.success_fee_pct !== null && (
                <p>
                  <span className="font-semibold">{status.success_fee_pct}%</span> од вредноста на договорот за
                  првата година, намалено за надоместот за подготовка платен за таа понуда.
                </p>
              )}
              {status.success_fee_authorised ? (
                <p className="flex items-start gap-2 font-medium text-green-700 dark:text-green-400">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    Овластено (
                    {status.success_fee_authorised_via === 'offline' ? 'писмен договор' : 'картичка'}) на{' '}
                    {formatDmy(status.success_fee_authorised_at)}.
                  </span>
                </p>
              ) : (
                <div className="space-y-2">
                  <p className="font-medium text-amber-700 dark:text-amber-300">Сè уште не е овластено.</p>
                  <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
                    {!status.terms_accepted && <li>Прифатете ги тековните услови на услугата.</li>}
                    {!status.has_card && (
                      <li>Зачувајте картичка, или договорете плаќање по фактура со писмено овластување.</li>
                    )}
                  </ul>
                </div>
              )}
              {!status.terms_accepted && (
                <div className="space-y-2 rounded-md border p-3">
                  <label className="flex cursor-pointer items-start gap-2">
                    <Checkbox
                      checked={ticked}
                      onCheckedChange={(v) => setTicked(v === true)}
                      disabled={busy !== null}
                      className="mt-0.5"
                    />
                    <span>
                      Ги прочитав и ги прифаќам{' '}
                      <Link href="/terms" target="_blank" className="text-primary underline underline-offset-4">
                        условите на услугата
                      </Link>
                      .
                    </span>
                  </label>
                  <Button size="sm" onClick={acceptTerms} disabled={!ticked || busy !== null}>
                    {busy === 'terms' && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                    Прифаќам
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Како се наплаќа надоместот за успех</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                Кога ќе ви биде доделена набавка за која ја подготвивме понудата, ви пишуваме однапред. Износот и
                деталите ги гледате во порталот, кај понудата.
              </p>
              <p>
                Наплатата од зачуваната картичка е најрано седум дена по нашата најава. Ако имате забелешка, одговорете
                ни во тој рок и наплатата се запира додека не ја разрешиме.
              </p>
              <p>
                Ако не сакате плаќање со картичка, може да платите по фактура од Фактурино ДООЕЛ. Тогаш овластувањето за
                надоместот за успех се дава писмено, а ние го евидентираме.
              </p>
              <p>Износите се без ДДВ: Фактурино ДООЕЛ не е ДДВ обврзник.</p>
            </CardContent>
          </Card>
        </div>
      )}
    </PageContainer>
  );
}
