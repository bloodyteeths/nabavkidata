'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';
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
import type { BidAgreement } from '@/lib/bid-service-types';
import { formatDmy } from '@/components/bid-service/DeadlineWarning';

interface StartBidButtonProps {
  tenderId: string;
  tenderTitle?: string | null;
  label?: string;
  className?: string;
  disabled?: boolean;
}

/** The fee and success-fee terms in one place, shared by the start dialog and the terms card. */
export function AgreementTerms({ agreement }: { agreement: BidAgreement }) {
  return (
    <div className="space-y-2 text-sm">
      {agreement.free_drafting ? (
        <p>Подготовката на понудите за вашата компанија е без надомест.</p>
      ) : (
        <p>
          Надомест за подготовка:{' '}
          <span className="font-semibold">{formatMkd(agreement.prep_fee_mkd)}</span> (без ДДВ), по фактура
          од Фактурино ДООЕЛ. Со подготовката започнуваме откако ќе ја евидентираме уплатата.
        </p>
      )}
      {agreement.success_fee_pct !== null && (
        <p>
          При доделена набавка: <span className="font-semibold">{agreement.success_fee_pct}%</span> од
          вредноста на договорот за првата година, по фактура.
        </p>
      )}
      <p className="text-muted-foreground">Износите се без ДДВ: Фактурино ДООЕЛ не е ДДВ обврзник.</p>
      <p>
        <Link href="/terms" target="_blank" className="text-primary underline underline-offset-4">
          Услови за користење
        </Link>
      </p>
    </div>
  );
}

/**
 * „Започни понуда“ with a confirmation step: shows the client's own prep fee and
 * success fee and records acceptance of the service terms before the job (and
 * the admin email) is created. A misclick therefore never starts a paid bid.
 */
export default function StartBidButton({
  tenderId,
  tenderTitle,
  label = 'Започни понуда',
  className,
  disabled,
}: StartBidButtonProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [agreement, setAgreement] = useState<BidAgreement | null>(null);
  const [loading, setLoading] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAgreement = async () => {
    setLoading(true);
    setError(null);
    try {
      setAgreement(await api.getBidAgreement());
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

  const confirm = async () => {
    if (!agreement) return;
    setBusy(true);
    setError(null);
    try {
      const res = await api.beginBidJob(tenderId, undefined, !agreement.accepted);
      router.push(`/portal/bid/${res.job.id}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '';
      if (msg === TERMS_REQUIRED) {
        // Terms changed meanwhile: reload them and ask again.
        setAgreement(null);
        setAccepted(false);
        void loadAgreement();
        setError('Условите се променија. Прочитајте ги и потврдете повторно.');
      } else {
        setError(msg || 'Барањето не успеа. Обидете се повторно.');
      }
      setBusy(false);
    }
  };

  const needsTick = agreement !== null && !agreement.accepted;

  return (
    <>
      <Button onClick={openDialog} disabled={disabled || busy} className={className}>
        {label}
      </Button>
      <Dialog open={open} onOpenChange={(o) => !busy && setOpen(o)}>
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
                    disabled={busy}
                    className="mt-0.5"
                  />
                  <span>Ги прочитав и ги прифаќам условите на услугата.</span>
                </label>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Условите ги прифативте на {formatDmy(agreement.terms_agreed_at)}.
                </p>
              )}
            </div>
          )}
          {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
          <DialogFooter className="gap-2">
            <Button variant="outline" disabled={busy} onClick={() => setOpen(false)}>
              Назад
            </Button>
            <Button onClick={confirm} disabled={busy || !agreement || (needsTick && !accepted)}>
              {busy && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Потврди и започни
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
