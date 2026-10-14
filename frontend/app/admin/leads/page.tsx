'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Building2,
  CalendarClock,
  ExternalLink,
  Inbox,
  Mail,
  Phone,
  RefreshCw,
  Target,
  Trophy,
  User,
} from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { api, type BidLead, type BidLeadStatus } from '@/lib/api';

type StatusFilter = BidLeadStatus | 'all';

const STATUS_LABELS: Record<BidLeadStatus, string> = {
  new: 'Ново',
  contacted: 'Контактирано',
  qualified: 'Квалификувано',
  client: 'Клиент (фактура платена)',
  rejected: 'Одбиено',
};

const STATUS_STYLES: Record<BidLeadStatus, string> = {
  new: 'bg-blue-100 text-blue-800 border-blue-200',
  contacted: 'bg-amber-100 text-amber-800 border-amber-200',
  qualified: 'bg-purple-100 text-purple-800 border-purple-200',
  client: 'bg-green-100 text-green-800 border-green-200',
  rejected: 'bg-gray-100 text-gray-600 border-gray-200',
};

const FILTERS: { value: StatusFilter; label: string }[] = [
  { value: 'new', label: 'Нови' },
  { value: 'contacted', label: 'Контактирани' },
  { value: 'qualified', label: 'Квалификувани' },
  { value: 'client', label: 'Клиенти' },
  { value: 'rejected', label: 'Одбиени' },
  { value: 'all', label: 'Сите' },
];

const SOURCE_LABELS: Record<string, string> = {
  usluga: 'Страница Услуга',
  tender_card: 'Картичка на тендер',
  paywall: 'Ограничен пристап',
  email: 'Е-пошта',
};

function formatDate(value: string | null | undefined, withTime = false): string {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString('mk-MK', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  });
}

function formatMkd(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `${Math.round(value).toLocaleString('mk-MK')} МКД`;
}

function daysUntil(value: string | null | undefined): number | null {
  if (!value) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  return Math.ceil((d.getTime() - Date.now()) / 86_400_000);
}

