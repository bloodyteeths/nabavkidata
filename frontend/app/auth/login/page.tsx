'use client';

import { useState, FormEvent, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth';

// Google OAuth icon
const GoogleIcon = () => (
  <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
  </svg>
);

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();

  // Get plan params from URL (from pricing page redirect)
  const plan = searchParams.get('plan');
  const interval = searchParams.get('interval');
  const currency = searchParams.get('currency');

  const [formData, setFormData] = useState({
    email: '',
    password: '',
    rememberMe: false,
  });
  const [errors, setErrors] = useState<{ email?: string; password?: string; general?: string }>({});
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [sessionKicked, setSessionKicked] = useState(false);

  // Check if user was kicked from another device
  useEffect(() => {
    if (searchParams.get('kicked') === 'true') {
      setSessionKicked(true);
    }
  }, [searchParams]);

  const validateForm = () => {
    const newErrors: { email?: string; password?: string } = {};

    if (!formData.email) {
      newErrors.email = 'Е-пошта е задолжителна';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = 'Невалидна е-пошта';
    }

    if (!formData.password) {
      newErrors.password = 'Лозинка е задолжителна';
    } else if (formData.password.length < 6) {
      newErrors.password = 'Лозинката мора да има најмалку 6 карактери';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrors({});

    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      await login(formData.email, formData.password);
      // If user selected a plan, redirect to billing checkout
      if (plan) {
        router.push(`/billing?checkout=true&plan=${plan}&interval=${interval || 'monthly'}&currency=${currency || 'mkd'}`);
      } else {
        // Redirect to the original page or dashboard
        const redirectUrl = searchParams.get('redirect') || '/dashboard';
        router.push(redirectUrl);
      }
    } catch (error: any) {
      setErrors({ general: error.message || 'Погрешна е-пошта или лозинка' });
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    setGoogleLoading(true);
    setErrors({});
    // Store the redirect URL or plan params for after OAuth callback
    if (plan) {
      // Store plan info for checkout after OAuth
      localStorage.setItem('auth_redirect', `/billing?checkout=true&plan=${plan}&interval=${interval || 'monthly'}&currency=${currency || 'mkd'}`);
    } else {
      const redirectUrl = searchParams.get('redirect');
      if (redirectUrl) {
        localStorage.setItem('auth_redirect', redirectUrl);
      }
    }
    // Redirect to backend Google OAuth endpoint
    const apiUrl = window.location.hostname === 'localhost'
      ? 'http://localhost:8000'
      : 'https://api.nabavkidata.com';
    window.location.href = `${apiUrl}/api/auth/google`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">Најава</CardTitle>
          <CardDescription className="text-center">
            Внесете ги вашите податоци за да се најавите
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            {sessionKicked && (
              <div className="p-3 rounded-md bg-amber-100 dark:bg-amber-900 text-amber-800 dark:text-amber-200 text-sm border border-amber-300 dark:border-amber-700">
                <strong>Сесија прекината:</strong> Вашата сесија е прекината бидејќи се најавивте од друг уред. Дозволена е само една активна сесија.
              </div>
            )}
            {errors.general && (
              <div className="p-3 rounded-md bg-destructive/10 text-destructive text-sm">
                {errors.general}
                <div className="mt-2 text-sm">
                  Немате профил?{' '}
                  <Link
                    href={plan ? `/auth/register?plan=${plan}&interval=${interval || 'monthly'}&currency=${currency || 'mkd'}` : '/auth/register'}
                    className="font-medium underline hover:text-destructive/80"
                  >
                    Регистрирајте се бесплатно
                  </Link>
                </div>
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
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                disabled={loading}
                className={errors.email ? 'border-destructive' : ''}
              />
              {errors.email && (
                <p className="text-sm text-destructive">{errors.email}</p>
              )}
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                Лозинка
              </label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                disabled={loading}
                className={errors.password ? 'border-destructive' : ''}
              />
              {errors.password && (
                <p className="text-sm text-destructive">{errors.password}</p>
              )}
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <input
                  id="rememberMe"
                  type="checkbox"
                  checked={formData.rememberMe}
                  onChange={(e) => setFormData({ ...formData, rememberMe: e.target.checked })}
                  disabled={loading}
                  className="h-4 w-4 rounded border-gray-300"
                />
                <label htmlFor="rememberMe" className="text-sm text-gray-700 dark:text-gray-300">
                  Запомни ме
                </label>
              </div>

              <Link
                href="/auth/forgot-password"
                className="text-sm text-primary hover:underline"
              >
                Заборавена лозинка?
              </Link>
            </div>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Се најавувате...' : 'Најави се'}
            </Button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-300 dark:border-gray-600"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-card text-muted-foreground">Или продолжи со</span>
            </div>
          </div>

          {/* Google Login Button */}
          <Button
            variant="outline"
            className="w-full"
            onClick={handleGoogleLogin}
            disabled={googleLoading}
          >
            <GoogleIcon />
            {googleLoading ? 'Се најавувате...' : 'Најави се со Google'}
          </Button>
        </CardContent>
        <CardFooter className="flex justify-center">
          <p className="text-sm text-muted-foreground">
            Немате профил?{' '}
            <Link
              href={plan ? `/auth/register?plan=${plan}&interval=${interval || 'monthly'}&currency=${currency || 'mkd'}` : '/auth/register'}
              className="text-primary hover:underline font-medium"
            >
              Регистрирајте се
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  );
}
