import { redirect } from 'next/navigation';

/**
 * Self-serve registration is closed: NabavkiData is now a done-for-you
 * bid-writing service, and new accounts are created only through the
 * /usluga assessment form (POST /api/bid-service/qualify).
 *
 * Login is untouched: /auth/login, Google OAuth (backend -> /auth/callback)
 * and password reset never pass through this route.
 *
 * Old links (landing CTAs, blog posts, emails with ?ref=...) keep working and
 * land on /usluga with their source tag preserved.
 */
type SearchParams = { [key: string]: string | string[] | undefined };

function first(value: string | string[] | undefined): string | undefined {
  const v = Array.isArray(value) ? value[0] : value;
  return v && v.trim() ? v.trim() : undefined;
}

export default function RegisterPage({ searchParams }: { searchParams: SearchParams }) {
  const params = new URLSearchParams();
  const src = first(searchParams.src) ?? first(searchParams.ref) ?? first(searchParams.utm_source) ?? 'register';
  params.set('src', src);
  const tender = first(searchParams.tender);
  if (tender) params.set('tender', tender);
  redirect(`/usluga?${params.toString()}`);
}
