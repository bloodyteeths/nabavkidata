'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { CreditCard, FileText, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { api } from '@/lib/api';
import { TERMS_REQUIRED, formatMkd } from '@/lib/bid-service-types';
import type { BidAgreement, BidJobSummary } from '@/lib/bid-service-types';
import { formatDmy } from '@/components/bid-service/DeadlineWarning';

interface StartBidButtonProps {
  tenderId: string;
  tenderTitle?: string | null;
  label?: string;
  className?: string;
  disabled?: boolean;
  /** Open the confirmation dialog on mount (tender page ?start=1 after auto-login). */
  autoOpen?: boolean;
}

/** Shown when Stripe is not configured (503 from the API) — matches backend ERR_CARD_UNAVAILABLE. */
const ERR_CARD_UNAVAILABLE =
  'Плаќањето со картичка моментално не е достапно. Изберете плаќање со фактура.';

/** True when the client pays no prep fee (admin free drafting, or a zero fee). */
function isFreeDrafting(agreement: BidAgreement): boolean {
  return agreement.free_drafting || !(agreement.prep_fee_mkd && agreement.prep_fee_mkd > 0);
}

/** The fee and success-fee terms in one place, shared by the start dialog and the terms card. */
export function AgreementTerms({ agreement }: { agreement: BidAgreement }) {
  const free = isFreeDrafting(agreement);
  return (
    <div className="space-y-2 text-sm">
      {free ? (
        <p>Подготовката на понудите за вашата компанија е без надомест.</p>
      ) : (
        <p>
          Надомест за подготовка:{' '}
          <span className="font-semibold">{formatMkd(agreement.prep_fee_mkd)}</span> (без ДДВ), со картичка
          или по фактура од Фактурино ДООЕЛ. Со подготовката започнуваме откако ќе ја евидентираме уплатата.
        </p>
      )}
      {agreement.success_fee_pct !== null && (
        <p>
          При доделена набавка: <span className="font-semibold">{agreement.success_fee_pct}%</span> од
          вредноста на договорот за првата година
          {free ? '.' : ', намалено за надоместот за подготовка платен за таа понуда.'}
        </p>
      )}
      <p>
        Зачуваната картичка се користи за надоместот за успех, со најава најмалку седум дена пред наплатата.
        Наместо картичка, може да платите и по фактура.
      </p>
      <p className="text-muted-foreground">Износите се без ДДВ: Фактурино ДООЕЛ не е ДДВ обврзник.</p>
      <p>
        <Link href="/terms" target="_blank" className="text-primary underline underline-offset-4">
          Услови за користење
        </Link>
      </p>
    </div>
  );
}

type Busy = 'card' | 'invoice' | 'free' | null;

/**
 * „Започни понуда“ with a confirmation step: shows the client's own prep fee and
 * success fee and records acceptance of the service terms before the job (and
 * the admin email) is created. A misclick therefore never starts a paid bid.
 *
 * Paying clients then choose: card (Stripe Checkout, the card is saved for the
 * success fee) or invoice (our team issues an invoice and records the payment).
 */
