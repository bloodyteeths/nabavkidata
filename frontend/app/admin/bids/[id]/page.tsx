'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Download, ExternalLink, Loader2, RefreshCw, Trash2, Upload } from 'lucide-react';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import JobStatusBadge from '@/components/bid-service/JobStatusBadge';
import DeadlineWarning from '@/components/bid-service/DeadlineWarning';
import MessageThread from '@/components/bid-service/MessageThread';
import { api } from '@/lib/api';
import { tenderUrl } from '@/lib/utils';
import {
  BID_FILE_ACCEPT,
  BID_FILE_KIND_LABELS,
  BID_FILE_MAX_BYTES,
  CLIENT_DOCUMENT_CATEGORY_LABELS,
  FILE_APPROVAL_LABELS,
  PRE_SUBMITTED_STATUSES,
  SUCCESS_FEE_NOT_AUTHORISED,
  formatMkd,
  type AdminClientInfo,
  type AdminBidJobDetailResponse,
  type AdminTeamMember,
  type BidFileKind,
  type BidJobStatus,
  type BidOutcome,
} from '@/lib/bid-service-types';

const KIND_OPTIONS = Object.keys(BID_FILE_KIND_LABELS) as BidFileKind[];

const OUTCOME_LABELS: Record<BidOutcome, string> = {
  won: 'Добиена',
  lost: 'Не е добиена',
  cancelled: 'Постапката е поништена',
};

const PUBLISHABLE: BidJobStatus[] = ['preparing', 'ready', 'changes_requested', 'approved'];
const SUBMITTABLE: BidJobStatus[] = ['ready', 'changes_requested', 'approved'];
const TERMINAL: BidJobStatus[] = ['won', 'lost', 'cancelled'];

const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  free: 'Регистрирана сметка',
  prospect: 'Потенцијален клиент',
  managed_client: 'Клиент на услугата',
};

const PAID_VIA_LABELS: Record<string, string> = {
  stripe: 'со картичка',
  invoice: 'по фактура',
  free: 'без надомест',
};

const MISSING_LABELS: Record<string, string> = {
  terms: 'прифатени тековни услови',
  card: 'зачувана картичка или писмено овластување',
};

/** What the publish gate still needs, derived from the client row (fallback when the 409 detail is not exposed). */
function missingAuthorisation(client: AdminClientInfo, currentVersion: string | null): string[] {
  const missing: string[] = [];
  const termsOk =
    !!client.terms_agreed_at && (!currentVersion || client.agreement_version === currentVersion);
  if (!termsOk) missing.push('terms');
  if (!client.has_card) missing.push('card');
  return missing;
}

/** The 409 detail object when lib/api.ts exposes it on the error; null otherwise. */
function successFeeBlock(err: unknown): { missing: string[]; message: string | null } | null {
  const e = err as { status?: number; detail?: unknown; message?: string } | null;
  if (!e) return null;
  const d = e.detail as { code?: string; missing?: unknown; message?: string } | undefined;
  if (d && typeof d === 'object' && d.code === SUCCESS_FEE_NOT_AUTHORISED) {
    return {
      missing: Array.isArray(d.missing) ? d.missing.map(String) : [],
      message: d.message ?? null,
    };
  }
  if (e.status === 409 && (e.message === '[object Object]' || e.message?.includes(SUCCESS_FEE_NOT_AUTHORISED))) {
    return { missing: [], message: null };
  }
  return null;
}

const ACTOR_LABELS: Record<string, string> = {
  client: 'клиент',
  admin: 'админ',
  system: 'систем',
};

// Keys are the audit `event` values written by backend/api/bid_jobs.py.
const EVENT_LABELS: Record<string, string> = {
  requested: 'Барањето е примено',
  invoice_issued: 'Издадена фактура',
  invoice_file_uploaded: 'Прикачена фактура (PDF)',
  paid: 'Евидентирана уплата',
  invoice_requested: 'Клиентот побара фактура',
  duplicate_payment: 'Двојна уплата (потребен поврат)',
  paid_while_cancelled: 'Уплата по откажување',
  payment_amount_mismatch: 'Износот на уплатата не се совпаѓа',
  success_fee_authorised: 'Овластување за надомест за успех',
  marked_free: 'Без надомест',
  preparing: 'Подготовка',
  published: 'Објавено на клиентот',
  changes_requested: 'Побарани измени',
  approved: 'Одобрено',
  submitted: 'Поднесено',
  won: 'Добиена',
  lost: 'Не е добиена',
  cancelled: 'Откажано',
  fee_updated: 'Променет надомест',
  file_uploaded: 'Прикачен документ',
  file_deleted: 'Избришан документ',
  file_approved: 'Одобрен документ',
  file_changes_requested: 'Побарани измени на документ',
  assigned: 'Задолжување',
  notes_updated: 'Белешки',
  notify_failed: 'Е-поштата не е испратена',
};

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

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function todayIso(): string {
  // Europe/Skopje calendar date in YYYY-MM-DD (sv-SE locale formats as ISO).
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Skopje' });
}

