'use client';

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';

export default function ForgotPasswordPage() {
  const { requestPasswordReset } = useAuth();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const validateEmail = () => {
    if (!email) {
      setError('Е-пошта е задолжителна');
      return false;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Невалидна е-пошта');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (!validateEmail()) {
      return;
    }

    setLoading(true);

    try {
      await requestPasswordReset(email);
      setSuccess(true);
    } catch (error) {
      setError('Грешка при испраќање на барањето. Обидете се повторно.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="mx-auto w-12 h-12 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mb-4">
              <svg className="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <CardTitle className="text-center">Барањето е испратено</CardTitle>
            <CardDescription className="text-center">
              Проверете ја вашата е-пошта за инструкции за ресетирање на лозинката.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-blue-50 dark:bg-blue-950 p-4 rounded-md">
              <p className="text-sm text-blue-900 dark:text-blue-200">
                Ако е-поштата <strong>{email}</strong> е регистрирана во нашиот систем, ќе добиете порака со линк за ресетирање на лозинката.
              </p>
            </div>
          </CardContent>
          <CardFooter className="flex justify-center">
            <Link href="/auth/login" className="text-sm text-primary hover:underline">
              Врати се на најава
            </Link>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <div className="mx-auto w-12 h-12 bg-blue-100 dark:bg-blue-900 rounded-full flex items-center justify-center mb-4">
            <svg className="w-6 h-6 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <CardTitle className="text-2xl font-bold text-center">Заборавена лозинка</CardTitle>
          <CardDescription className="text-center">
            Внесете ја вашата е-пошта за да добиете линк за ресетирање на лозинката
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium">
                Е-пошта
              </label>
              <Input
                id="email"
                type="email"
                placeholder="vashe.ime@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                className={error ? 'border-destructive' : ''}
              />
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Се испраќа...' : 'Испрати барање'}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center">
          <Link href="/auth/login" className="text-sm text-primary hover:underline">
            Врати се на најава
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}
