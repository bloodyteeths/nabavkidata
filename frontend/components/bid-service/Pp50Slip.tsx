'use client';

import { useState } from 'react';
import { Check, Copy, Printer } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { FAKTURINO_PAYEE } from '@/lib/bid-service-types';

interface Pp50SlipProps {
  /** prep fee in MKD (без ДДВ) */
  amountMkd: number;
  invoiceNumber: string;
  tenderId?: string | null;
  /** payer (client) company name, if known */
  payerName?: string | null;
}

function formatAmount(mkd: number): string {
  return mkd.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!));
}

/**
 * Pre-filled ПП50 (налог за плаќање) so a client can pay the prep-fee invoice
 * from e-banking or at the bank counter without retyping our details.
 */
export default function Pp50Slip({ amountMkd, invoiceNumber, tenderId, payerName }: Pp50SlipProps) {
  const [copied, setCopied] = useState<string | null>(null);
  const purpose = `Фактура бр. ${invoiceNumber}${tenderId ? `, подготовка на понуда ${tenderId}` : ''}`;
  const amount = formatAmount(amountMkd);

  const copy = async (key: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(key);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard blocked: the value is visible anyway */
    }
  };

  const fields: Array<{ key: string; label: string; value: string; copyable?: boolean }> = [
    { key: 'recipient', label: 'Назив и седиште на примач', value: FAKTURINO_PAYEE.slipName },
    { key: 'account', label: 'Трансакциска сметка на примач', value: FAKTURINO_PAYEE.bankAccount, copyable: true },
    { key: 'bank', label: 'Банка на примач', value: FAKTURINO_PAYEE.bankName },
    { key: 'amount', label: 'Износ (MKD)', value: amount, copyable: true },
    { key: 'reference', label: 'Повикување на број (одобрување)', value: invoiceNumber, copyable: true },
    { key: 'purpose', label: 'Цел на дознаката', value: purpose, copyable: true },
  ];

  const print = () => {
    const w = window.open('', '_blank', 'width=820,height=900');
    if (!w) return;
    const box = (label: string, value: string) =>
      `<div class="f"><div class="l">${esc(label)}</div><div class="v">${esc(value) || '&nbsp;'}</div></div>`;
    w.document.write(`<!doctype html><html lang="mk"><head><meta charset="utf-8"><title>ПП50 — ${esc(invoiceNumber)}</title>
<style>
body{font-family:Arial,Helvetica,sans-serif;margin:32px;color:#111}
h1{font-size:16px;text-align:right;margin:0 0 18px}
.slip{border:1px solid #111;padding:20px;display:grid;grid-template-columns:1fr 1fr;gap:0 28px}
.col h2{font-size:13px;text-align:right;margin:0 0 8px;font-weight:normal}
.f{margin-bottom:12px}.l{font-size:12px;margin-bottom:3px}.v{border:1px solid #111;min-height:22px;padding:4px 6px;font-size:13px}
.row{display:grid;grid-template-columns:90px 1fr;gap:10px}
.note{font-size:11px;color:#444;margin-top:14px}
@media print{.noprint{display:none}}
</style></head><body>
<h1>НАЛОГ ЗА ПЛАЌАЊЕ — ПП50</h1>
<div class="slip">
<div class="col"><h2>Налогодавач</h2>
${box('Назив и седиште на налогодавач', payerName || '')}
${box('Трансакциска сметка на налогодавач', '')}
${box('Банка на налогодавач', '')}
${box('Повикување на број (задолжување)', '')}
${box('Цел на дознаката', purpose)}
</div>
<div class="col"><h2>Примач</h2>
${box('Назив и седиште на примач', FAKTURINO_PAYEE.slipName)}
${box('Трансакциска сметка на примач', FAKTURINO_PAYEE.bankAccount)}
${box('Банка на примач', FAKTURINO_PAYEE.bankName)}
<div class="row">${box('Валута', 'MKD')}${box('Износ', amount)}</div>
${box('Повикување на број (одобрување)', invoiceNumber)}
${box('Шифра', '')}
</div>
</div>
<p class="note">Износот е без ДДВ: Фактурино ДООЕЛ не е обврзник за ДДВ. Полињата на налогодавачот ги пополнувате вие.</p>
<button class="noprint" onclick="window.print()">Печати</button>
</body></html>`);
    w.document.close();
    w.focus();
    w.print();
  };

  return (
    <div className="rounded-md border bg-muted/40 p-3 text-xs">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="font-medium text-sm">Налог за плаќање (ПП50)</p>
        <Button type="button" size="sm" variant="outline" onClick={print}>
          <Printer className="mr-1.5 h-3.5 w-3.5" />
          Печати налог
        </Button>
      </div>
      <dl className="space-y-1.5">
        {fields.map((f) => (
          <div key={f.key} className="flex items-start justify-between gap-3">
            <dt className="text-muted-foreground shrink-0">{f.label}</dt>
            <dd className="flex items-center gap-1.5 text-right font-medium break-all">
              {f.value}
              {f.copyable && (
                <button
                  type="button"
                  onClick={() => copy(f.key, f.value)}
                  className="text-muted-foreground hover:text-foreground"
                  aria-label={`Копирај: ${f.label}`}
                >
                  {copied === f.key ? <Check className="h-3.5 w-3.5 text-green-600" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
              )}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-muted-foreground">
        Износот е без ДДВ: Фактурино ДООЕЛ не е обврзник за ДДВ.
      </p>
    </div>
  );
}
