'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Briefcase, Search, UserRound } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import type { BidAgreement } from '@/lib/bid-service-types';
import { AgreementTerms } from '@/components/bid-service/StartBidButton';
import KeywordsEditor from '@/components/bid-service/KeywordsEditor';
import { formatDmy } from '@/components/bid-service/DeadlineWarning';

/**
 * Settings for clients of the bid service. Replaces the legacy SaaS settings
 * (plans, referrals, sector preferences that never fed the portal) with the
 * client's own terms and the keywords that drive „Тендери за мене“.
 */
export default function PortalSettingsPanel() {
  const { user } = useAuth();
  const [agreement, setAgreement] = useState<BidAgreement | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getBidAgreement()
      .then((res) => {
        if (!cancelled) setAgreement(res);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Условите не се вчитаа.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const statusText =
    user?.account_type === 'managed_client'
      ? 'Вие сте клиент на услугата. Изберете тендер во порталот и ние ја подготвуваме понудата.'
      : 'Вашиот профил е отворен. Изберете тендер во порталот, а ние ќе ви издадеме фактура пред да започнеме.';

  return (
    <div className="container mx-auto max-w-4xl space-y-6 px-3 py-4 md:px-4 md:py-8">
      <div>
        <h1 className="text-2xl font-bold md:text-3xl">Поставки</h1>
        <p className="mt-1 text-sm text-muted-foreground">Вашите услови и тендерите што ги следиме за вас.</p>
      </div>

      <Card className="border-primary/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Briefcase className="h-5 w-5 text-primary" />
            Услуга
          </CardTitle>
          <CardDescription>{statusText}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          {agreement ? (
            <>
              <AgreementTerms agreement={agreement} />
              <p className="text-xs text-muted-foreground">
                {agreement.accepted
                  ? `Условите ги прифативте на ${formatDmy(agreement.terms_agreed_at)}.`
                  : 'Условите ги прифаќате при првата понуда.'}
              </p>
            </>
          ) : (
            !error && <p className="text-sm text-muted-foreground">Се вчитува…</p>
          )}
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button asChild>
              <Link href="/portal">Отвори портал</Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/portal/tenders">
                <Search className="mr-1.5 h-4 w-4" />
                Тендери за мене
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Што следиме за вас</CardTitle>
          <CardDescription>
            Клучни зборови од насловите на тендерите. Од нив се полни „Тендери за мене“ и известувањата за нови
            тендери.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <KeywordsEditor />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <UserRound className="h-5 w-5" />
            Профил
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 text-sm">
          <p>
            <span className="text-muted-foreground">Е-пошта: </span>
            {user?.email ?? '—'}
          </p>
          <p>
            <span className="text-muted-foreground">Компанија: </span>
            {user?.company_name || '—'}
          </p>
          <p className="pt-2 text-muted-foreground">
            За промена на податоците на компанијата{' '}
            <Link href="/portal/messages" className="text-primary underline underline-offset-4">
              пишете ни
            </Link>
            .
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