export default function StartBidButton({
  tenderId,
  tenderTitle,
  label = 'Започни понуда',
  className,
  disabled,
  autoOpen = false,
}: StartBidButtonProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [agreement, setAgreement] = useState<BidAgreement | null>(null);
  const [cardEnabled, setCardEnabled] = useState(true);
  const [loading, setLoading] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const autoOpened = useRef(false);

  const loadAgreement = async () => {
    setLoading(true);
    setError(null);
    try {
      const [agr, billing] = await Promise.all([
        api.getBidAgreement(),
        api.getServiceBillingStatus().catch(() => null),
      ]);
      setAgreement(agr);
      // Unknown billing status: offer the card and let the API answer 503 if it is off.
      if (billing) setCardEnabled(billing.card_payments_enabled);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Условите не се вчитаа.');
    } finally {
      setLoading(false);
    }
  };

  const openDialog = () => {
    setOpen(true);
    setAccepted(false);
    setError(null);
    if (!agreement) void loadAgreement();
  };

  useEffect(() => {
    if (!autoOpen || disabled || autoOpened.current) return;
    autoOpened.current = true;
    openDialog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoOpen, disabled]);

  const begin = async (): Promise<BidJobSummary & { paymentRequired: boolean }> => {
    const res = await api.beginBidJob(tenderId, undefined, !agreement?.accepted);
    // Terms are now accepted; a retry must not resend them.
    setAgreement((a) => (a ? { ...a, accepted: true } : a));
    return { ...res.job, paymentRequired: Boolean(res.payment_required) || res.job.status === 'payment_required' };
  };

  const handleError = (e: unknown) => {
    const msg = e instanceof Error ? e.message : '';
    const status = (e as { status?: number } | null)?.status;
    if (msg === TERMS_REQUIRED) {
      // Terms changed meanwhile: reload them and ask again.
      setAgreement(null);
      setAccepted(false);
      void loadAgreement();
      setError('Условите се променија. Прочитајте ги и потврдете повторно.');
    } else if (status === 503) {
      setCardEnabled(false);
      setError(msg || ERR_CARD_UNAVAILABLE);
    } else {
      setError(msg || 'Барањето не успеа. Обидете се повторно.');
    }
    setBusy(null);
  };

  const startFree = async () => {
    if (!agreement) return;
    setBusy('free');
    setError(null);
    try {
      const job = await begin();
      router.push(`/portal/bid/${job.id}`);
    } catch (e) {
      handleError(e);
    }
  };

  const payByCard = async () => {
    if (!agreement) return;
    setBusy('card');
    setError(null);
    try {
      const job = await begin();
      if (!job.paymentRequired && job.status !== 'requested') {
        router.push(`/portal/bid/${job.id}`);
        return;
      }
      const { url } = await api.payBidPrepFee(job.id);
      window.location.href = url;
    } catch (e) {
      handleError(e);
    }
  };

  const payByInvoice = async () => {
    if (!agreement) return;
    setBusy('invoice');
    setError(null);
    try {
      const job = await begin();
      if (job.paymentRequired || job.status === 'requested') {
        await api.chooseBidInvoice(job.id);
      }
      router.push(`/portal/bid/${job.id}`);
    } catch (e) {
      handleError(e);
    }
  };

  const needsTick = agreement !== null && !agreement.accepted;
  const blocked = busy !== null || !agreement || (needsTick && !accepted);
  const free = agreement !== null && isFreeDrafting(agreement);

  return (
    <>
      <Button onClick={openDialog} disabled={disabled || busy !== null} className={className}>
        {label}
      </Button>
      <Dialog open={open} onOpenChange={(o) => busy === null && setOpen(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Започни понуда</DialogTitle>
            <DialogDescription>
              {tenderTitle ? `${tenderId} — ${tenderTitle}` : `Тендер ${tenderId}`}
            </DialogDescription>
          </DialogHeader>
          {loading || !agreement ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              {loading && <Loader2 className="h-4 w-4 animate-spin" />}
              {loading ? 'Се вчитува…' : null}
            </div>
          ) : (
            <div className="space-y-4">
              <AgreementTerms agreement={agreement} />
              {needsTick ? (
                <label className="flex cursor-pointer items-start gap-2 text-sm">
                  <Checkbox
                    checked={accepted}
                    onCheckedChange={(v) => setAccepted(v === true)}
                    disabled={busy !== null}
                    className="mt-0.5"
                  />
                  <span>Ги прочитав и ги прифаќам условите на услугата.</span>
                </label>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Условите ги прифативте на {formatDmy(agreement.terms_agreed_at)}.
                </p>
              )}
              {!free && !cardEnabled && (
                <p className="text-xs text-muted-foreground">{ERR_CARD_UNAVAILABLE}</p>
              )}
            </div>
          )}
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <DialogFooter className="gap-2">
            <Button variant="outline" disabled={busy !== null} onClick={() => setOpen(false)}>
              Назад
            </Button>
            {free || !agreement ? (
              <Button onClick={startFree} disabled={blocked}>
                {busy === 'free' && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
                Започни понуда
              </Button>
            ) : (
              <>
                <Button variant={cardEnabled ? 'outline' : 'default'} onClick={payByInvoice} disabled={blocked}>
                  {busy === 'invoice' ? (
                    <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  ) : (
                    <FileText className="mr-1.5 h-4 w-4" />
                  )}
                  Платам со фактура
                </Button>
                {cardEnabled && (
                  <Button onClick={payByCard} disabled={blocked}>
                    {busy === 'card' ? (
                      <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    ) : (
                      <CreditCard className="mr-1.5 h-4 w-4" />
                    )}
                    Плати со картичка
                  </Button>
                )}
              </>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
