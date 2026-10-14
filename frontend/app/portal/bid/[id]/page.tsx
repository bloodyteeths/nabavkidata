'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, Building2, CalendarDays, CheckCheck, Loader2, Send, XCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { PageContainer } from '@/components/ui/page-container';
import { api } from '@/lib/api';
import { cn, tenderUrl } from '@/lib/utils';
import { ENABAVKI_SUBMIT_REMINDER, formatMkd } from '@/lib/bid-service-types';
import type { BidAgreement, BidJobDetailResponse, BidJobStatus } from '@/lib/bid-service-types';
import JobStatusBadge from '@/components/bid-service/JobStatusBadge';
import DeadlineWarning, { formatDmy } from '@/components/bid-service/DeadlineWarning';
import PaymentBox from '@/components/bid-service/PaymentBox';
import DeliverablesList from '@/components/bid-service/DeliverablesList';
import MessageThread from '@/components/bid-service/MessageThread';
import { AgreementTerms } from '@/components/bid-service/StartBidButton';

const REVIEW_STATUSES: BidJobStatus[] = ['ready', 'changes_requested', 'approved'];

type Action = 'approve_all' | 'submit' | 'cancel' | 'terms';

export default function PortalBidPage() {
  const params = useParams<{ id: string }>();
  const jobId = params?.id ?? '';

  const [data, setData] = useState<BidJobDetailResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState<Action | null>(null);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [cancelReason, setCancelReason] = useState('');
  // Jobs opened by our team for the client still need the client's acceptance of the terms.
  const [agreement, setAgreement] = useState<BidAgreement | null>(null);
  const [termsTicked, setTermsTicked] = useState(false);

  const load = useCallback(async () => {
    if (!jobId) return;
    try {
      const [res, agr] = await Promise.all([
        api.getBidJob(jobId),
        api.getBidAgreement().catch(() => null),
      ]);
      setData(res);
      setAgreement(agr);
      setLoadError(null);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'Понудата не се вчита.');
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (action: Action, fn: () => Promise<unknown>) => {
    setBusy(action);
    setActionError(null);
    try {
      await fn();
      await load();
      return true;
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Акцијата не успеа. Обидете се повторно.');
      return false;
    } finally {
      setBusy(null);
    }
  };

  if (loadError && !data) {
    return (
      <PageContainer>
        <Link href="/portal/bids" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline">
          <ArrowLeft className="h-4 w-4" /> Мои понуди
        </Link>
        <p className="text-red-600 dark:text-red-400">{loadError}</p>
      </PageContainer>
    );
  }

  if (!data) {
    return (
      <div className="flex justify-center py-16 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Се вчитува…
      </div>
    );
  }

  const { job, tender, files, messages, payment } = data;
  const title = tender.title || job.tender_title || job.tender_id;
  const closing = tender.closing_date ?? job.closing_date;
  const buyer = tender.procuring_entity ?? job.procuring_entity;
  const canReview = REVIEW_STATUSES.includes(job.status);

  return (
    <PageContainer className="max-w-5xl">
      <Link href="/portal/bids" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:underline">
        <ArrowLeft className="h-4 w-4" /> Мои понуди
      </Link>

      {/* Header */}
      <div className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-1">
            <p className="text-xs text-muted-foreground">{job.tender_id}</p>
            <h1 className="text-xl font-bold leading-snug sm:text-2xl">
              <Link href={tenderUrl(job.tender_id)} className="hover:underline">
                {title}
              </Link>
            </h1>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
              {buyer && (
                <span className="flex items-center gap-1">
                  <Building2 className="h-4 w-4 shrink-0" /> {buyer}
                </span>
              )}
              <span className="flex items-center gap-1">
                <CalendarDays className="h-4 w-4 shrink-0" /> Рок: {formatDmy(closing)}
              </span>
              {tender.estimated_value_mkd !== null && (
                <span>Проценета вредност: {formatMkd(tender.estimated_value_mkd)}</span>
              )}
            </div>
          </div>
          <JobStatusBadge status={job.status} className="w-fit shrink-0" />
        </div>

        <div
          className={cn(
            'rounded-md border px-4 py-3 text-sm font-medium',
            job.whose_move === 'client'
              ? 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100'
              : job.whose_move === 'us'
              ? 'border-blue-200 bg-blue-50 text-blue-900 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-100'
              : 'border-border bg-muted text-foreground'
          )}
        >
          {job.phase_text}
        </div>

        <DeadlineWarning closingDate={closing} deadlineState={job.deadline_state} daysLeft={job.days_left} />

        {actionError && (
          <p className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
            {actionError}
          </p>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          {/* Deliverables */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between gap-3 space-y-0 pb-3">
              <CardTitle className="text-base">Документи за понудата</CardTitle>
              {job.can_approve_all && (
                <Button
                  size="sm"
                  disabled={busy !== null}
                  onClick={() => run('approve_all', () => api.approveAllBidFiles(job.id))}
                >
                  {busy === 'approve_all' ? (
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCheck className="mr-1.5 h-4 w-4" />
                  )}
                  Одобри сè
                </Button>
              )}
            </CardHeader>
            <CardContent>
              <DeliverablesList jobId={job.id} files={files} canReview={canReview} onChanged={load} />
            </CardContent>
          </Card>

          {/* Submission */}
          {job.can_mark_submitted && (
            <Card className="border-amber-300 dark:border-amber-700">
              <CardContent className="space-y-3 p-4">
                <p className="text-sm">{ENABAVKI_SUBMIT_REMINDER}</p>
                <Button disabled={busy !== null} onClick={() => setConfirmSubmit(true)}>
                  <Send className="mr-1.5 h-4 w-4" />
                  Поднесено
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Messages */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Пораки за оваа понуда</CardTitle>
            </CardHeader>
            <CardContent>
              <MessageThread
                messages={messages}
                viewerRole="client"
                emptyText="Имате прашање за оваа понуда? Пишете ни."
                onSend={async (body) => {
                  await api.sendBidJobMessage(job.id, body);
                  await load();
                }}
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {agreement && !agreement.accepted && job.can_cancel && (
            <Card className="border-amber-300 dark:border-amber-700">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Услови на услугата</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <AgreementTerms agreement={agreement} />
                <label className="flex cursor-pointer items-start gap-2 text-sm">
                  <Checkbox
                    checked={termsTicked}
                    onCheckedChange={(v) => setTermsTicked(v === true)}
                    disabled={busy !== null}
                    className="mt-0.5"
                  />
                  <span>Ги прочитав и ги прифаќам условите на услугата.</span>
                </label>
                <Button
                  size="sm"
                  disabled={!termsTicked || busy !== null}
                  onClick={() => run('terms', () => api.acceptBidAgreement(agreement.current_version))}
                >
                  {busy === 'terms' && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                  Прифаќам
                </Button>
              </CardContent>
            </Card>
          )}

          <PaymentBox payment={payment} status={job.status} jobId={job.id} />

          {job.client_note && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Ваша белешка</CardTitle>
              </CardHeader>
              <CardContent className="whitespace-pre-wrap text-sm">{job.client_note}</CardContent>
            </Card>
          )}

          {job.status === 'cancelled' && job.cancel_reason && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Причина за откажување</CardTitle>
              </CardHeader>
              <CardContent className="whitespace-pre-wrap text-sm">{job.cancel_reason}</CardContent>
            </Card>
          )}

          {job.can_cancel && (
            <Button
              variant="outline"
              className="w-full text-red-600 hover:text-red-700 dark:text-red-400"
              disabled={busy !== null}
              onClick={() => {
                setCancelReason('');
                setConfirmCancel(true);
              }}
            >
              <XCircle className="mr-1.5 h-4 w-4" />
              Откажи барање
            </Button>
          )}
        </div>
      </div>

      {/* Confirm: submitted */}
      <Dialog open={confirmSubmit} onOpenChange={(o) => busy === null && setConfirmSubmit(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ја поднесовте понудата?</DialogTitle>
            <DialogDescription>
              Потврдете само ако понудата е потпишана и поднесена на e-nabavki.gov.mk.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" disabled={busy !== null} onClick={() => setConfirmSubmit(false)}>
              Назад
            </Button>
            <Button
              disabled={busy !== null}
              onClick={async () => {
                const ok = await run('submit', () => api.markBidJobSubmitted(job.id));
                if (ok) setConfirmSubmit(false);
              }}
            >
              {busy === 'submit' && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Да, поднесена е
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Confirm: cancel */}
      <Dialog open={confirmCancel} onOpenChange={(o) => busy === null && setConfirmCancel(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Да го откажеме барањето?</DialogTitle>
            <DialogDescription>
              Ќе престанеме со подготовка на оваа понуда. Причината не е задолжителна.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={cancelReason}
            onChange={(e) => setCancelReason(e.target.value)}
            placeholder="Причина (опционално)"
            rows={3}
            maxLength={1000}
            disabled={busy !== null}
          />
          <DialogFooter className="gap-2">
            <Button variant="outline" disabled={busy !== null} onClick={() => setConfirmCancel(false)}>
              Назад
            </Button>
            <Button
              variant="destructive"
              disabled={busy !== null}
              onClick={async () => {
                const reason = cancelReason.trim();
                const ok = await run('cancel', () => api.cancelBidJob(job.id, reason || undefined));
                if (ok) setConfirmCancel(false);
              }}
            >
              {busy === 'cancel' && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Откажи барање
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
