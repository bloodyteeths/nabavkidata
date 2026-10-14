'use client';

import { useEffect, type ReactNode } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import { canAccessPortal } from '@/lib/portal';

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

  return <>{children}</>;
}
