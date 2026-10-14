'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ExternalLink, Inbox, RefreshCw, Trophy } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api } from '@/lib/api';
import { tenderUrl } from '@/lib/utils';
import {
  formatMkd,
  type AdminWinsResponse,
  type ClientWin,
  type ClientWinStatus,
  type ConfirmWinBody,
} from '@/lib/bid-service-types';

const TABS: { value: ClientWinStatus; label: string }[] = [
  { value: 'suspected', label: 'За проверка' },
  { value: 'confirmed', label: 'Потврдени' },
  { value: 'invoiced', label: 'Фактурирани' },
  { value: 'dismissed', label: 'Отфрлени' },
];

const VALUE_SOURCE_LABELS: Record<string, string> = {
  bid: 'наша понуда',
  actual: 'вредност на договор',
  estimated: 'проценета вредност',
  admin: 'внесено рачно',
};

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof Error && err.message ? err.message : fallback;
}

function formatDay(value: string | null | undefined): string {
  if (!value) return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (m) {
    const d = new Date(value);
    if (!Number.isNaN(d.getTime()) && value.length > 10) {
      return d.toLocaleDateString('mk-MK', {
        timeZone: 'Europe/Skopje',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      });
    }
    return `${m[3]}.${m[2]}.${m[1]}`;
  }
  return value;
}

/** Mirrors backend services/client_wins.compute_success_fee: no cap, prep fee credited. */
function previewFee(firstYear: number, pct: number | null, credit: number): number {
  if (!Number.isFinite(firstYear) || pct == null) return 0;
  return Math.max(Math.round((firstYear * pct) / 100) - (credit || 0), 0);
}

function SummaryTile({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className={`mt-1 text-2xl font-bold ${tone}`}>{value}</p>
      </CardContent>
    </Card>
  );
}

