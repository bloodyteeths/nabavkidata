'use client';

import { useEffect } from 'react';
import { useSearchParams } from 'next/navigation';

/**
 * Captures ?ref=CODE from URL and stores in localStorage.
 * Must be wrapped in <Suspense> when used (useSearchParams requirement).
 */
export default function ReferralCapture() {
  const searchParams = useSearchParams();

  useEffect(() => {
    const ref = searchParams.get('ref');
    if (ref && ref.length > 0) {
      localStorage.setItem('referral_code', ref);
    }
  }, [searchParams]);

  return null;
}
