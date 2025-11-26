'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useAuth } from '@/lib/auth';

export default function AuthCallbackPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { setTokens } = useAuth();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const accessToken = searchParams.get('access_token');
    const refreshToken = searchParams.get('refresh_token');
    const errorParam = searchParams.get('error');

    if (errorParam) {
      setError(getErrorMessage(errorParam));
      setTimeout(() => router.push('/auth/login'), 3000);
      return;
    }

    if (accessToken && refreshToken) {
      // Store tokens
      localStorage.setItem('auth_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);

      // Trigger auth state update if setTokens is available
      if (setTokens) {
        setTokens(accessToken, refreshToken);
      }

      // Redirect to dashboard
      router.push('/dashboard');
    } else {
      setError('Недостасуваат токени за автентикација');
      setTimeout(() => router.push('/auth/login'), 3000);
    }
  }, [searchParams, router, setTokens]);

  const getErrorMessage = (error: string): string => {
    switch (error) {
      case 'google_auth_failed':
        return 'Грешка при најава со Google. Обидете се повторно.';
      case 'email_required':
        return 'Потребна е е-пошта за регистрација.';
      default:
        return 'Грешка при автентикација.';
    }
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="mx-auto w-12 h-12 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <CardTitle className="text-center text-red-600">{error}</CardTitle>
          </CardHeader>
          <CardContent className="text-center text-muted-foreground">
            Ве пренасочуваме кон страницата за најава...
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="mx-auto w-12 h-12 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center mb-4">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          </div>
          <CardTitle className="text-center">Се најавувате...</CardTitle>
        </CardHeader>
        <CardContent className="text-center text-muted-foreground">
          Ве молиме почекајте додека ја завршиме автентикацијата.
        </CardContent>
      </Card>
    </div>
  );
}