function ConfirmForm({
  win,
  busy,
  onConfirm,
  onCancel,
}: {
  win: ClientWin;
  busy: boolean;
  onConfirm: (body: ConfirmWinBody) => void;
  onCancel: () => void;
}) {
  // An estimate-based value is never billed without a human check (no cap on the fee):
  // the admin must enter the real first-year value or the fee.
  const estimated = win.value_source === 'estimated';
  const [firstYear, setFirstYear] = useState(
    win.first_year_value_mkd != null && !estimated ? String(win.first_year_value_mkd) : ''
  );
  const [fee, setFee] = useState(win.success_fee_mkd != null ? String(win.success_fee_mkd) : '');
  const [feeTouched, setFeeTouched] = useState(false);
  const [notes, setNotes] = useState(win.notes ?? '');
  const [stripeDraft, setStripeDraft] = useState(win.has_card);
  const [error, setError] = useState<string | null>(null);

  const computed = previewFee(Number(firstYear), win.success_fee_pct, win.prep_fee_credit_mkd);

  // Until the admin overrides the fee, keep it in step with the first-year value.
  useEffect(() => {
    if (!feeTouched && firstYear !== '') setFee(String(computed));
  }, [computed, feeTouched, firstYear]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const body: ConfirmWinBody = { create_stripe_invoice: stripeDraft };
    if (estimated && firstYear === '' && !feeTouched) {
      setError('Вредноста е проценета. Внесете ја вистинската вредност за првата година или надоместот.');
      return;
    }
    if (win.success_fee_pct == null && !feeTouched) {
      setError('Процентот не е поставен. Внесете го надоместот директно.');
      return;
    }
    const fy = Number(firstYear);
    if (firstYear !== '' && fy !== win.first_year_value_mkd) {
      if (!Number.isFinite(fy) || fy < 0) {
        setError('Внесете валидна вредност за првата година.');
        return;
      }
      body.first_year_value_mkd = fy;
    }
    if (feeTouched) {
      const f = Number(fee);
      if (!Number.isInteger(f) || f < 0) {
        setError('Надоместот мора да е цел број во денари.');
        return;
      }
      body.success_fee_mkd = f;
    }
    if (notes.trim() !== (win.notes ?? '')) body.notes = notes.trim();
    if (
      !confirm(
        'Потврди ја победата? Клиентот добива известување дека надоместот за успех ќе се наплати најрано за седум дена.'
      )
    )
      return;
    onConfirm(body);
  };

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-md border bg-muted/30 p-3 text-sm">
      {estimated && (
        <p className="text-xs font-medium text-amber-700 dark:text-amber-400">
          Вредноста е проценета од тендерот ({formatMkd(win.first_year_value_mkd)} за првата година), не од
          понудата или договорот. Внесете ја вистинската вредност.
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label htmlFor={`fy-${win.id}`} className="text-xs">
            Вредност за првата година (МКД)
          </Label>
          <Input
            id={`fy-${win.id}`}
            type="number"
            min={0}
            step="0.01"
            value={firstYear}
            onChange={(e) => setFirstYear(e.target.value)}
            disabled={busy}
          />
        </div>
        <div>
          <Label htmlFor={`fee-${win.id}`} className="text-xs">
            Надомест за успех (МКД)
          </Label>
          <Input
            id={`fee-${win.id}`}
            type="number"
            min={0}
            step={1}
            value={fee}
            onChange={(e) => {
              setFee(e.target.value);
              setFeeTouched(true);
            }}
            disabled={busy}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Пресметано: {win.success_fee_pct ?? '—'}% од првата година
            {win.prep_fee_credit_mkd > 0 ? `, минус ${formatMkd(win.prep_fee_credit_mkd)} подготовка` : ''} ={' '}
            {formatMkd(computed)}
            {feeTouched && (
              <button
                type="button"
                className="ml-2 text-blue-600 hover:underline"
                onClick={() => {
                  setFeeTouched(false);
                  setFee(String(computed));
                }}
              >
                врати пресметка
              </button>
            )}
          </p>
        </div>
      </div>
      <div>
        <Label htmlFor={`notes-${win.id}`} className="text-xs">
          Белешка (интерна)
        </Label>
        <Textarea
          id={`notes-${win.id}`}
          rows={2}
          maxLength={2000}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={busy}
        />
      </div>
      <div className="flex items-center gap-2">
        <Switch
          id={`stripe-${win.id}`}
          checked={stripeDraft}
          onCheckedChange={setStripeDraft}
          disabled={busy || !win.has_card}
        />
        <Label htmlFor={`stripe-${win.id}`}>
          {win.has_card
            ? 'Креирај Stripe нацрт-фактура (не се наплаќа автоматски)'
            : 'Нема картичка: издадете фактура и означете ја како фактурирана'}
        </Label>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={busy}>
          {busy ? 'Се потврдува…' : 'Потврди победа'}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
          Откажи
        </Button>
      </div>
    </form>
  );
}

export default function AdminWinsPage() {
  const [tab, setTab] = useState<ClientWinStatus>('suspected');
  const [data, setData] = useState<AdminWinsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.adminListWins(tab);
      setData(res);
    } catch (err) {
      setError(errorMessage(err, 'Победите не можат да се вчитаат.'));
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (key: string, fn: () => Promise<unknown>, success?: string) => {
    setBusy(key);
    setError(null);
    try {
      await fn();
      if (success) toast.success(success);
      setConfirming(null);
      await load();
    } catch (err) {
      const msg = errorMessage(err, 'Акцијата не успеа.');
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(null);
    }
  };

  const confirmWin = (win: ClientWin, body: ConfirmWinBody) =>
    run(`confirm-${win.id}`, async () => {
      const res = await api.adminConfirmWin(win.id, body);
      toast.success('Победата е потврдена.');
      if (res.notice?.message) {
        if (res.notice.sent) toast.success(res.notice.message);
        else toast.warning(res.notice.message, { duration: 15000 });
      }
      if (res.invoice?.message) {
        if (res.invoice.created) toast.success(res.invoice.message);
        else toast.message(res.invoice.message);
      }
    });

  const summary = data?.summary;
  const wins = data?.wins ?? [];

  return (
    <div className="container mx-auto space-y-6 p-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-3xl font-bold">Победи на клиенти</h1>
          <p className="mt-1 text-muted-foreground">
            Можни победи пронајдени во податоците за доделување. Потврдете ја секоја рачно; наплатата од
            картичка ја праќате од Stripe по истекот на седумдневниот рок.
          </p>
        </div>
        <Button variant="outline" onClick={load} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          Освежи
        </Button>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <SummaryTile label="За проверка" value={String(summary?.suspected ?? '—')} tone="text-amber-600" />
        <SummaryTile label="Потврдени" value={String(summary?.confirmed ?? '—')} tone="text-blue-600" />
        <SummaryTile
          label="Надомест во проверка"
          value={summary ? formatMkd(summary.pipeline_fee_mkd) : '—'}
          tone="text-slate-700 dark:text-slate-200"
        />
        <SummaryTile
          label="Потврден надомест"
          value={summary ? formatMkd(summary.confirmed_fee_mkd) : '—'}
          tone="text-green-600"
        />
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as ClientWinStatus)}>
        <TabsList>
          {TABS.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              {t.label}
              {summary && (
                <span className="ml-1 text-xs text-muted-foreground">({summary[t.value] ?? 0})</span>
              )}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {error && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="h-10 w-10 animate-spin rounded-full border-b-2 border-primary" />
        </div>
      ) : wins.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Inbox className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="font-medium">Нема победи во оваа група</p>
        </div>
      ) : (
        <div className="space-y-3">
          {wins.map((w) => {
            const isBusy = busy !== null;
            return (
              <Card key={w.id}>
                <CardContent className="space-y-2 p-4 text-sm">
                  <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                    <div className="min-w-0 space-y-1">
                      <p className="font-semibold break-words">
                        <Trophy className="mr-1 inline h-4 w-4 text-amber-500" />
                        {w.company_name || w.email}
                        <span className="ml-2 text-xs font-normal text-muted-foreground break-all">{w.email}</span>
                      </p>
                      <Link
                        href={tenderUrl(w.tender_id)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-start gap-1 text-blue-600 hover:underline"
                      >
                        <span className="font-mono text-xs text-muted-foreground">{w.tender_id}</span>
                        <span className="break-words">{w.tender_title || 'Без наслов'}</span>
                        <ExternalLink className="mt-0.5 h-3 w-3 shrink-0" />
                      </Link>
                      {w.procuring_entity && <p className="text-xs text-muted-foreground">{w.procuring_entity}</p>}
                      {w.job_id && (
                        <Link href={`/admin/bids/${w.job_id}`} className="text-xs text-blue-600 hover:underline">
                          Отвори ја понудата
                        </Link>
                      )}
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="text-lg font-bold">{formatMkd(w.success_fee_mkd)}</p>
                      <p className="text-xs text-muted-foreground">
                        {w.success_fee_pct ?? '—'}% од {formatMkd(w.first_year_value_mkd)} (прва година)
                      </p>
                    </div>
                  </div>

                  <div className="grid gap-1 text-xs text-muted-foreground md:grid-cols-3">
                    <p>
                      Победник во податоците: {w.matched_name || '—'}
                      {w.match_score != null ? ` (совпаѓање ${Math.round(Number(w.match_score) * 100)}%)` : ''}
                    </p>
                    <p>
                      Вредност: {formatMkd(w.contract_value_mkd)}
                      {w.value_source ? ` (${VALUE_SOURCE_LABELS[w.value_source] ?? w.value_source})` : ''}
                      {w.contract_months ? `, ${w.contract_months} мес.` : ''}
                    </p>
                    <p>
                      Одбиена подготовка: {formatMkd(w.prep_fee_credit_mkd)} · Картичка:{' '}
                      {w.has_card ? 'да' : 'не'}
                    </p>
                    <p>Пронајдено: {formatDay(w.detected_at)}</p>
                    {w.confirmed_at && <p>Потврдено: {formatDay(w.confirmed_at)}</p>}
                    {w.notice_sent_at && <p>Известување: {formatDay(w.notice_sent_at)}</p>}
                    {w.charge_not_before && (
                      <p className="font-medium text-amber-700 dark:text-amber-400">
                        Наплата најрано: {formatDay(w.charge_not_before)}
                      </p>
                    )}
                    {w.status === 'confirmed' && !w.notice_sent_at && (w.success_fee_mkd ?? 0) > 0 && (
                      <p className="font-medium text-red-600 dark:text-red-400">
                        Известувањето не е испратено: не наплаќајте.
                      </p>
                    )}
                    {w.stripe_invoice_id && <p className="break-all">Stripe: {w.stripe_invoice_id}</p>}
                    {w.invoice_number && <p>Фактура: {w.invoice_number}</p>}
                    {w.invoiced_at && <p>Фактурирано: {formatDay(w.invoiced_at)}</p>}
                  </div>
                  {w.notes && <p className="whitespace-pre-wrap text-xs">Белешка: {w.notes}</p>}

                  <div className="flex flex-wrap gap-2 pt-1">
                    {w.status === 'suspected' && confirming !== w.id && (
                      <Button size="sm" disabled={isBusy} onClick={() => setConfirming(w.id)}>
                        Потврди
                      </Button>
                    )}
                    {w.status === 'suspected' && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={isBusy}
                        onClick={() => {
                          const notes = prompt('Причина за отфрлање (опционално):') ?? undefined;
                          if (notes === undefined) return;
                          run(
                            `dismiss-${w.id}`,
                            () => api.adminDismissWin(w.id, notes.trim() || undefined),
                            'Отфрлено.'
                          );
                        }}
                      >
                        Отфрли
                      </Button>
                    )}
                    {w.status === 'confirmed' && !w.notice_sent_at && w.job_id && (w.success_fee_mkd ?? 0) > 0 && (
                      <Button
                        size="sm"
                        disabled={isBusy}
                        onClick={() =>
                          run(`notice-${w.id}`, async () => {
                            const res = await api.adminSendWinNotice(w.id);
                            if (res.notice.sent) toast.success(res.notice.message);
                            else throw new Error(res.notice.message);
                          })
                        }
                      >
                        Испрати известување
                      </Button>
                    )}
                    {w.status === 'confirmed' && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={isBusy}
                        onClick={() => {
                          const num = prompt('Број на фактура (опционално):', w.invoice_number ?? '');
                          if (num === null) return;
                          run(
                            `invoiced-${w.id}`,
                            () => api.adminMarkWinInvoiced(w.id, num.trim() || undefined),
                            'Означено како фактурирано.'
                          );
                        }}
                      >
                        Означи фактурирано
                      </Button>
                    )}
                  </div>

                  {w.status === 'suspected' && confirming === w.id && (
                    <ConfirmForm
                      win={w}
                      busy={busy === `confirm-${w.id}`}
                      onCancel={() => setConfirming(null)}
                      onConfirm={(body) => confirmWin(w, body)}
                    />
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
