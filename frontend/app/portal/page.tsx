'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, FileUp, Loader2, MessageSquare, Search } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { PageContainer, PageSection } from '@/components/ui/page-container';
import { api } from '@/lib/api';
import type { PortalSummary } from '@/lib/bid-service-types';
import JobCard from '@/components/bid-service/JobCard';
import MatchedTenderCard from '@/components/bid-service/MatchedTenderCard';

const FIRST_STEPS = [
  { n: 1, label: 'Изберете тендер', href: '/portal/tenders', icon: Search },
  { n: 2, label: 'Прикачете ги документите на компанијата', href: '/portal/documents', icon: FileUp },
  { n: 3, label: 'Пишете ни', href: '/portal/messages', icon: MessageSquare },
];

export default function PortalHomePage() {
  const [data, setData] = useState<PortalSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.getPortalSummary());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Податоците не се вчитаа.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !data) {
    return (
      <div className="flex justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Се вчитува…
      </div>
    );
  }

  if (error || !data) {
    return (
      <PageContainer>
        <p className="text-red-600 dark:text-red-400">{error ?? 'Податоците не се вчитаа.'}</p>
        <Button variant="outline" onClick={load}>Обиди се повторно</Button>
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">
          Добредојдовте{data.company_name ? `, ${data.company_name}` : ''}
        </h1>
        <p className="text-sm text-muted-foreground">
          Вашите понуди, документи и рокови на едно место.
        </p>
      </div>

      {data.first_run && (
        <Card className="border-primary/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Како да започнете</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="grid gap-3 sm:grid-cols-3">
              {FIRST_STEPS.map((s) => (
                <li key={s.n}>
                  <Link
                    href={s.href}
                    className="flex h-full items-start gap-3 rounded-md border p-3 transition-colors hover:border-primary/50"
                  >
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                      {s.n}
                    </span>
                    <span className="text-sm font-medium">{s.label}</span>
                  </Link>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {data.your_move.length > 0 && (
        <PageSection>
          <h2 className="text-lg font-semibold">Ваш потег</h2>
          <div className="grid gap-4 md:grid-cols-2">
            {data.your_move.map((j) => (
              <JobCard key={j.id} job={j} />
            ))}
          </div>
        </PageSection>
      )}

      <PageSection>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Во тек</h2>
          <Link href="/portal/bids" className="text-sm text-primary hover:underline">
            Сите понуди
          </Link>
        </div>
        {data.active_jobs.length === 0 ? (
          <p className="text-sm text-muted-foreground">Моментално нема понуди во подготовка.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {data.active_jobs.map((j) => (
              <JobCard key={j.id} job={j} />
            ))}
          </div>
        )}
      </PageSection>

      {/* General-thread unread only: replies about a bid are counted on its JobCard. */}
      {data.unread_general > 0 && (
        <Link
          href="/portal/messages"
          className="flex items-center justify-between gap-3 rounded-md border border-primary/30 bg-primary/5 px-4 py-3 text-sm font-medium hover:bg-primary/10"
        >
          <span className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            {data.unread_general === 1
              ? 'Имате 1 непрочитана порака'
              : `Имате ${data.unread_general} непрочитани пораки`}
          </span>
          <ArrowRight className="h-4 w-4" />
        </Link>
      )}

      <PageSection>
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Тендери за вас</h2>
          <Link href="/portal/tenders" className="text-sm text-primary hover:underline">
            Сите тендери
          </Link>
        </div>
        {data.matched_tenders.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Сè уште немаме тендери што одговараат на вашиот профил.
          </p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.matched_tenders.map((t) => (
              <MatchedTenderCard key={t.tender_id} tender={t} />
            ))}
          </div>
        )}
      </PageSection>
    </PageContainer>
  );
}
