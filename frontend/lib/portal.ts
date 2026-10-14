import type { User } from '@/lib/auth';

type U = Pick<User, 'account_type' | 'role'> | null | undefined;

/**
 * Clients of the done-for-you bid service (prospect or managed_client).
 * Drives navigation, post-login redirects and the dashboard bounce.
 * Admins are deliberately excluded so they keep the full tool.
 */
export function isPortalUser(user: U): boolean {
  return user?.account_type === 'prospect' || user?.account_type === 'managed_client';
}

/** Portal access: service clients plus admins. Used by PortalGate and WriteMyBidCard. */
export function canAccessPortal(user: U): boolean {
  return isPortalUser(user) || user?.role?.toLowerCase() === 'admin';
}

/** Where to land after login, honouring a same-origin `redirect` when it is allowed. */
export function postLoginPath(user: U, requested: string | null | undefined): string {
  const safe = requested && requested.startsWith('/') && !requested.startsWith('//') ? requested : null;
  if (!safe || safe === '/dashboard') {
    return isPortalUser(user) ? '/portal' : '/dashboard';
  }
  if (safe.startsWith('/portal') && !canAccessPortal(user)) {
    return '/dashboard';
  }
  return safe;
}
