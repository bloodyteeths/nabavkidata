'use client';

import { useEffect, useMemo, useState } from 'react';
import { FileText, Loader2 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PageContainer } from '@/components/ui/page-container';
import { EmptyState } from '@/components/ui/empty-state';
import { api } from '@/lib/api';
import { TERMINAL_STATUSES } from '@/lib/bid-service-types';
import type { BidJobSummary } from '@/lib/bid-service-types';
import JobCard from '@/components/bid-service/JobCard';

export default function PortalBidsPage() {
  const [jobs, setJobs] = useState<BidJobSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getMyBidJobs()
      .then((res) => {
        if (!cancelled) setJobs(res.jobs);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Понудите не се вчитаа.');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const [active, done] = useMemo(() => {
    const list = jobs ?? [];
    return [
      list.filter((j) => !TERMINAL_STATUSES.includes(j.status)),
      list.filter((j) => TERMINAL_STATUSES.includes(j.status)),
    ];
  }, [jobs]);

  const renderList = (list: BidJobSummary[], emptyTitle: string, emptyDescription?: string) =>
    list.length === 0 ? (
      <EmptyState
        icon={FileText}
        title={emptyTitle}
        description={emptyDescription}
        action={{ label: 'Тендери за мене', href: '/portal/tenders' }}
      />
    ) : (
      <div className="grid gap-4 md:grid-cols-2">
        {list.map((j) => (
          <JobCard key={j.id} job={j} />
        ))}
      </div>
    );

  return (
    <PageContainer>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Мои понуди</h1>
        <p className="text-sm text-muted-foreground">Сите понуди што ги подготвуваме за вас.</p>
      </div>

      {error ? (
        <p className="text-red-600 dark:text-red-400">{error}</p>
      ) : jobs === null ? (
        <div className="flex justify-center py-16 text-muted-foreground">
          <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Се вчитува…
        </div>
      ) : (
        <Tabs defaultValue="active">
          <TabsList>
            <TabsTrigger value="active">Активни ({active.length})</TabsTrigger>
            <TabsTrigger value="done">Завршени ({done.length})</TabsTrigger>
          </TabsList>
          <TabsContent value="active" className="mt-4">
            {renderList(
              active,
              'Немате активни понуди',
              'Изберете тендер и ние ќе ја подготвиме понудата за вас.'
            )}
          </TabsContent>
          <TabsContent value="done" className="mt-4">
            {renderList(done, 'Сè уште нема завршени понуди')}
          </TabsContent>
        </Tabs>
      )}
    </PageContainer>
  );
}
