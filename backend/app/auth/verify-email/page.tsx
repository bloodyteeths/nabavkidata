'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';

export const dynamic = 'force-dynamic';

export default function VerifyEmailPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { verifyEmail, resendVerification } = useAuth();
  const [status, setStatus] = useState<'verifying' | 'success' | 'error' | 'waiting'>('waiting');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const token = searchParams.get('token');

    if (token) {
      verifyToken(token);
    }
  }, [searchParams]);

  const verifyToken = async (token: string) => {
    setStatus('verifying');
    setMessage('Се верификува вашата е-пошта...');

    try {
      await verifyEmail(token);
      setStatus('success');
      setMessage('Вашата е-пошта е успешно верификувана!');

      setTimeout(() => {
        router.push('/auth/login');
      }, 3000);
    } catch (error) {
      setStatus('error');
      setMessage('Токенот е невалиден или истечен. Ве молиме побарајте нов.');
    }
  };

  const handleResendVerification = async () => {
    setLoading(true);
    setMessage('');

    try {
      await resendVerification();
      setMessage('Нова верификациска порака е испратена на вашата е-пошта.');
      setStatus('waiting');
    } catch (error) {
      setMessage('Грешка при испраќање на верификацијата. Обидете се повторно.');
      setStatus('error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="mx-auto w-16 h-16 mb-4">
            {status === 'verifying' && (
              <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
            )}
            {status === 'success' && (
              <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
            )}
            {status === 'error' && (
              <div className="w-16 h-16 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
            )}
            {status === 'waiting' && (
              <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center">
                <svg className="w-8 h-8 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
            )}
          </div>
          <CardTitle className="text-center">
            {status === 'verifying' && 'Верификација во тек'}
            {status === 'success' && 'Успешна верификација'}
            {status === 'error' && 'Грешка при верификација'}
            {status === 'waiting' && 'Верификација на е-пошта'}
          </CardTitle>
          <CardDescription className="text-center">
            {message || 'Проверете ја вашата е-пошта за верификациски линк'}
          </CardDescription>
        </CardHeader>

        {(status === 'error' || status === 'waiting') && (
          <CardContent className="space-y-4">
            {status === 'waiting' && (
              <div className="bg-blue-50 dark:bg-blue-950 p-4 rounded-md">
                <p className="text-sm text-blue-900 dark:text-blue-200">
                  Испратена е верификациска порака на вашата е-пошта. Кликнете на линкот во пораката за да ја верификувате вашата е-пошта.
                </p>
              </div>
            )}

            <div className="text-center">
              <p className="text-sm text-muted-foreground mb-4">
                Неја добивте пораката?
              </p>
              <Button
                onClick={handleResendVerification}
                disabled={loading}
                variant="outline"
                className="w-full"
              >
                {loading ? 'Се испраќа...' : 'Испрати повторно'}
              </Button>
            </div>
          </CardContent>
        )}

        {status === 'success' && (
          <CardContent>
            <div className="bg-green-50 dark:bg-green-950 p-4 rounded-md">
              <p className="text-sm text-green-900 dark:text-green-200 text-center">
                Ве пренасочуваме кон страната за најава...
              </p>
            </div>
          </CardContent>
        )}

        <CardFooter className="flex justify-center">
          <Link href="/auth/login" className="text-sm text-primary hover:underline">
            Врати се на најава
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}