function phaseBoxClass(whoseMove: string): string {
  if (whoseMove === 'client') {
    return 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200';
  }
  if (whoseMove === 'us') {
    return 'border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200';
  }
  return 'border-slate-200 bg-slate-50 text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200';
}

export default function AdminBidJobPage() {
  const params = useParams<{ id: string }>();
  const jobId = params?.id ?? '';

  const [data, setData] = useState<AdminBidJobDetailResponse | null>(null);
  const [team, setTeam] = useState<AdminTeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  // Payment form
  const [invoiceFee, setInvoiceFee] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('');
  const [paidDate, setPaidDate] = useState(todayIso());

  // Upload form
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadKind, setUploadKind] = useState<BidFileKind>('tehnicka');
  const [uploadTitle, setUploadTitle] = useState('');

  // Outcome / cancel
  const [outcome, setOutcome] = useState<BidOutcome>('won');
  const [cancelReason, setCancelReason] = useState('');

  // Notes
  const [notes, setNotes] = useState('');

  // Client settings
  const [freeDrafting, setFreeDrafting] = useState(false);
  const [clientFee, setClientFee] = useState('');
  const [clientPct, setClientPct] = useState('');
  const [clientCompany, setClientCompany] = useState('');
  const [newTenderId, setNewTenderId] = useState('');
  const [authRef, setAuthRef] = useState('');
  const [publishMissing, setPublishMissing] = useState<string[] | null>(null);

  const load = useCallback(
    async (initial = false) => {
      if (!jobId) return;
      if (initial) setLoading(true);
      try {
        const res = await api.getAdminBidJob(jobId);
        setData(res);
        setLoadError(null);
        setInvoiceFee(res.job.prep_fee_mkd != null ? String(res.job.prep_fee_mkd) : '');
        setInvoiceNumber(res.job.invoice_number ?? '');
        setNotes(res.job.admin_notes ?? '');
        setFreeDrafting(res.client.free_drafting);
        setClientFee(String(res.client.prep_fee_mkd));
        setClientPct(String(res.client.success_fee_pct));
        setClientCompany(res.client.company_name ?? '');
      } catch (err) {
        setLoadError(errorMessage(err, 'Понудата не може да се вчита.'));
      } finally {
        if (initial) setLoading(false);
      }
    },
    [jobId]
  );

  useEffect(() => {
    load(true);
  }, [load]);

  useEffect(() => {
    api
      .getAdminBidTeam()
      .then((res) => setTeam(res.admins || []))
      .catch(() => setTeam([]));
  }, []);

  /** Run one action: disable its button, show backend detail on error, reload after. */
  const run = async (key: string, fn: () => Promise<unknown>, success?: string) => {
    setBusy(key);
    setActionError(null);
    try {
      await fn();
      if (success) toast.success(success);
      await load();
    } catch (err) {
      const msg = errorMessage(err, 'Акцијата не успеа.');
      setActionError(msg);
      toast.error(msg);
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Се вчитува…
      </div>
    );
  }

  if (!data) {
    return (
      <div className="container mx-auto p-6 space-y-4">
        <Link href="/admin/bids" className="inline-flex items-center text-sm text-blue-600 hover:underline">
          <ArrowLeft className="w-4 h-4 mr-1" />
          Назад кон понудите
        </Link>
        <div className="space-y-3 rounded-md border border-red-200 p-4 dark:border-red-900">
          <p className="font-semibold text-red-700 dark:text-red-300">Грешка</p>
          <p className="text-sm text-red-600 dark:text-red-400">{loadError || 'Понудата не е пронајдена.'}</p>
          <Button variant="outline" size="sm" onClick={() => load(true)}>
            Обиди се повторно
          </Button>
        </div>
      </div>
    );
  }

  const { job, tender, files, messages, client, client_documents, events, payment } = data;
  const isBusy = busy !== null;
  const canInvoice = job.status === 'requested' || job.status === 'payment_required';
  // Backend mark_job_paid accepts requested or payment_required (card window or invoice).
  const canMarkPaid = canInvoice && !job.free && !job.paid_at;
  const canMarkFree = canInvoice;
  const canUpload = !TERMINAL.includes(job.status);
  const publishBlocked = !!job.publish_blocked_reason;
  const canPublish = files.length > 0 && PUBLISHABLE.includes(job.status) && !publishBlocked;
  const sfAuthorised = !!client.success_fee_authorised_at;
  const canAdminSubmit = SUBMITTABLE.includes(job.status) && !!job.published_at;
  const canSetOutcome =
    job.status === 'submitted' ||
    job.status === 'won' ||
    job.status === 'lost' ||
    (job.status === 'cancelled' && job.outcome !== null);
  const canCancel = PRE_SUBMITTED_STATUSES.includes(job.status);
  // Once invoiced, a new amount needs a new invoice (POST /invoice), not a silent edit.
  const feeEditable = !job.paid_at && !job.invoice_number;

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      setActionError('Изберете датотека.');
      return;
    }
    if (uploadFile.size > BID_FILE_MAX_BYTES) {
      setActionError('Датотеката е поголема од 25 MB.');
      return;
    }
    const file = uploadFile;
    await run(
      'upload',
      async () => {
        await api.uploadBidJobFile(job.id, file, uploadKind, uploadTitle.trim() || undefined);
        setUploadFile(null);
        setUploadTitle('');
        if (fileInputRef.current) fileInputRef.current.value = '';
      },
      'Документот е прикачен.'
    );
  };

  const handleInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    const fee = Number(invoiceFee);
    if (!Number.isInteger(fee) || fee < 1 || fee > 10_000_000) {
      setActionError('Внесете валиден износ во денари (цел број).');
      return;
    }
    if (!invoiceNumber.trim()) {
      setActionError('Внесете број на фактура.');
      return;
    }
    await run(
      'invoice',
      () => api.issueBidInvoice(job.id, { prep_fee_mkd: fee, invoice_number: invoiceNumber.trim() }),
      'Фактурата е евидентирана.'
    );
  };

  const handleSaveClient = async (e: React.FormEvent) => {
    e.preventDefault();
    const fee = Number(clientFee);
    const pct = Number(clientPct);
    if (!Number.isInteger(fee) || fee < 0 || fee > 10_000_000) {
      setActionError('Надоместот мора да е цел број од 0 до 10.000.000.');
      return;
    }
    if (!Number.isFinite(pct) || pct < 0 || pct > 100) {
      setActionError('Процентот мора да е од 0 до 100.');
      return;
    }
    if (freeDrafting && !client.free_drafting) {
      if (
        !confirm(
          'Подготовка без надомест за овој клиент (одобрено од админ)?\n\nНовите барања ќе одат директно во подготовка, без фактура. Сметката станува клиент на услугата.'
        )
      ) {
        return;
      }
    }
    await run(
      'client',
      async () => {
        const res = await api.updateBidClient(client.user_id, {
          free_drafting: freeDrafting,
          prep_fee_mkd: fee,
          success_fee_pct: pct,
          company_name: clientCompany.trim(),
        });
        if (res.account_promoted) toast.success('Сметката стана клиент на услугата.');
      },
      'Поставките за клиентот се зачувани.'
    );
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between gap-4">
        <Link href="/admin/bids" className="inline-flex items-center text-sm text-blue-600 hover:underline">
          <ArrowLeft className="w-4 h-4 mr-1" />
          Назад кон понудите
        </Link>
        <Button variant="outline" size="sm" onClick={() => load()} disabled={isBusy}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Освежи
        </Button>
      </div>

      {/* Header */}
      <Card>
        <CardContent className="p-5 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <JobStatusBadge status={job.status} />
            <span className="font-mono text-xs text-muted-foreground">{job.tender_id}</span>
            {job.free && (
              <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-800 dark:bg-green-950 dark:text-green-300">
                Без надомест
              </span>
            )}
            {job.reopen_count > 0 && (
              <span className="text-xs text-muted-foreground">повторно отворена {job.reopen_count}x</span>
            )}
          </div>
          <Link
            href={tenderUrl(job.tender_id)}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-start gap-1 text-xl font-semibold text-blue-600 hover:underline"
          >
            <span className="break-words">{tender.title || job.tender_title || job.tender_id}</span>
            <ExternalLink className="w-4 h-4 mt-1.5 shrink-0" />
          </Link>
          <div className="grid gap-1 text-sm text-muted-foreground md:grid-cols-2">
            <p>Договорен орган: {tender.procuring_entity || job.procuring_entity || '—'}</p>
            <p>Рок за поднесување: {formatDay(tender.closing_date ?? job.closing_date)}</p>
            <p>Проценета вредност: {formatMkd(tender.estimated_value_mkd ?? job.estimated_value_mkd)}</p>
            <p>
              Клиент: {job.company_name || '—'} ({job.user_email})
            </p>
            <p>Создадено: {formatDateTime(job.created_at)}</p>
            <p>Објавено: {job.publish_count}x{job.published_at ? `, последно ${formatDateTime(job.published_at)}` : ''}</p>
          </div>
          <div className={`rounded-md border px-3 py-2 text-sm ${phaseBoxClass(job.whose_move)}`}>
            {job.phase_text}
          </div>
          <DeadlineWarning
            closingDate={job.closing_date}
            deadlineState={job.deadline_state}
            daysLeft={job.days_left}
          />
          {job.client_note && (
            <div className="rounded-md bg-muted/50 px-3 py-2 text-sm">
              <span className="font-medium">Белешка од клиентот:</span> {job.client_note}
            </div>
          )}
          {job.cancelled_at && (
            <p className="text-sm text-muted-foreground">
              Откажано {formatDateTime(job.cancelled_at)}
              {job.cancelled_by ? ` (${ACTOR_LABELS[job.cancelled_by] ?? job.cancelled_by})` : ''}
              {job.cancel_reason ? `: ${job.cancel_reason}` : ''}
            </p>
          )}
        </CardContent>
      </Card>

      {actionError && (
        <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {actionError}
        </p>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Payment */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Плаќање</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="grid gap-1">
              <p>
                Надомест за подготовка:{' '}
                <strong>{payment.free ? 'без надомест' : formatMkd(payment.prep_fee_mkd)}</strong>
              </p>
              <p>
                При доделена набавка:{' '}
                <strong>{payment.success_fee_pct != null ? `${payment.success_fee_pct}%` : '—'}</strong>
              </p>
              <p>
                Фактура: {payment.invoice_number || '—'}
                {payment.invoice_issued_at ? `, издадена ${formatDateTime(payment.invoice_issued_at)}` : ''}
              </p>
              <p>
                Уплатено: {payment.paid_at ? formatDateTime(payment.paid_at) : '—'}
                {payment.paid_at && job.paid_via ? ` (${PAID_VIA_LABELS[job.paid_via] ?? job.paid_via})` : ''}
              </p>
              {payment.invoice_requested_at && !payment.paid_at && (
                <p className="font-medium text-sky-700 dark:text-sky-400">
                  Клиентот побара фактура на {formatDateTime(payment.invoice_requested_at)}.
                </p>
              )}
              {payment.required && (
                <p className="font-medium text-amber-700 dark:text-amber-400">
                  Чекаме уплата{payment.can_pay_card ? ' (клиентот може да плати и со картичка)' : ''}.
                </p>
              )}
              {payment.success_fee && (
                <p>
                  Надомест за успех:{' '}
                  <strong>{formatMkd(payment.success_fee.fee_mkd)}</strong>
                  {payment.success_fee.charge_not_before
                    ? `, наплата најрано ${formatDay(payment.success_fee.charge_not_before)}`
                    : ''}
                  {payment.success_fee.stripe ? ' (Stripe нацрт-фактура)' : ''}
                </p>
              )}
            </div>

            <form onSubmit={handleInvoice} className="space-y-2 rounded-md border p-3">
              <p className="font-medium">Издади фактура</p>
              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <Label htmlFor="invoice-fee" className="text-xs">
                    Износ (МКД, без ДДВ)
                  </Label>
                  <Input
                    id="invoice-fee"
                    type="number"
                    min={1}
                    max={10000000}
                    step={1}
                    value={invoiceFee}
                    onChange={(e) => setInvoiceFee(e.target.value)}
                    disabled={!canInvoice || isBusy}
                  />
                </div>
                <div>
                  <Label htmlFor="invoice-number" className="text-xs">
                    Број на фактура
                  </Label>
                  <Input
                    id="invoice-number"
                    value={invoiceNumber}
                    maxLength={50}
                    onChange={(e) => setInvoiceNumber(e.target.value)}
                    disabled={!canInvoice || isBusy}
                  />
                </div>
              </div>
              <Button type="submit" size="sm" disabled={!canInvoice || isBusy}>
                {busy === 'invoice' ? 'Се зачувува…' : job.invoice_number ? 'Ажурирај фактура' : 'Издади фактура'}
              </Button>
              {job.invoice_number && (
                <p className="text-xs text-muted-foreground">
                  Клиентот добива нова е-пошта само кога се менува бројот на фактурата. За друга промена пишете
                  му порака.
                </p>
              )}
            </form>

            <div className="space-y-2 rounded-md border p-3">
              <p className="font-medium">Фактура (PDF) за клиентот</p>
              {payment.invoice_file_name ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="break-all">{payment.invoice_file_name}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={isBusy}
                    aria-label="Преземи фактура"
                    onClick={() =>
                      run('invoice-dl', () =>
                        api.adminDownloadBidInvoice(job.id, payment.invoice_file_name ?? 'faktura.pdf')
                      )
                    }
                  >
                    <Download className="w-4 h-4" />
                  </Button>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  {job.invoice_number
                    ? 'Сè уште не е прикачена. Клиентот ја презема од порталот.'
                    : 'Прво издадете фактура.'}
                </p>
              )}
              <Input
                type="file"
                accept=".pdf"
                disabled={!job.invoice_number || isBusy}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  e.target.value = '';
                  if (!f) return;
                  if (f.size > BID_FILE_MAX_BYTES) {
                    setActionError('Датотеката е поголема од 25 MB.');
                    return;
                  }
                  run('invoice-file', () => api.uploadBidInvoiceFile(job.id, f), 'Фактурата е прикачена.');
                }}
              />
            </div>

            <div className="flex flex-wrap items-end gap-2 rounded-md border p-3">
              <div>
                <Label htmlFor="paid-date" className="text-xs">
                  Датум на уплата
                </Label>
                <Input
                  id="paid-date"
                  type="date"
                  value={paidDate}
                  max={todayIso()}
                  onChange={(e) => setPaidDate(e.target.value)}
                  disabled={!canMarkPaid || isBusy}
                />
              </div>
              <Button
                size="sm"
                disabled={!canMarkPaid || isBusy}
                onClick={() => {
                  if (!confirm('Означи ја понудата како платена (по фактура)? Подготовката започнува и клиентот добива известување.')) return;
                  run(
                    'paid',
                    async () => {
                      const res = await api.markBidJobPaid(job.id, paidDate || undefined);
                      if (res.account_promoted) toast.success('Сметката стана клиент на услугата.');
                    },
                    'Означено како платено.'
                  );
                }}
              >
                {busy === 'paid' ? 'Се зачувува…' : 'Означи платено'}
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!canMarkFree || isBusy}
                onClick={() => {
                  if (!confirm('Подготовка без надомест за оваа понуда? Подготовката започнува веднаш.')) return;
                  run(
                    'free',
                    async () => {
                      const res = await api.markBidJobFree(job.id);
                      if (res.account_promoted) toast.success('Сметката стана клиент на услугата.');
                    },
                    'Понудата е означена без надомест.'
                  );
                }}
              >
                {busy === 'free' ? 'Се зачувува…' : 'Без надомест'}
              </Button>
            </div>

            {feeEditable && canInvoice && !job.free && (
              <Button
                size="sm"
                variant="ghost"
                disabled={isBusy || invoiceFee === String(job.prep_fee_mkd ?? '')}
                onClick={() => {
                  const fee = Number(invoiceFee);
                  if (!Number.isInteger(fee) || fee < 0 || fee > 10_000_000) {
                    setActionError('Внесете валиден износ во денари (цел број).');
                    return;
                  }
                  run('fee', () => api.updateAdminBidJob(job.id, { prep_fee_mkd: fee }), 'Надоместот е зачуван.');
                }}
              >
                Зачувај само надомест
              </Button>
            )}
          </CardContent>
        </Card>

        {/* Outcome, status, assignment */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Исход и статус</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                disabled={!canAdminSubmit || isBusy}
                onClick={() => {
                  if (!confirm('Означи ја понудата како поднесена на е-набавки?')) return;
                  run('submitted', () => api.adminMarkBidJobSubmitted(job.id), 'Означено како поднесено.');
                }}
              >
                {busy === 'submitted' ? 'Се зачувува…' : 'Означи поднесено'}
              </Button>
              {job.submitted_at && (
                <span className="text-muted-foreground">Поднесено {formatDateTime(job.submitted_at)}</span>
              )}
            </div>

            <div className="flex flex-wrap items-end gap-2">
              <div className="w-56">
                <Label className="text-xs">Исход</Label>
                <Select
                  value={outcome}
                  onValueChange={(v) => setOutcome(v as BidOutcome)}
                  disabled={!canSetOutcome || isBusy}
                >
                  <SelectTrigger aria-label="Исход">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(OUTCOME_LABELS) as BidOutcome[]).map((o) => (
                      <SelectItem key={o} value={o}>
                        {OUTCOME_LABELS[o]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                size="sm"
                disabled={!canSetOutcome || isBusy}
                onClick={() => {
                  if (!confirm(`Исход: ${OUTCOME_LABELS[outcome]}? Клиентот добива известување.`)) return;
                  run('outcome', () => api.setBidJobOutcome(job.id, outcome), 'Исходот е зачуван.');
                }}
              >
                {busy === 'outcome' ? 'Се зачувува…' : 'Зачувај исход'}
              </Button>
              {job.outcome && (
                <span className="text-muted-foreground">
                  Тековно: {OUTCOME_LABELS[job.outcome]} ({formatDateTime(job.outcome_at)})
                </span>
              )}
            </div>

            <div className="space-y-2 rounded-md border p-3">
              <Label htmlFor="cancel-reason" className="text-xs">
                Причина за откажување (опционално)
              </Label>
              <Textarea
                id="cancel-reason"
                rows={2}
                maxLength={1000}
                value={cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
                disabled={!canCancel || isBusy}
              />
              <Button
                size="sm"
                variant="destructive"
                disabled={!canCancel || isBusy}
                onClick={() => {
                  if (!confirm('Откажи го барањето? Клиентот добива известување.')) return;
                  run(
                    'cancel',
                    async () => {
                      await api.adminCancelBidJob(job.id, cancelReason.trim() || undefined);
                      setCancelReason('');
                    },
                    'Барањето е откажано.'
                  );
                }}
              >
                {busy === 'cancel' ? 'Се откажува…' : 'Откажи'}
              </Button>
            </div>

            <div className="space-y-1">
              <Label className="text-xs">Задолжен</Label>
              <Select
                value={job.assigned_to ?? 'none'}
                onValueChange={(v) =>
                  run(
                    'assign',
                    () => api.assignBidJob(job.id, v === 'none' ? null : v),
                    'Задолжувањето е зачувано.'
                  )
                }
                disabled={isBusy}
              >
                <SelectTrigger aria-label="Задолжен">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Никој</SelectItem>
                  {job.assigned_to && !team.some((m) => m.user_id === job.assigned_to) && (
                    <SelectItem value={job.assigned_to}>{job.assigned_to_email || job.assigned_to}</SelectItem>
                  )}
                  {team.map((m) => (
                    <SelectItem key={m.user_id} value={m.user_id}>
                      {m.full_name ? `${m.full_name} (${m.email})` : m.email}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="admin-notes" className="text-xs">
                Интерни белешки
              </Label>
              <Textarea
                id="admin-notes"
                rows={4}
                maxLength={10000}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                disabled={isBusy}
              />
              <Button
                size="sm"
                variant="outline"
                disabled={isBusy || notes === (job.admin_notes ?? '')}
                onClick={() => run('notes', () => api.updateAdminBidJob(job.id, { admin_notes: notes }), 'Белешките се зачувани.')}
              >
                {busy === 'notes' ? 'Се зачувува…' : 'Зачувај белешки'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Deliverables */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between gap-4 pb-2">
          <CardTitle className="text-lg">Документи за понудата</CardTitle>
          <Button
            size="sm"
            disabled={!canPublish || isBusy}
            title={job.publish_blocked_reason ?? undefined}
            onClick={async () => {
              if (!confirm('Објави ги сите документи на клиентот? Клиентот добива известување.')) return;
              setBusy('publish');
              setActionError(null);
              setPublishMissing(null);
              try {
                await api.publishBidJob(job.id);
                toast.success('Документите се објавени на клиентот.');
              } catch (err) {
                const block = successFeeBlock(err);
                if (block) {
                  const missing = block.missing.length
                    ? block.missing
                    : missingAuthorisation(client, null);
                  setPublishMissing(missing);
                  const msg = block.message || 'Надоместот за успех не е овластен.';
                  setActionError(msg);
                  toast.error(msg);
                } else {
                  const msg = errorMessage(err, 'Акцијата не успеа.');
                  setActionError(msg);
                  toast.error(msg);
                }
              } finally {
                setBusy(null);
                await load();
              }
            }}
          >
            {busy === 'publish' ? 'Се објавува…' : 'Објави на клиентот'}
          </Button>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {(publishBlocked || publishMissing) && (
            <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="space-y-1">
                <p className="font-medium">
                  {job.publish_blocked_reason || 'Надоместот за успех не е овластен.'}
                </p>
                {publishMissing && publishMissing.length > 0 && (
                  <p>Недостасува: {publishMissing.map((m) => MISSING_LABELS[m] ?? m).join(', ')}.</p>
                )}
                <p className="text-xs">
                  Клиентот ги прифаќа условите и зачувува картичка во порталот (Плаќање), или евидентирајте
                  писмено овластување во делот Клиент подолу.
                </p>
              </div>
            </div>
          )}
          <form onSubmit={handleUpload} className="grid gap-2 rounded-md border p-3 md:grid-cols-[1fr_200px_1fr_auto] md:items-end">
            <div>
              <Label htmlFor="bid-file" className="text-xs">
                Датотека (до 25 MB)
              </Label>
              <Input
                id="bid-file"
                ref={fileInputRef}
                type="file"
                accept={BID_FILE_ACCEPT}
                onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
                disabled={!canUpload || isBusy}
              />
            </div>
            <div>
              <Label className="text-xs">Вид</Label>
              <Select
                value={uploadKind}
                onValueChange={(v) => setUploadKind(v as BidFileKind)}
                disabled={!canUpload || isBusy}
              >
                <SelectTrigger aria-label="Вид">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {KIND_OPTIONS.map((k) => (
                    <SelectItem key={k} value={k}>
                      {BID_FILE_KIND_LABELS[k]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="bid-file-title" className="text-xs">
                Наслов (опционално)
              </Label>
              <Input
                id="bid-file-title"
                value={uploadTitle}
                maxLength={300}
                onChange={(e) => setUploadTitle(e.target.value)}
                disabled={!canUpload || isBusy}
              />
            </div>
            <Button type="submit" size="sm" disabled={!canUpload || isBusy || !uploadFile}>
              <Upload className="w-4 h-4 mr-2" />
              {busy === 'upload' ? 'Се прикачува…' : 'Прикачи'}
            </Button>
          </form>

          {files.length === 0 ? (
            <p className="py-4 text-center text-muted-foreground">Нема прикачени документи.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Документ</th>
                    <th className="py-2 pr-3 font-medium">Видлив</th>
                    <th className="py-2 pr-3 font-medium">Статус</th>
                    <th className="py-2 pr-3 font-medium">Коментар од клиентот</th>
                    <th className="py-2 font-medium text-right">Акции</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((f) => (
                    <tr key={f.id} className="border-b last:border-0 align-top">
                      <td className="py-2 pr-3">
                        <p className="font-medium break-words">{f.title}</p>
                        <p className="text-xs text-muted-foreground break-all">
                          {BID_FILE_KIND_LABELS[f.kind]} · {f.original_name} · {formatSize(f.size_bytes)} ·{' '}
                          {formatDateTime(f.created_at)}
                        </p>
                      </td>
                      <td className="py-2 pr-3">
                        {f.client_visible ? (
                          <span className="text-green-700 dark:text-green-400">Да</span>
                        ) : (
                          <span className="text-muted-foreground">Не (сè уште необјавен)</span>
                        )}
                      </td>
                      <td className="py-2 pr-3">
                        <span
                          className={
                            f.approval_status === 'approved'
                              ? 'text-green-700 dark:text-green-400'
                              : f.approval_status === 'changes_requested'
                                ? 'font-medium text-amber-700 dark:text-amber-400'
                                : 'text-muted-foreground'
                          }
                        >
                          {FILE_APPROVAL_LABELS[f.approval_status]}
                        </span>
                        {f.reviewed_at && (
                          <span className="block text-xs text-muted-foreground">{formatDateTime(f.reviewed_at)}</span>
                        )}
                      </td>
                      <td className="py-2 pr-3 whitespace-pre-wrap break-words">{f.client_comment || '—'}</td>
                      <td className="py-2 text-right whitespace-nowrap">
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={isBusy}
                          aria-label="Преземи"
                          onClick={() =>
                            run(`dl-${f.id}`, () => api.adminDownloadBidJobFile(job.id, f.id, f.original_name))
                          }
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={isBusy}
                          aria-label="Избриши"
                          onClick={() => {
                            if (!confirm(`Избриши го документот „${f.title}“?`)) return;
                            run(`del-${f.id}`, () => api.deleteBidJobFile(job.id, f.id), 'Документот е избришан.');
                          }}
                        >
                          <Trash2 className="w-4 h-4 text-red-600" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Client */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Клиент</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            <div className="grid gap-1">
              <p className="font-medium">{client.full_name || '—'}</p>
              <a href={`mailto:${client.email}`} className="text-blue-600 hover:underline break-all">
                {client.email}
              </a>
              <p className="text-muted-foreground">
                {ACCOUNT_TYPE_LABELS[client.account_type] ?? client.account_type}
              </p>
              <p className={client.terms_agreed_at ? 'text-muted-foreground' : 'text-amber-700 dark:text-amber-400'}>
                {client.terms_agreed_at
                  ? `Услови прифатени ${formatDay(client.terms_agreed_at)} (верзија ${client.agreement_version ?? '—'})`
                  : 'Условите сè уште не се прифатени: клиентот ги прифаќа во порталот.'}
              </p>
            </div>

            <div className="space-y-2 rounded-md border p-3">
              <p className="font-medium">Картичка и надомест за успех</p>
              <p className={client.has_card ? '' : 'text-muted-foreground'}>
                {client.has_card
                  ? `Зачувана картичка: ${client.card_brand ? client.card_brand.toUpperCase() : 'картичка'}${
                      client.card_last4 ? ` •••• ${client.card_last4}` : ''
                    }`
                  : 'Нема зачувана картичка.'}
              </p>
              <p
                className={
                  sfAuthorised
                    ? 'text-green-700 dark:text-green-400'
                    : 'text-amber-700 dark:text-amber-400'
                }
              >
                {sfAuthorised
                  ? `Надоместот за успех е овластен ${formatDay(client.success_fee_authorised_at)} (${
                      client.success_fee_authorised_via === 'offline' ? 'писмен договор' : 'картичка'
                    })${client.success_fee_authorised_ref ? `, реф. ${client.success_fee_authorised_ref}` : ''}`
                  : 'Надоместот за успех сè уште не е овластен.'}
              </p>
              {!sfAuthorised && (
                <form
                  className="space-y-2"
                  onSubmit={(e) => {
                    e.preventDefault();
                    const ref = authRef.trim();
                    if (ref.length < 3 || ref.length > 120) {
                      setActionError('Референцата мора да има од 3 до 120 знаци.');
                      return;
                    }
                    if (!confirm('Евидентирај писмено овластување за надоместот за успех за овој клиент?')) return;
                    run(
                      'authorise',
                      async () => {
                        await api.adminAuthoriseSuccessFee(client.user_id, ref);
                        setAuthRef('');
                        setPublishMissing(null);
                      },
                      'Овластувањето е евидентирано.'
                    );
                  }}
                >
                  <Label htmlFor="auth-ref" className="text-xs">
                    Референца (број на договор или архивски број)
                  </Label>
                  <div className="flex gap-2">
                    <Input
                      id="auth-ref"
                      value={authRef}
                      minLength={3}
                      maxLength={120}
                      placeholder="на пр. Договор бр. 12/2026"
                      onChange={(e) => setAuthRef(e.target.value)}
                      disabled={isBusy}
                    />
                    <Button
                      type="submit"
                      size="sm"
                      variant="outline"
                      disabled={isBusy || authRef.trim().length < 3}
                    >
                      {busy === 'authorise' ? 'Се зачувува…' : 'Евидентирај писмено овластување'}
                    </Button>
                  </div>
                </form>
              )}
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                const tid = newTenderId.trim();
                if (!tid) {
                  setActionError('Внесете број на тендер.');
                  return;
                }
                run(
                  'create-job',
                  async () => {
                    const res = await api.adminCreateBidJob(client.user_id, tid);
                    setNewTenderId('');
                    toast.success(res.created ? 'Понудата е креирана.' : 'Клиентот веќе има понуда за овој тендер.');
                    window.location.href = `/admin/bids/${res.job.id}`;
                  }
                );
              }}
              className="space-y-2 rounded-md border p-3"
            >
              <Label htmlFor="new-tender" className="text-xs">
                Креирај понуда за овој клиент (друг тендер)
              </Label>
              <div className="flex gap-2">
                <Input
                  id="new-tender"
                  value={newTenderId}
                  placeholder="на пр. 17400/2026"
                  maxLength={100}
                  onChange={(e) => setNewTenderId(e.target.value)}
                  disabled={isBusy}
                />
                <Button type="submit" size="sm" variant="outline" disabled={isBusy || !newTenderId.trim()}>
                  {busy === 'create-job' ? 'Се креира…' : 'Креирај'}
                </Button>
              </div>
            </form>

            <form onSubmit={handleSaveClient} className="space-y-3 rounded-md border p-3">
              <div className="flex items-center gap-2">
                <Switch
                  id="free-drafting"
                  checked={freeDrafting}
                  onCheckedChange={setFreeDrafting}
                  disabled={isBusy}
                />
                <Label htmlFor="free-drafting">Без надомест (одобрено од админ, без фактура)</Label>
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <Label htmlFor="client-fee" className="text-xs">
                    Стандарден надомест (МКД)
                  </Label>
                  <Input
                    id="client-fee"
                    type="number"
                    min={0}
                    max={10000000}
                    step={1}
                    value={clientFee}
                    onChange={(e) => setClientFee(e.target.value)}
                    disabled={isBusy}
                  />
                </div>
                <div>
                  <Label htmlFor="client-pct" className="text-xs">
                    Надомест при доделување (%)
                  </Label>
                  <Input
                    id="client-pct"
                    type="number"
                    min={0}
                    max={100}
                    step={0.01}
                    value={clientPct}
                    onChange={(e) => setClientPct(e.target.value)}
                    disabled={isBusy}
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="client-company" className="text-xs">
                  Назив на компанијата
                </Label>
                <Input
                  id="client-company"
                  value={clientCompany}
                  maxLength={500}
                  onChange={(e) => setClientCompany(e.target.value)}
                  disabled={isBusy}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Важи за идните барања. Постојните понуди не се менуваат.
              </p>
              <Button type="submit" size="sm" variant="outline" disabled={isBusy}>
                {busy === 'client' ? 'Се зачувува…' : 'Зачувај поставки'}
              </Button>
            </form>

            <div className="space-y-2">
              <p className="font-medium">Документи на компанијата</p>
              {client_documents.length === 0 ? (
                <p className="text-muted-foreground">Клиентот нема прикачено документи.</p>
              ) : (
                <ul className="divide-y rounded-md border">
                  {client_documents.map((d) => (
                    <li key={d.id} className="flex items-start justify-between gap-2 p-2">
                      <div className="min-w-0">
                        <p className="font-medium break-words">{d.title}</p>
                        <p className="text-xs text-muted-foreground">
                          {CLIENT_DOCUMENT_CATEGORY_LABELS[d.category]} · {formatSize(d.size_bytes)}
                          {d.expires_on ? ` · важи до ${formatDay(d.expires_on)}` : ''}
                        </p>
                        {d.expired && (
                          <span className="mt-1 inline-block rounded-full bg-red-100 px-2 text-xs font-semibold text-red-800 dark:bg-red-950 dark:text-red-300">
                            Истечен
                          </span>
                        )}
                        {!d.expired && d.expires_soon && (
                          <span className="mt-1 inline-block rounded-full bg-amber-100 px-2 text-xs font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                            Истекува наскоро
                          </span>
                        )}
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={isBusy}
                        aria-label="Преземи"
                        onClick={() =>
                          run(`doc-${d.id}`, () =>
                            api.adminDownloadClientDocument(client.user_id, d.id, d.original_name)
                          )
                        }
                      >
                        <Download className="w-4 h-4" />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Messages */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg">Пораки</CardTitle>
          </CardHeader>
          <CardContent>
            <MessageThread
              messages={messages}
              viewerRole="admin"
              emptyText="Нема пораки за оваа понуда."
              onSend={async (body) => {
                // MessageThread shows the backend detail itself when this throws.
                await api.sendAdminBidJobMessage(job.id, body);
                await load();
              }}
            />
          </CardContent>
        </Card>
      </div>

      {/* Events */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-lg">Историја</CardTitle>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <p className="text-sm text-muted-foreground">Нема настани.</p>
          ) : (
            <ul className="space-y-1 text-sm">
              {events.map((ev, i) => (
                <li key={`${ev.created_at}-${ev.event}-${i}`} className="flex flex-wrap gap-x-3 gap-y-0.5">
                  <span className="w-36 shrink-0 text-muted-foreground">{formatDateTime(ev.created_at)}</span>
                  <span className={ev.kind === 'notify' ? 'text-indigo-700 dark:text-indigo-400' : 'font-medium'}>
                    {ev.kind === 'notify'
                      ? `Е-пошта: ${ev.event}`
                      : EVENT_LABELS[ev.event] ?? ev.event}
                  </span>
                  {ev.actor_role && (
                    <span className="text-muted-foreground">({ACTOR_LABELS[ev.actor_role] ?? ev.actor_role})</span>
                  )}
                  {ev.detail && Object.keys(ev.detail).length > 0 && (
                    <code className="break-all text-xs text-muted-foreground">{JSON.stringify(ev.detail)}</code>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
