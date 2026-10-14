'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { CalendarPlus, Copy, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import JobStatusBadge from '@/components/bid-service/JobStatusBadge';
import { api } from '@/lib/api';
import { tenderUrl } from '@/lib/utils';
import type { CalendarTokenResponse, DeadlineItem } from '@/lib/bid-service-types';

const MONTHS = [
  'Јануари',
  'Февруари',
  'Март',
  'Април',
  'Мај',
  'Јуни',
  'Јули',
  'Август',
  'Септември',
  'Октомври',
  'Ноември',
  'Декември',
];

function errMsg(e: unknown, fallback: string): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-');
  return y && m && d ? `${d}.${m}.${y}` : iso;
}

function monthKey(iso: string): string {
  return iso.slice(0, 7);
}

function monthLabel(key: string): string {
  const [y, m] = key.split('-');
  const idx = Number(m) - 1;
  return idx >= 0 && idx < 12 ? `${MONTHS[idx]} ${y}` : key;
}

function todayIso(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Skopje' }).format(new Date());
}

export default function PortalCalendarPage() {
  const [token, setToken] = useState<CalendarTokenResponse | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);
  const [rotating, setRotating] = useState(false);

  const [deadlines, setDeadlines] = useState<DeadlineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [tokRes, dlRes] = await Promise.allSettled([api.getCalendarToken(), api.getBidDeadlines()]);
    if (tokRes.status === 'fulfilled') {
      setToken(tokRes.value);
      setTokenError(null);
    } else {
      setTokenError(errMsg(tokRes.reason, 'Линкот за календарот не може да се вчита.'));
    }
    if (dlRes.status === 'fulfilled') {
      setDeadlines(dlRes.value.deadlines);
      setError(null);
    } else {
      setError(errMsg(dlRes.reason, 'Роковите не може да се вчитаат.'));
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const grouped = useMemo(() => {
    const groups: { key: string; items: DeadlineItem[] }[] = [];
    for (const item of deadlines) {
      const key = monthKey(item.date);
      const last = groups[groups.length - 1];
      if (last && last.key === key) last.items.push(item);
      else groups.push({ key, items: [item] });
    }
    return groups;
  }, [deadlines]);

  const today = todayIso();

  const copyUrl = async () => {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token.url);
      toast.success('Линкот е копиран.');
    } catch {
      toast.error('Копирањето не успеа. Изберете го линкот и копирајте го рачно.');
    }
  };

  const rotate = async () => {
    if (
      !window.confirm(
        'Ќе се создаде нов линк. Стариот линк ќе престане да работи и календарите што го користат ќе треба повторно да се поврзат. Продолжи?'
      )
    )
      return;
    setRotating(true);
    try {
      const res = await api.rotateCalendarToken();
      setToken(res);
      setTokenError(null);
      toast.success('Создаден е нов линк.');
    } catch (e: unknown) {
      toast.error(errMsg(e, 'Создавањето нов линк не успеа.'));
    } finally {
      setRotating(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-bold">Календар</h1>
        <p className="text-sm text-muted-foreground">
          Роковите за вашите понуди и препорачаните тендери, на едно место.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Поврзете го вашиот календар</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Додајте ги роковите во Google, Outlook или Apple календар. Календарот се ажурира автоматски.
          </p>
          {loading ? (
            <p className="text-sm text-muted-foreground">Се вчитува…</p>
          ) : tokenError || !token ? (
            <p className="text-sm text-destructive">{tokenError ?? 'Линкот за календарот не може да се вчита.'}</p>
          ) : (
            <>
              <a href={token.webcal_url}>
                <Button>
                  <CalendarPlus className="mr-2 h-4 w-4" />
                  Додај во календар
                </Button>
              </a>
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  Или копирајте го линкот и додајте го рачно како претплата (&bdquo;од URL&ldquo;):
                </p>
                <div className="flex gap-2">
                  <Input readOnly value={token.url} onFocus={(e) => e.currentTarget.select()} />
                  <Button variant="outline" onClick={copyUrl} aria-label="Копирај">
                    <Copy className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="flex flex-col gap-2 border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-muted-foreground">
                  Линкот е личен. Ако сте го споделиле со погрешна личност, создадете нов.
                </p>
                <Button variant="outline" size="sm" disabled={rotating} onClick={rotate}>
                  <RefreshCw className={`mr-2 h-4 w-4 ${rotating ? 'animate-spin' : ''}`} />
                  Нов линк
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Рокови</h2>
        {loading ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Се вчитува…</p>
        ) : error ? (
          <Card>
            <CardContent className="py-6 text-center text-sm text-destructive">{error}</CardContent>
          </Card>
        ) : grouped.length === 0 ? (
          <Card>
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              Нема претстојни рокови. Изберете тендер во{' '}
              <Link href="/portal/tenders" className="text-primary underline-offset-4 hover:underline">
                Тендери за мене
              </Link>
              .
            </CardContent>
          </Card>
        ) : (
          grouped.map((group) => (
            <Card key={group.key}>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{monthLabel(group.key)}</CardTitle>
              </CardHeader>
              <CardContent className="divide-y p-0">
                {group.items.map((item) => {
                  const href =
                    item.kind === 'job' && item.job_id ? `/portal/bid/${item.job_id}` : tenderUrl(item.tender_id);
                  const past = item.date.slice(0, 10) < today;
                  return (
                    <Link
                      key={`${item.kind}-${item.job_id ?? item.tender_id}`}
                      href={href}
                      className="flex flex-col gap-2 px-6 py-3 transition-colors hover:bg-muted/50 sm:flex-row sm:items-center"
                    >
                      <span
                        className={`w-24 shrink-0 text-sm font-medium tabular-nums ${
                          past ? 'text-muted-foreground line-through' : ''
                        }`}
                      >
                        {formatDate(item.date)}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">{item.title ?? item.tender_id}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {item.tender_id}
                          {item.procuring_entity ? ` · ${item.procuring_entity}` : ''}
                        </p>
                      </div>
                      <div className="shrink-0">
                        {item.kind === 'job' && item.status ? (
                          <JobStatusBadge status={item.status} />
                        ) : (
                          <span className="rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200">
                            Препорачан тендер
                          </span>
                        )}
                      </div>
                    </Link>
                  );
                })}
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
