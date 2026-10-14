'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';
import { CreditCard, Download, FileText, Loader2, Receipt } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { FAKTURINO_PAYEE, PAYMENT_INSTRUCTIONS, PAYMENT_NEXT_STEP, TERMS_REQUIRED, formatMkd } from '@/lib/bid-service-types';
import type { BidJobStatus, PaymentInfo } from '@/lib/bid-service-types';
import { formatDmy } from '@/components/bid-service/DeadlineWarning';

interface PaymentBoxProps {
  payment: PaymentInfo;
  status: BidJobStatus;
  /** The job the payment belongs to (card checkout, invoice request, invoice PDF). */
  jobId: string;
  /** Called after the client requested an invoice, so the page reloads the job. */
  onChanged?: () => void | Promise<void>;
  /** False while the current service terms are not accepted: card payment waits for them. */
  termsAccepted?: boolean;
}

const TERMS_FIRST = 'Прво прифатете ги условите на услугата (погоре), па платете.';

function PayeeRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
      <dt className="shrink-0 text-muted-foreground sm:w-40">{label}</dt>
      <dd className="font-medium break-words">{value}</dd>
    </div>
  );
}

/**
 * Payment state for a bid job. The prep fee is paid by card (Stripe Checkout,
 * the card is saved for the success fee) or by invoice from Фактурино ДООЕЛ.
 */
