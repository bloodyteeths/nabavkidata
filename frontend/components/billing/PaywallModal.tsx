'use client';

import { useCallback, useEffect, useState } from 'react';
import { UpgradePrompt } from './UpgradePrompt';

interface PaywallEventDetail {
  feature?: string;
  message?: string;
  tierRequired?: string;
  status?: number;
}

/**
 * Global service prompt. Opens on any 'paywall-required' event dispatched by
 * lib/api.ts (402/403 upgrade responses) and points the user to the
 * done-for-you service instead of a paid plan. AI tools, price analytics and
 * alerts are perks included for clients we write bids for (account_type
 * managed_client); the copy itself lives in UpgradePrompt (SERVICE_PRICE_NOTE).
 */
export function PaywallModal() {
  const [show, setShow] = useState(false);
  const [feature, setFeature] = useState('premium');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = ((e as CustomEvent<PaywallEventDetail>).detail ?? {}) as PaywallEventDetail;
      setFeature(detail.feature || 'premium');
      setMessage(typeof detail.message === 'string' ? detail.message : '');
      setShow(true);
    };
    window.addEventListener('paywall-required', handler);
    return () => window.removeEventListener('paywall-required', handler);
  }, []);

  const close = useCallback(() => setShow(false), []);

  if (!show) return null;

  return (
    <UpgradePrompt
      feature={feature}
      currentTier="free"
      message={message}
      onClose={close}
      variant="modal"
    />
  );
}
