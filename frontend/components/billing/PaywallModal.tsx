'use client';

import { useEffect, useState } from 'react';
import { UpgradePrompt } from './UpgradePrompt';

export function PaywallModal() {
  const [show, setShow] = useState(false);
  const [feature, setFeature] = useState('premium');
  const [tierRequired, setTierRequired] = useState('starter');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      setFeature(detail.feature || 'premium');
      setTierRequired(detail.tierRequired || 'starter');
      setMessage(detail.message || '');
      setShow(true);
    };
    window.addEventListener('paywall-required', handler);
    return () => window.removeEventListener('paywall-required', handler);
  }, []);

  if (!show) return null;

  return (
    <UpgradePrompt
      feature={feature}
      currentTier="free"
      tierRequired={tierRequired}
      message={message}
      onClose={() => setShow(false)}
      variant="modal"
    />
  );
}