export default function PaymentBox({ payment, status, jobId, onChanged, termsAccepted = true }: PaymentBoxProps) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'card' | 'invoice' | null>(null);
  const [payError, setPayError] = useState<string | null>(null);
  const [cardOff, setCardOff] = useState(false);

  const downloadInvoice = async () => {
    if (!payment.invoice_file_name) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await api.downloadBidInvoice(jobId, payment.invoice_file_name);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : 'Фактурата не се презема.');
    } finally {
      setDownloading(false);
    }
  };

  const payByCard = async () => {
    setBusy('card');
    setPayError(null);
    try {
      const { url } = await api.payBidPrepFee(jobId);
      window.location.href = url;
    } catch (e) {
      if ((e as { status?: number } | null)?.status === 503) setCardOff(true);
      const msg = e instanceof Error ? e.message : '';
      setPayError(
        msg === TERMS_REQUIRED ? TERMS_FIRST : msg || 'Плаќањето не може да започне. Обидете се повторно.'
      );
      setBusy(null);
    }
  };

  const requestInvoice = async () => {
    setBusy('invoice');
    setPayError(null);
    try {
      await api.chooseBidInvoice(jobId);
      await onChanged?.();
    } catch (e) {
      setPayError(e instanceof Error && e.message ? e.message : 'Барањето не успеа. Обидете се повторно.');
    } finally {
      setBusy(null);
    }
  };

  const invoiceButton = payment.invoice_file_name ? (
    <div className="space-y-1">
      <Button size="sm" variant="outline" onClick={downloadInvoice} disabled={downloading}>
        {downloading ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Download className="mr-1.5 h-4 w-4" />}
        Преземи фактура
      </Button>
      {downloadError && <p className="text-xs text-red-600 dark:text-red-400">{downloadError}</p>}
    </div>
  ) : null;

  const canCard = Boolean(payment.can_pay_card) && !cardOff;
  const invoiceIssued = Boolean(payment.invoice_number);
  const invoiceRequested = Boolean(payment.invoice_requested_at);

  let main: ReactNode = null;

  if (payment.free) {
    main = <p>Подготовката на оваа понуда е без надомест.</p>;
  } else if (payment.paid_at) {
    const how =
      payment.paid_via === 'stripe' ? 'со картичка ' : payment.paid_via === 'invoice' ? 'по фактура ' : '';
    main = (
      <div className="space-y-2">
        <p>
          Уплатено {how}на {formatDmy(payment.paid_at)}.
        </p>
        {invoiceButton}
      </div>
    );
  } else if (payment.required) {
    main = (
      <div className="space-y-3">
        <p>
          Надомест за подготовка: <span className="font-semibold">{formatMkd(payment.prep_fee_mkd)}</span> (без ДДВ)
        </p>

        {(canCard || (!invoiceIssued && !invoiceRequested)) && (
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            {canCard && (
              <Button size="sm" onClick={payByCard} disabled={busy !== null || !termsAccepted}>
                {busy === 'card' ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                ) : (
                  <CreditCard className="mr-1.5 h-4 w-4" />
                )}
                Плати со картичка
              </Button>
            )}
            {!invoiceIssued && !invoiceRequested && (
              <Button size="sm" variant={canCard ? 'outline' : 'default'} onClick={requestInvoice} disabled={busy !== null}>
                {busy === 'invoice' ? (
                  <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                ) : (
                  <FileText className="mr-1.5 h-4 w-4" />
                )}
                Платам со фактура
              </Button>
            )}
          </div>
        )}
        {canCard && !termsAccepted && <p className="text-xs text-amber-700 dark:text-amber-300">{TERMS_FIRST}</p>}
        {canCard && (
          <p className="text-xs text-muted-foreground">
            Плаќањето со картичка е преку Stripe. Картичката се зачувува за надоместот за успех, кој се наплаќа
            најрано седум дена по нашата најава.
          </p>
        )}
        {payError && <p className="text-xs text-red-600 dark:text-red-400">{payError}</p>}

        {invoiceIssued ? (
          <>
            <p>
              Фактура бр. {payment.invoice_number} издадена на {formatDmy(payment.invoice_issued_at)}.
            </p>
            {invoiceButton}
            <dl className="space-y-1.5 rounded-md border bg-muted/40 p-3 text-xs">
              <PayeeRow label="Примач" value={FAKTURINO_PAYEE.name} />
              <PayeeRow label="Адреса" value={FAKTURINO_PAYEE.address} />
              <PayeeRow label="ЕДБ" value={FAKTURINO_PAYEE.edb} />
              {FAKTURINO_PAYEE.bankAccount ? (
                <PayeeRow
                  label="Трансакциска сметка"
                  value={`${FAKTURINO_PAYEE.bankAccount}${FAKTURINO_PAYEE.bankName ? `, ${FAKTURINO_PAYEE.bankName}` : ''}`}
                />
              ) : (
                <PayeeRow label="Трансакциска сметка" value="наведена во фактурата" />
              )}
              <PayeeRow label="Цел на дознаката" value={`Фактура бр. ${payment.invoice_number}`} />
              <PayeeRow label="Износ" value={`${formatMkd(payment.prep_fee_mkd)} (без ДДВ)`} />
            </dl>
            {!payment.invoice_file_name && (
              <p className="text-muted-foreground">
                Ако ви треба фактурата како документ, пишете ни во пораките и ќе ви ја испратиме.
              </p>
            )}
            <p className="font-medium text-amber-700 dark:text-amber-300">Чекаме уплата.</p>
            <p className="text-muted-foreground">{PAYMENT_NEXT_STEP}</p>
          </>
        ) : invoiceRequested ? (
          <p className="font-medium text-amber-700 dark:text-amber-300">
            Побаравте фактура. Ќе ја издадеме во рок од еден работен ден.
          </p>
        ) : (
          <p className="text-muted-foreground">{PAYMENT_INSTRUCTIONS}</p>
        )}
      </div>
    );
  } else if (status === 'requested') {
    main = (
      <div className="space-y-2">
        <p>Ја проверуваме понудата.</p>
        <p>
          Надомест за подготовка: <span className="font-semibold">{formatMkd(payment.prep_fee_mkd)}</span> (без ДДВ)
        </p>
      </div>
    );
  }

  const fee = payment.success_fee;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Receipt className="h-4 w-4" />
          Плаќање
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {main}
        {fee ? (
          <div className="space-y-1 rounded-md border bg-muted/40 p-3">
            <p className="font-medium">Надомест за успех</p>
            <p>
              Износ: <span className="font-semibold">{formatMkd(fee.fee_mkd)}</span> (без ДДВ)
            </p>
            {fee.first_year_value_mkd !== null && (
              <p className="text-muted-foreground">
                Вредност на договорот за првата година: {formatMkd(fee.first_year_value_mkd)}
              </p>
            )}
            {fee.status === 'invoiced' ? (
              <p className="text-muted-foreground">Надоместот е фактуриран.</p>
            ) : (
              fee.charge_not_before && (
                <p className="text-muted-foreground">Наплата најрано на {formatDmy(fee.charge_not_before)}.</p>
              )
            )}
          </div>
        ) : (
          payment.success_fee_pct !== null && (
            <p className="text-muted-foreground">
              При доделена набавка: {payment.success_fee_pct}% од вредноста на договорот за првата година.
            </p>
          )
        )}
      </CardContent>
    </Card>
  );
}