export default function AdminLeadsPage() {
  const [filter, setFilter] = useState<StatusFilter>('new');
  const [leads, setLeads] = useState<BidLead[]>([]);
  const [loading, setLoading] = useState(true);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState<Record<string, boolean>>({});

  const fetchLeads = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getBidLeads(filter === 'all' ? undefined : filter);
      const rows = data.leads || [];
      setLeads(rows);
      setNotes(Object.fromEntries(rows.map((l) => [l.id, l.admin_notes || ''])));
    } catch (error) {
      console.error('Error loading leads:', error);
      toast.error('Не можеа да се вчитаат барањата');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  const counts = useMemo(() => {
    const c: Partial<Record<BidLeadStatus, number>> = {};
    for (const l of leads) c[l.status] = (c[l.status] || 0) + 1;
    return c;
  }, [leads]);

  const handleStatusChange = async (lead: BidLead, status: BidLeadStatus) => {
    if (status === lead.status) return;
    if (
      status === 'client' &&
      !confirm(
        `Означи ја „${lead.company_name}" како клиент?\n\nОва значи дека фактурата е платена. Поврзаната сметка станува managed_client.`
      )
    ) {
      return;
    }
    setSaving((s) => ({ ...s, [lead.id]: true }));
    try {
      await api.updateBidLead(lead.id, { status });
      setLeads((prev) =>
        filter === 'all' || filter === status
          ? prev.map((l) => (l.id === lead.id ? { ...l, status } : l))
          : prev.filter((l) => l.id !== lead.id)
      );
      toast.success(
        status === 'client' && !lead.user_id
          ? 'Статусот е зачуван. Нема поврзана сметка — немаше што да се промовира.'
          : `Статус: ${STATUS_LABELS[status]}`
      );
    } catch (error) {
      console.error('Error updating lead status:', error);
      toast.error('Статусот не беше зачуван');
    } finally {
      setSaving((s) => ({ ...s, [lead.id]: false }));
    }
  };

  /** Open a bid job for the lead's tender (Phase 2): invoice and preparation start from there. */
  const handleCreateJob = async (lead: BidLead) => {
    if (!lead.user_id || !lead.tender_id) return;
    setSaving((s) => ({ ...s, [lead.id]: true }));
    try {
      const res = await api.adminCreateBidJob(lead.user_id, lead.tender_id);
      toast.success(res.created ? 'Понудата е креирана.' : 'Клиентот веќе има понуда за овој тендер.');
      window.location.href = `/admin/bids/${res.job.id}`;
    } catch (error) {
      toast.error(error instanceof Error && error.message ? error.message : 'Понудата не беше креирана');
      setSaving((s) => ({ ...s, [lead.id]: false }));
    }
  };

  const handleNotesBlur = async (lead: BidLead) => {
    const value = notes[lead.id] ?? '';
    if (value === (lead.admin_notes || '')) return;
    setSaving((s) => ({ ...s, [lead.id]: true }));
    try {
      await api.updateBidLead(lead.id, { admin_notes: value });
      setLeads((prev) => prev.map((l) => (l.id === lead.id ? { ...l, admin_notes: value } : l)));
      toast.success('Белешката е зачувана');
    } catch (error) {
      console.error('Error saving notes:', error);
      toast.error('Белешката не беше зачувана');
    } finally {
      setSaving((s) => ({ ...s, [lead.id]: false }));
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Барања за понуди</h1>
          <p className="text-muted-foreground mt-1">
            Барања од формуларот за услугата. Одговори истиот работен ден.
          </p>
        </div>
        <Button variant="outline" onClick={fetchLeads} disabled={loading}>
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          Освежи
        </Button>
      </div>

      <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">
        Статус <strong>„Клиент"</strong> значи дека фактурата е платена. Поврзаната сметка
        автоматски станува <code className="font-mono">managed_client</code> и добива пристап
        до услугата. Не го поставувај пред уплатата да е видлива на сметката.
      </div>

      <Tabs value={filter} onValueChange={(v) => setFilter(v as StatusFilter)}>
        <TabsList className="flex h-auto flex-wrap justify-start">
          {FILTERS.map((f) => (
            <TabsTrigger key={f.value} value={f.value}>
              {f.label}
              {filter === f.value && !loading && (
                <span className="ml-2 rounded-full bg-muted px-2 text-xs">{leads.length}</span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {filter === 'all' && !loading && leads.length > 0 && (
        <div className="flex flex-wrap gap-2 text-sm">
          {(Object.keys(STATUS_LABELS) as BidLeadStatus[]).map((s) => (
            <Badge key={s} variant="outline" className={STATUS_STYLES[s]}>
              {STATUS_LABELS[s]}: {counts[s] || 0}
            </Badge>
          ))}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-primary" />
        </div>
      ) : leads.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Inbox className="w-10 h-10 text-muted-foreground mb-3" />
            <p className="font-medium">Нема барања во оваа категорија</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {leads.map((lead, i) => {
            const h = lead.history || {};
            const days = daysUntil(lead.closing_date);
            return (
              <motion.div
                key={lead.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, delay: Math.min(i, 10) * 0.03 }}
              >
                <Card className={lead.status === 'new' ? 'border-blue-300' : undefined}>
                  <CardContent className="p-5">
                    <div className="grid gap-5 lg:grid-cols-[1.2fr_1.2fr_1fr]">
                      {/* Who */}
                      <div className="space-y-2 min-w-0">
                        <div className="flex items-start gap-2">
                          <Building2 className="w-4 h-4 mt-1 shrink-0 text-muted-foreground" />
                          <div className="min-w-0">
                            <p className="font-semibold leading-tight break-words">{lead.company_name}</p>
                            <p className="text-xs text-muted-foreground">
                              {formatDate(lead.created_at, true)} ·{' '}
                              {SOURCE_LABELS[lead.source || ''] || lead.source || '-'}
                            </p>
                          </div>
                        </div>
                        {lead.lead_person && (
                          <p className="flex items-center gap-2 text-sm">
                            <User className="w-4 h-4 text-muted-foreground" />
                            {lead.lead_person}
                          </p>
                        )}
                        <a
                          href={`mailto:${lead.email}`}
                          className="flex items-center gap-2 text-sm text-blue-600 hover:underline break-all"
                        >
                          <Mail className="w-4 h-4 shrink-0" />
                          {lead.email}
                        </a>
                        {lead.phone && (
                          <a
                            href={`tel:${lead.phone.replace(/\s+/g, '')}`}
                            className="flex items-center gap-2 text-sm text-blue-600 hover:underline"
                          >
                            <Phone className="w-4 h-4" />
                            {lead.phone}
                          </a>
                        )}
                        {!lead.user_id && (
                          <p className="text-xs text-amber-700">Нема поврзана корисничка сметка</p>
                        )}
                      </div>

                      {/* What */}
                      <div className="space-y-2 min-w-0 text-sm">
                        {lead.tender_id ? (
                          <div>
                            <Link
                              href={`/tenders/${encodeURIComponent(lead.tender_id)}`}
                              target="_blank"
                              className="inline-flex items-start gap-1 font-medium text-blue-600 hover:underline"
                            >
                              <span className="break-words">
                                {lead.tender_id}
                                {lead.tender_title ? ` — ${lead.tender_title}` : ''}
                              </span>
                              <ExternalLink className="w-3 h-3 mt-1 shrink-0" />
                            </Link>
                            <p className="flex items-center gap-2 mt-1 text-muted-foreground">
                              <CalendarClock className="w-4 h-4" />
                              Рок: {formatDate(lead.closing_date)}
                              {days !== null && (
                                <span
                                  className={
                                    days < 0
                                      ? 'text-gray-500'
                                      : days <= 5
                                        ? 'font-semibold text-red-600'
                                        : 'text-muted-foreground'
                                  }
                                >
                                  ({days < 0 ? 'истечен' : `уште ${days} ден.`})
                                </span>
                              )}
                            </p>
                            {lead.user_id && (days === null || days >= 0) && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="mt-2"
                                disabled={!!saving[lead.id]}
                                onClick={() => handleCreateJob(lead)}
                              >
                                Креирај понуда
                              </Button>
                            )}
                          </div>
                        ) : (
                          <p className="text-muted-foreground">Без конкретен тендер</p>
                        )}
                        {lead.wants_to_win && (
                          <p className="flex items-start gap-2">
                            <Target className="w-4 h-4 mt-0.5 shrink-0 text-muted-foreground" />
                            <span className="break-words">{lead.wants_to_win}</span>
                          </p>
                        )}
                        <div className="rounded-md bg-muted/50 p-3">
                          <p className="flex items-center gap-2 font-medium">
                            <Trophy className="w-4 h-4 text-muted-foreground" />
                            {typeof h.wins === 'number' || typeof h.bids === 'number'
                              ? `${h.wins ?? 0} победи / ${h.bids ?? 0} понуди`
                              : 'Нема историја во нашите податоци'}
                          </p>
                          {h.avg_win_mkd != null && (
                            <p className="text-xs text-muted-foreground mt-1">
                              Просечна победа: {formatMkd(h.avg_win_mkd)}
                              {h.last_bid ? ` · последна понуда ${formatDate(h.last_bid)}` : ''}
                            </p>
                          )}
                          {h.top_buyers && h.top_buyers.length > 0 && (
                            <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
                              {h.top_buyers.map((b) => (
                                <li key={b.buyer} className="truncate">
                                  {b.buyer} ({b.wins})
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      </div>

                      {/* Action */}
                      <div className="space-y-3">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className={STATUS_STYLES[lead.status]}>
                            {STATUS_LABELS[lead.status]}
                          </Badge>
                          {saving[lead.id] && (
                            <span className="text-xs text-muted-foreground">Се зачувува...</span>
                          )}
                        </div>
                        <Select
                          value={lead.status}
                          onValueChange={(v) => handleStatusChange(lead, v as BidLeadStatus)}
                          disabled={saving[lead.id]}
                        >
                          <SelectTrigger aria-label="Статус">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {(Object.keys(STATUS_LABELS) as BidLeadStatus[]).map((s) => (
                              <SelectItem key={s} value={s}>
                                {STATUS_LABELS[s]}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <Textarea
                          placeholder="Интерни белешки (се зачувуваат кога ќе кликнете надвор)"
                          value={notes[lead.id] ?? ''}
                          onChange={(e) => setNotes((n) => ({ ...n, [lead.id]: e.target.value }))}
                          onBlur={() => handleNotesBlur(lead)}
                          rows={4}
                          maxLength={5000}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
