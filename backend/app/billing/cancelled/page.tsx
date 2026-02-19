'use client';

import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { XCircle, ArrowLeft } from 'lucide-react';

export default function CancelledPage() {
  const router = useRouter();

  return (
    <div className="container mx-auto py-12 px-4 max-w-2xl">
      <Card className="text-center">
        <CardHeader>
          <div className="mx-auto mb-4">
            <XCircle className="h-16 w-16 text-muted-foreground" />
          </div>
          <CardTitle className="text-3xl mb-2">Претплата откажана</CardTitle>
          <CardDescription className="text-lg">
            Вашата претплата не беше завршена
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          <p className="text-muted-foreground">
            Ве разбираме - понекогаш треба повеќе време за да одлучите.
          </p>

          <div className="bg-secondary/50 rounded-lg p-6">
            <h3 className="font-semibold mb-3">Зошто да изберете претплата?</h3>
            <ul className="text-sm text-left space-y-2">
              <li className="flex items-start gap-2">
                <span className="text-primary mt-1">•</span>
                <span>Персонализирани препораки за тендери</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary mt-1">•</span>
                <span>Напредно пребарување и филтрирање</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary mt-1">•</span>
                <span>Известувања по е-пошта за нови можности</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary mt-1">•</span>
                <span>Следење на активноста на конкуренцијата</span>
              </li>
              <li className="flex items-start gap-2">
                <span className="text-primary mt-1">•</span>
                <span>14-дневна гаранција за враќање на пари</span>
              </li>
            </ul>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-4">
            <Button
              onClick={() => router.push('/billing/plans')}
              className="flex-1"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Врати се кон планови
            </Button>
            <Button
              variant="outline"
              onClick={() => router.push('/')}
              className="flex-1"
            >
              Оди на почетна
            </Button>
          </div>

          <p className="text-sm text-muted-foreground pt-4">
            Ако имате прашања, слободно контактирајте не.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
