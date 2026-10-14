'use client';

import { useState } from 'react';
import type { ReactNode } from 'react';
import { Download, Loader2, Receipt } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { FAKTURINO_PAYEE, PAYMENT_INSTRUCTIONS, PAYMENT_NEXT_STEP, formatMkd } from '@/lib/bid-service-types';
import type { BidJobStatus, PaymentInfo } from '@/lib/bid-service-types';
import { formatDmy } from '@/components/bid-service/DeadlineWarning';

interface PaymentBoxProps {
  payment: PaymentInfo;
  status: BidJobStatus;
  /** Needed to download the invoice PDF when the admin attached one. */
  jobId?: string;
}

function PayeeRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 sm:flex-row sm:gap-2">
      <dt className="shrink-0 text-muted-foreground sm:w-40">{label}</dt>
      <dd className="font-medium break-words">{value}</dd>
    </div>
  );
}

/** Invoice / payment state for a bid job. Payment is by invoice from Фактурино ДООЕЛ. */
export default function PaymentBox({ payment, status, jobId }: PaymentBoxProps) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const downloadInvoice = async () => {
    if (!jobId || !payment.invoice_file_name) return;
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

  const invoiceButton =
    jobId && payment.invoice_file_name ? (
      <div className="space-y-1">
        <Button size="sm" variant="outline" onClick={downloadInvoice} disabled={downloading}>
          {downloading ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Download className="mr-1.5 h-4 w-4" />}
          Преземи фактура
        </Button>
        {downloadError && <p className="text-xs text-red-600 dark:text-red-400">{downloadError}</p>}
      </div>
    ) : null;

  let main: ReactNode = null;

  if (payment.free) {
    main = <p>Подготовката на оваа понуда е без надомест.</p>;
  } else if (payment.paid_at) {
    main = (
      <div className="space-y-2">
        <p>Уплатено на {formatDmy(payment.paid_at)}.</p>
        {invoiceButton}
      </div>
    );
  } else if (status === 'payment_required') {
    main = (
      <div className="space-y-3">
        <p>
          Фактура бр. {payment.invoice_number ?? '—'} издадена на {formatDmy(payment.invoice_issued_at)}.
        </p>
        <p>
          Надомест за подготовка: <span className="font-semibold">{formatMkd(payment.prep_fee_mkd)}</span> (без ДДВ)
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
          <PayeeRow label="Цел на дознаката" value={`Фактура бр. ${payment.invoice_number ?? '—'}`} />
          <PayeeRow label="Износ" value={`${formatMkd(payment.prep_fee_mkd)} (без ДДВ)`} />
        </dl>
        <p className="text-muted-foreground">{PAYMENT_INSTRUCTIONS}</p>
        {!payment.invoice_file_name && (
          <p className="text-muted-foreground">
            Ако ви треба фактурата како документ, пишете ни во пораките подолу и ќе ви ја испратиме.
          </p>
        )}
        <p className="font-medium text-amber-700 dark:text-amber-300">Чекаме уплата.</p>
        <p className="text-muted-foreground">{PAYMENT_NEXT_STEP}</p>
      </div>
    );
  } else if (status === 'requested') {
    main = (
      <div className="space-y-2">
        <p>Ја проверуваме понудата и ќе ви издадеме фактура.</p>
        <p>
          Надомест за подготовка: <span className="font-semibold">{formatMkd(payment.prep_fee_mkd)}</span> (без ДДВ)
        </p>
      </div>
    );
  }

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
        {payment.success_fee_pct !== null && (
          <p className="text-muted-foreground">
            При доделена набавка: {payment.success_fee_pct}% од вредноста на договорот за првата година.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
