'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { CreditCard } from 'lucide-react';
import { api } from '@/lib/api';
import type { BillingStatus } from '@/lib/bid-service-types';

/**
 * Asks the client to authorise the success fee (save a card, or arrange
 * payment by invoice) while it is not authorised. Without it we cannot publish
 * the finished bid documents (publish gate), so the client must know before
 * the documents are ready. Renders nothing once authorised or when no success
 * fee applies.
 */
export default function SuccessFeeAuthBanner({ className }: { className?: string }) {
  const [status, setStatus] = useState<BillingStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getServiceBillingStatus()
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch(() => {
        /* non-critical: the billing page shows the same state */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!status || status.success_fee_authorised || !((status.success_fee_pct ?? 0) > 0)) return null;

  return (
    <Link
      href="/portal/billing"
      className={
        'flex items-start gap-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 ' +
        'transition-colors hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100 ' +
        'dark:hover:bg-amber-950/60 ' +
        (className ?? '')
      }
    >
      <CreditCard className="mt-0.5 h-4 w-4 shrink-0" />
      <span>
        Зачувајте картичка за надоместот за успех (се наплаќа само ако победите, најрано седум дена по нашата
        најава) или договорете плаќање по фактура. Без тоа не можеме да ви ги објавиме готовите документи.{' '}
        <span className="font-medium underline underline-offset-2">Отвори „Плаќање“</span>
      </span>
    </Link>
  );
}
