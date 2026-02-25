'use client';

import { useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function BillingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    // Preserve checkout redirect params when redirecting to settings
    const checkout = searchParams.get('checkout');
    const plan = searchParams.get('plan');
    const interval = searchParams.get('interval');
    const currency = searchParams.get('currency');

    if (checkout && plan) {
      const params = new URLSearchParams({ checkout, plan });
      if (interval) params.set('interval', interval);
      if (currency) params.set('currency', currency);
      router.replace(`/settings?${params.toString()}`);
    } else {
      router.replace('/settings');
    }
  }, [router, searchParams]);

  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Ве пренасочуваме...</p>
      </div>
    </div>
  );
}
