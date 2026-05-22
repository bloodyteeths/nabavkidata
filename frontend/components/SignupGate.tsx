'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { useAuth } from '@/lib/auth';
import { Lock, ArrowRight } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface SignupGateProps {
  children: ReactNode;
  teaser?: ReactNode;
  message?: string;
  feature?: string;
}

export function SignupGate({ children, teaser, message, feature }: SignupGateProps) {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="relative">
        <div className="blur-sm pointer-events-none select-none" aria-hidden="true">
          {teaser || children}
        </div>
      </div>
    );
  }

  if (user) {
    return <>{children}</>;
  }

  const redirectPath = typeof window !== 'undefined' ? window.location.pathname : '/';

  return (
    <div className="relative">
      <div className="blur-[6px] pointer-events-none select-none" aria-hidden="true">
        {teaser || children}
      </div>
      <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-b from-transparent via-white/60 to-white/90 dark:via-gray-900/60 dark:to-gray-900/90">
        <div className="text-center px-6 py-8 max-w-md">
          <div className="mx-auto w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-4">
            <Lock className="w-6 h-6 text-blue-600 dark:text-blue-400" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            {message || 'Регистрирајте се за да ги видите деталите'}
          </h3>
          <ul className="text-sm text-gray-500 dark:text-gray-400 mb-6 text-left space-y-1.5">
            <li className="flex items-center gap-2">
              <span className="text-green-500 font-bold">&#10003;</span>
              Бесплатна регистрација — без кредитна картичка
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-500 font-bold">&#10003;</span>
              290,000+ тендери и 19,000+ добавувачи
            </li>
            <li className="flex items-center gap-2">
              <span className="text-green-500 font-bold">&#10003;</span>
              AI анализа, аларми и ценовна интелигенција
            </li>
          </ul>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link href={`/auth/register?redirect=${encodeURIComponent(redirectPath)}`}>
              <Button className="w-full sm:w-auto bg-blue-600 hover:bg-blue-700">
                Регистрирајте се бесплатно
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <Link href={`/auth/login?redirect=${encodeURIComponent(redirectPath)}`}>
              <Button variant="outline" className="w-full sm:w-auto">
                Најавете се
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
