'use client';

import { useEffect, useState, type ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { api } from '@/lib/api';
import { canAccessPortal } from '@/lib/portal';

/**
 * Accounts created by /usluga are signed in straight away but stay unverified
 * until the set-password link is used. Tender alert emails go only to verified
 * addresses, so tell the client and let them request the link again.
 */
function VerifyEmailBanner({ email }: { email: string }) {
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const send = async () => {
    setState('sending');
    try {
      await api.authForgotPassword(email);
      setState('sent');
    } catch {
      setState('error');
    }
  };
  return (
    <div className="mb-4 rounded-md border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100">
      <p>
        Поставете лозинка за да ја потврдите е-поштата и да добивате известувања за тендери.
      </p>
      <div className="mt-2">
        {state === 'sent' ? (
          <span>Ви испративме линк за поставување лозинка на {email}.</span>
        ) : (
          <button
            type="button"
            onClick={send}
            disabled={state === 'sending'}
            className="font-medium underline underline-offset-2 disabled:opacity-60"
          >
            {state === 'sending' ? 'Се испраќа…' : 'Испрати ми линк за поставување лозинка'}
          </button>
        )}
        {state === 'error' && (
          <span className="ml-2">Не успеавме да го испратиме линкот. Обидете се повторно подоцна.</span>
        )}
      </div>
    </div>
  );
}

/**
 * Renders the client portal only for bid-service clients (and admins).
 * Anonymous visitors go to login (returning here afterwards); everyone else
 * is sent to the service page. Children never render before the check passes.
 */
export default function PortalGate({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const allowed = canAccessPortal(user);

  useEffect(() => {
    if (isLoading) return;
    if (!user) {
      router.replace('/auth/login?redirect=' + encodeURIComponent(pathname || '/portal'));
    } else if (!allowed) {
      router.replace('/usluga');
    }
  }, [isLoading, user, allowed, pathname, router]);

  if (isLoading || !user || !allowed) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground">
        Се вчитува…
      </div>
    );
  }

  return (
    <>
      {!user.email_verified && user.email && <VerifyEmailBanner email={user.email} />}
      {children}
    </>
  );
}
