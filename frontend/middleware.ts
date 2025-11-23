import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Define protected routes and their required roles
const PROTECTED_ROUTES = {
  '/dashboard': ['user', 'admin'],
  '/billing': ['user', 'admin'],
  '/settings': ['user', 'admin'],
  '/chat': ['user', 'admin'],
  '/competitors': ['user', 'admin'],
  '/inbox': ['user', 'admin'],
  '/admin': ['admin'],
} as const;

// Public routes that don't require authentication
const PUBLIC_ROUTES = [
  '/',
  '/auth/login',
  '/auth/register',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
  '/tenders',
  '/privacy',
  '/terms',
  '/403',
];

// Helper function to check if a path matches a route pattern
function matchesRoute(path: string, pattern: string): boolean {
  if (pattern === path) return true;
  if (pattern.endsWith('*')) {
    const basePattern = pattern.slice(0, -1);
    return path.startsWith(basePattern);
  }
  // Check if path starts with the pattern
  return path.startsWith(pattern + '/') || path === pattern;
}

// Helper function to check if route is public
function isPublicRoute(path: string): boolean {
  return PUBLIC_ROUTES.some(route => matchesRoute(path, route));
}

// Helper function to get required roles for a route
function getRequiredRoles(path: string): readonly string[] | null {
  for (const [route, roles] of Object.entries(PROTECTED_ROUTES)) {
    if (matchesRoute(path, route)) {
      return roles;
    }
  }
  return null;
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public routes
  if (isPublicRoute(pathname)) {
    return NextResponse.next();
  }

  // Check for authentication token
  const token = request.cookies.get('auth_token')?.value;

  if (!token) {
    // No token found, redirect to login
    const loginUrl = new URL('/auth/login', request.url);
    loginUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Check role-based access
  const requiredRoles = getRequiredRoles(pathname);

  if (requiredRoles) {
    // For now, we'll verify the token on the client side
    // In production, you might want to decode the JWT here
    // Note: This is a basic check - the backend is the source of truth

    // Admin routes require admin role
    if (pathname.startsWith('/admin')) {
      // The actual role check happens on the backend
      // This middleware just ensures authentication
      return NextResponse.next();
    }
  }

  // Allow authenticated users to proceed
  return NextResponse.next();
}

// Configure which routes this middleware runs on
export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public files (public folder)
     */
    '/((?!_next/static|_next/image|favicon.ico|.*\\.png|.*\\.jpg|.*\\.jpeg|.*\\.gif|.*\\.svg|.*\\.ico).*)',
  ],
};
