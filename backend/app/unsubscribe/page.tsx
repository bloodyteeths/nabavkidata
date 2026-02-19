'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import Link from 'next/link';

export default function UnsubscribePage() {
  const searchParams = useSearchParams();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const email = searchParams.get('e');
    const token = searchParams.get('t');

    if (!email || !token) {
      setStatus('error');
      setMessage('Невалиден линк за одјава. Ве молиме контактирајте не на support@nabavkidata.com');
      return;
    }

    // Call unsubscribe API
    const unsubscribe = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.nabavkidata.com';
        const response = await fetch(`${apiUrl}/api/outreach/unsubscribe?e=${encodeURIComponent(email)}&t=${encodeURIComponent(token)}`);

        const data = await response.json();

        if (response.ok && data.success) {
          setStatus('success');
          setMessage(data.message || 'Успешно се одјавивте од маркетинг пораки.');
        } else {
          setStatus('error');
          setMessage(data.detail || data.message || 'Настана грешка при одјавата.');
        }
      } catch (error) {
        setStatus('error');
        setMessage('Настана грешка. Ве молиме обидете се повторно или контактирајте не на support@nabavkidata.com');
      }
    };

    unsubscribe();
  }, [searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">
            {status === 'loading' && 'Обработка...'}
            {status === 'success' && 'Успешна одјава'}
            {status === 'error' && 'Грешка'}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-center space-y-6">
          {status === 'loading' && (
            <div className="flex justify-center">
              <Loader2 className="h-12 w-12 animate-spin text-primary" />
            </div>
          )}

          {status === 'success' && (
            <>
              <div className="flex justify-center">
                <CheckCircle className="h-16 w-16 text-green-500" />
              </div>
              <p className="text-muted-foreground">{message}</p>
              <p className="text-sm text-muted-foreground">
                Нема повеќе да добивате маркетинг е-пошта од NabavkiData.
                Сепак, може да добиете важни трансакциски пораки (доколку имате кориснички профил).
              </p>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="flex justify-center">
                <XCircle className="h-16 w-16 text-destructive" />
              </div>
              <p className="text-muted-foreground">{message}</p>
              <p className="text-sm text-muted-foreground">
                Ако проблемот продолжи, контактирајте не на{' '}
                <a href="mailto:support@nabavkidata.com" className="text-primary hover:underline">
                  support@nabavkidata.com
                </a>
              </p>
            </>
          )}

          <div className="pt-4">
            <Link href="/">
              <Button variant="outline">
                Назад на почетна
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
