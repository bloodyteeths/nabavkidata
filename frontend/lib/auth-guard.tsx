'use client';

import { useEffect, ReactNode } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

interface AuthGuardProps {
  children: ReactNode;
  requireAuth?: boolean;
  requireRoles?: string[];
  fallbackUrl?: string;
}

/**
 * Client-side authentication guard component
 * Wraps pages that require authentication and/or specific roles
 *
 * Usage:
 * <AuthGuard requireAuth requireRoles={['admin']}>
 *   <YourComponent />
 * </AuthGuard>
 */
export function AuthGuard({
  children,
  requireAuth = true,
  requireRoles = [],
  fallbackUrl = '/auth/login'
}: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isLoading, isAuthenticated } = useAuth();

  useEffect(() => {
    // Wait for auth to load
    if (isLoading) return;

    // Check authentication requirement
    if (requireAuth && !isAuthenticated) {
      const loginUrl = `${fallbackUrl}?redirect=${encodeURIComponent(pathname)}`;
      router.push(loginUrl);
      return;
    }

    // Check role requirements
    if (requireRoles.length > 0 && user) {
      const userRole = user.subscription_tier.toLowerCase();
      const hasRequiredRole = requireRoles.some(role =>
        role.toLowerCase() === userRole || userRole === 'admin'
      );

      if (!hasRequiredRole) {
        router.push('/403');
        return;
      }
    }
  }, [isLoading, isAuthenticated, user, requireAuth, requireRoles, router, pathname, fallbackUrl]);

  // Show loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Show nothing if not authenticated (will redirect)
  if (requireAuth && !isAuthenticated) {
    return null;
  }

  // Show nothing if role check fails (will redirect)
  if (requireRoles.length > 0 && user) {
    const userRole = user.subscription_tier.toLowerCase();
    const hasRequiredRole = requireRoles.some(role =>
      role.toLowerCase() === userRole || userRole === 'admin'
    );

    if (!hasRequiredRole) {
      return null;
    }
  }

  // Render children if all checks pass
  return <>{children}</>;
}

/**
 * Higher-order component to protect pages
 *
 * Usage:
 * export default withAuth(YourComponent, { requireRoles: ['admin'] });
 */
export function withAuth<P extends object>(
  Component: React.ComponentType<P>,
  options: {
    requireAuth?: boolean;
    requireRoles?: string[];
    fallbackUrl?: string;
  } = {}
) {
  return function WithAuthComponent(props: P) {
    return (
      <AuthGuard {...options}>
        <Component {...props} />
      </AuthGuard>
    );
  };
}

/**
 * Hook to check if user has specific role
 */
export function useRole(requiredRole: string): boolean {
  const { user } = useAuth();

  if (!user) return false;

  const userRole = user.subscription_tier.toLowerCase();
  return userRole === requiredRole.toLowerCase() || userRole === 'admin';
}

/**
 * Hook to check if user has any of the specified roles
 */
export function useRoles(requiredRoles: string[]): boolean {
  const { user } = useAuth();

  if (!user || requiredRoles.length === 0) return false;

  const userRole = user.subscription_tier.toLowerCase();
  return requiredRoles.some(role =>
    role.toLowerCase() === userRole || userRole === 'admin'
  );
}

/**
 * Hook to check if user is admin
 */
export function useIsAdmin(): boolean {
  return useRole('admin');
}
