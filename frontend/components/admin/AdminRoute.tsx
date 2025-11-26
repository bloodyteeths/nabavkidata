'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

interface AdminRouteProps {
  children: React.ReactNode;
}

export default function AdminRoute({ children }: AdminRouteProps) {
  const router = useRouter();
  const { user, isLoading, isAuthenticated } = useAuth();
  const [authChecked, setAuthChecked] = useState(false);

  // Check if user has admin role
  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    // Wait for auth to fully load
    if (isLoading) return;

    // Give a moment for user data to be fully populated
    const timer = setTimeout(() => {
      // Not authenticated - redirect to login
      if (!isAuthenticated || !user) {
        router.push('/auth/login?redirect=/admin');
        return;
      }

      // Authenticated but not admin - redirect to 403
      if (user.role !== 'admin') {
        console.log('User role:', user.role, 'Full user:', user);
        router.push('/403');
        return;
      }

      // All checks passed
      setAuthChecked(true);
    }, 100);

    return () => clearTimeout(timer);
  }, [isLoading, isAuthenticated, user, router]);

  // Show loading while checking auth
  if (isLoading || !authChecked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mb-4"></div>
          <p className="text-gray-600 text-lg">Проверка на пристап...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
