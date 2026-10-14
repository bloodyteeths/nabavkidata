'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { Inbox, MessageSquare, RefreshCw, Search, X } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import JobStatusBadge from '@/components/bid-service/JobStatusBadge';
import MessageThread from '@/components/bid-service/MessageThread';
import { api } from '@/lib/api';
import {
  BID_STATUS_LABELS,
  formatMkd,
  type AdminBidJobFilters,
  type AdminBidJobSummary,
  type AdminBidSummary,
  type AdminInboxThread,
  type BidJobStatus,
  type BidMessage,
  type PaidVia,
} from '@/lib/bid-service-types';

type StatusFilter = NonNullable<AdminBidJobFilters['status']>;

const GROUP_FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'open', label: 'Отворени' },
  { value: 'needs_us', label: 'Наш потег' },
  { value: 'needs_client', label: 'Потег на клиентот' },
  { value: 'all', label: 'Сите' },
];

const ALL_STATUSES = Object.keys(BID_STATUS_LABELS) as BidJobStatus[];

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

function formatDay(value: string | null | undefined): string {
  if (!value) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (m) return `${m[3]}.${m[2]}.${m[1]}`;
  return value;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('mk-MK', {
    timeZone: 'Europe/Skopje',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

const PAID_VIA_LABELS: Record<PaidVia, string> = {
  stripe: 'Картичка',
  invoice: 'Фактура',
  free: 'Бесплатно',
};

const PAID_VIA_CLASSES: Record<PaidVia, string> = {
  stripe: 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300',
  invoice: 'bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300',
  free: 'bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300',
};

/** paid_via comes from the shared admin serializer; older rows fall back to free/paid_at. */
function paidVia(job: AdminBidJobSummary): PaidVia | null {
  const v = (job as AdminBidJobSummary & { paid_via?: PaidVia | null }).paid_via;
  if (v) return v;
  if (job.free) return 'free';
  return job.paid_at ? 'invoice' : null;
}

function PaidViaBadge({ via }: { via: PaidVia | null }) {
  if (!via) return null;
  return (
    <span
      className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[11px] font-semibold ${PAID_VIA_CLASSES[via]}`}
    >
      {PAID_VIA_LABELS[via]}
    </span>
  );
}

function SummaryTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | undefined;
  tone: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className={`mt-1 text-3xl font-bold ${tone}`}>{value ?? '—'}</p>
      </CardContent>
    </Card>
  );
}

export default function AdminBidsPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('open');
  const [onlyMine, setOnlyMine] = useState(false);
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');

  const [jobs, setJobs] = useState<AdminBidJobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<AdminBidSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [threads, setThreads] = useState<AdminInboxThread[]>([]);
  const [totalUnread, setTotalUnread] = useState(0);
  const [inboxLoading, setInboxLoading] = useState(true);
  const [inboxError, setInboxError] = useState<string | null>(null);

  const [openThread, setOpenThread] = useState<AdminInboxThread | null>(null);
  const [threadMessages, setThreadMessages] = useState<BidMessage[]>([]);
  const [threadLoading, setThreadLoading] = useState(false);
  const [threadError, setThreadError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: AdminBidJobFilters = { status: statusFilter };
      if (onlyMine) filters.assigned_to = 'me';
      if (query) filters.q = query;
      const data = await api.getAdminBidJobs(filters);
      setJobs(data.jobs || []);
      setTotal(data.total ?? 0);
      setSummary(data.summary ?? null);
    } catch (err) {
      setError(errorMessage(err, 'Не можеа да се вчитаат понудите.'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, onlyMine, query]);

  const fetchInbox = useCallback(async () => {
    setInboxLoading(true);
    setInboxError(null);
    try {
      const data = await api.getAdminBidInbox();
      setThreads(data.threads || []);
      setTotalUnread(data.total_unread ?? 0);
    } catch (err) {
      setInboxError(errorMessage(err, 'Не можеа да се вчитаат пораките.'));
    } finally {
      setInboxLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  useEffect(() => {
    fetchInbox();
  }, [fetchInbox]);

  const openGeneralThread = async (thread: AdminInboxThread) => {
    setOpenThread(thread);
    setThreadMessages([]);
    setThreadError(null);
    setThreadLoading(true);
    try {
      const data = await api.getAdminClientMessages(thread.user_id);
      setThreadMessages(data.messages || []);
      // Opening the thread marks it read on the server; reflect that locally.
      setThreads((prev) =>
        prev.map((t) =>
          t.user_id === thread.user_id && t.job_id === null ? { ...t, unread_count: 0 } : t
        )
      );
      setTotalUnread((n) => Math.max(0, n - thread.unread_count));
    } catch (err) {
      setThreadError(errorMessage(err, 'Не можеа да се вчитаат пораките.'));
    } finally {
      setThreadLoading(false);
    }
  };

  const sendGeneral = async (body: string) => {
    if (!openThread) return;
    // MessageThread shows the backend detail itself when this throws.
    await api.sendAdminClientMessage(openThread.user_id, body);
    const data = await api.getAdminClientMessages(openThread.user_id);
    setThreadMessages(data.messages || []);
    setThreadError(null);
    fetchInbox();
  };

  // Debounced search (the form submit applies it immediately).
  useEffect(() => {
    const t = setTimeout(() => setQuery(searchInput.trim()), 400);
    return () => clearTimeout(t);
  }, [searchInput]);

  const refreshAll = () => {
    fetchJobs();
    fetchInbox();
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Понуди (клиенти)</h1>
          <p className="text-muted-foreground mt-1">
            Сите понуди што ги подготвуваме за клиентите на услугата.
          </p>
        </div>
        <Button variant="outline" onClick={refreshAll} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Освежи
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <SummaryTile label="Наш потег" value={summary?.needs_us} tone="text-blue-600" />
        <SummaryTile
          label="Потег на клиентот"
          value={summary?.needs_client}
          tone="text-amber-600"
        />
        <SummaryTile label="Поминат рок" value={summary?.overdue} tone="text-red-600" />
        <SummaryTile
          label="Непрочитани пораки"
          value={summary?.unread_messages}
          tone="text-indigo-600"
        />
      </div>

      <div className="flex flex-col gap-3 md:flex-row md:items-end">
        <div className="w-full md:w-64">
          <Label htmlFor="bid-status-filter" className="mb-1 block text-sm">
            Статус
          </Label>
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
            <SelectTrigger id="bid-status-filter" aria-label="Статус">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {GROUP_FILTERS.map((f) => (
                <SelectItem key={f.value} value={f.value}>
                  {f.label}
                </SelectItem>
              ))}
              {ALL_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {BID_STATUS_LABELS[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <form
          className="flex flex-1 gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(searchInput.trim());
          }}
        >
          <Input
            placeholder="Пребарај по тендер, наслов, компанија или е-пошта"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            maxLength={200}
          />
          <Button type="submit" variant="secondary" disabled={loading}>
            <Search className="w-4 h-4 mr-2" />
            Барај
          </Button>
          {query && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setSearchInput('');
                setQuery('');
              }}
              aria-label="Исчисти пребарување"
            >
              <X className="w-4 h-4" />
            </Button>
          )}
        </form>
        <div className="flex items-center gap-2 pb-2">
          <Switch id="only-mine" checked={onlyMine} onCheckedChange={setOnlyMine} />
          <Label htmlFor="only-mine">Само мои</Label>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">
              Понуди {!loading && <span className="text-muted-foreground">({total})</span>}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {error && (
              <p className="mx-4 mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
                {error}
              </p>
            )}
            {loading ? (
              <div className="flex items-center justify-center py-16">
                <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" />
              </div>
            ) : jobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Inbox className="w-10 h-10 text-muted-foreground mb-3" />
                <p className="font-medium">Нема понуди за овој филтер</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b bg-muted/40 text-left text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-4 py-2 font-medium">Клиент</th>
                      <th className="px-4 py-2 font-medium">Тендер</th>
                      <th className="px-4 py-2 font-medium">Статус</th>
                      <th className="px-4 py-2 font-medium">Рок</th>
                      <th className="px-4 py-2 font-medium">Надомест</th>
                      <th className="px-4 py-2 font-medium">Задолжен</th>
                      <th className="px-4 py-2 font-medium text-right">Пораки</th>
                    </tr>
                  </thead>
                  <tbody>
                    {jobs.map((job) => {
                      const overdue = job.deadline_state === 'passed';
                      const urgent =
                        job.deadline_state === 'today' || job.deadline_state === 'soon';
                      return (
                        <tr key={job.id} className="border-b last:border-0 hover:bg-muted/30">
                          <td className="px-4 py-3 align-top">
                            <Link href={`/admin/bids/${job.id}`} className="block">
                              <span className="font-medium">
                                {job.company_name || job.user_email}
                              </span>
                              {job.company_name && (
                                <span className="block text-xs text-muted-foreground break-all">
                                  {job.user_email}
                                </span>
                              )}
                            </Link>
                          </td>
                          <td className="px-4 py-3 align-top max-w-xs">
                            <Link href={`/admin/bids/${job.id}`} className="block">
                              <span className="font-mono text-xs text-muted-foreground">
                                {job.tender_id}
                              </span>
                              <span className="block line-clamp-2 text-blue-600 hover:underline">
                                {job.tender_title || 'Без наслов'}
                              </span>
                              {job.procuring_entity && (
                                <span className="block truncate text-xs text-muted-foreground">
                                  {job.procuring_entity}
                                </span>
                              )}
                            </Link>
                          </td>
                          <td className="px-4 py-3 align-top">
                            <JobStatusBadge status={job.status} />
                          </td>
                          <td
                            className={`px-4 py-3 align-top whitespace-nowrap ${
                              overdue
                                ? 'font-semibold text-red-600'
                                : urgent
                                  ? 'font-semibold text-amber-600'
                                  : ''
                            }`}
                          >
                            {formatDay(job.closing_date)}
                            {job.days_left !== null && job.deadline_state !== null && (
                              <span className="block text-xs font-normal">
                                {overdue
                                  ? 'поминат'
                                  : job.days_left === 0
                                    ? 'денес'
                                    : `уште ${job.days_left} ден.`}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 align-top whitespace-nowrap">
                            {job.free ? 'Без надомест' : formatMkd(job.prep_fee_mkd)}
                            {job.paid_at && (
                              <span className="block text-xs text-green-700 dark:text-green-400">
                                платено
                              </span>
                            )}
                            {(job.paid_at || job.free) && (
                              <span className="block">
                                <PaidViaBadge via={paidVia(job)} />
                              </span>
                            )}
                            {!job.paid_at && job.invoice_number && (
                              <span className="block text-xs text-muted-foreground">
                                ф. {job.invoice_number}
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 align-top text-xs break-all">
                            {job.assigned_to_email || '—'}
                          </td>
                          <td className="px-4 py-3 align-top text-right">
                            {job.unread_messages > 0 ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                                <MessageSquare className="w-3 h-3" />
                                {job.unread_messages}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center justify-between text-lg">
              <span>Пораки</span>
              {totalUnread > 0 && (
                <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300">
                  {totalUnread} непрочитани
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {inboxError && <p className="text-sm text-red-600">{inboxError}</p>}
            {openThread ? (
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-medium break-words">
                      {openThread.company_name || openThread.user_email}
                    </p>
                    <p className="text-xs text-muted-foreground">Општа преписка</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setOpenThread(null)}
                    aria-label="Затвори"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
                {threadError && <p className="text-sm text-red-600">{threadError}</p>}
                {threadLoading ? (
                  <p className="py-6 text-center text-sm text-muted-foreground">Се вчитува…</p>
                ) : (
                  <MessageThread
                    messages={threadMessages}
                    viewerRole="admin"
                    onSend={sendGeneral}
                    emptyText="Нема пораки."
                  />
                )}
              </div>
            ) : inboxLoading ? (
              <p className="py-6 text-center text-sm text-muted-foreground">Се вчитува…</p>
            ) : threads.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">Нема пораки.</p>
            ) : (
              <ul className="divide-y">
                {threads.map((t) => {
                  const key = `${t.user_id}:${t.job_id ?? 'general'}`;
                  const content = (
                    <>
                      <div className="flex items-start justify-between gap-2">
                        <span
                          className={`min-w-0 break-words text-sm ${
                            t.unread_count > 0 ? 'font-semibold' : 'font-medium'
                          }`}
                        >
                          {t.company_name || t.user_email}
                        </span>
                        {t.unread_count > 0 && (
                          <span className="shrink-0 rounded-full bg-indigo-600 px-2 text-xs font-semibold text-white">
                            {t.unread_count}
                          </span>
                        )}
                      </div>
                      <p className="truncate text-xs text-muted-foreground">
                        {t.job_id
                          ? `${t.tender_id ?? ''}${t.tender_title ? ` — ${t.tender_title}` : ''}`
                          : 'Општа преписка'}
                      </p>
                      <p className="line-clamp-2 text-xs">
                        {t.last_sender_role === 'admin' ? 'Ние: ' : ''}
                        {t.last_body}
                      </p>
                      <p className="text-[11px] text-muted-foreground">
                        {formatDateTime(t.last_message_at)}
                      </p>
                    </>
                  );
                  return (
                    <li key={key} className="py-2">
                      {t.job_id ? (
                        <Link
                          href={`/admin/bids/${t.job_id}`}
                          className="block rounded-md p-2 hover:bg-muted/50"
                        >
                          {content}
                        </Link>
                      ) : (
                        <button
                          type="button"
                          onClick={() => openGeneralThread(t)}
                          className="block w-full rounded-md p-2 text-left hover:bg-muted/50"
                        >
                          {content}
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
