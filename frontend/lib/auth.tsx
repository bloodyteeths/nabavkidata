'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';

const API_URL = (typeof window !== 'undefined')
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : 'https://api.nabavkidata.com';

export interface User {
  user_id: string;
  email: string;
  full_name?: string;
  email_verified: boolean;
  subscription_tier: string;
  role?: string;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string, referralCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  verifyEmail: (token: string) => Promise<void>;
  resendVerification: (email?: string) => Promise<void>;
  requestPasswordReset: (email: string) => Promise<void>;
  resetPassword: (token: string, newPassword: string) => Promise<void>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
  setTokens: (accessToken: string, refreshToken: string) => Promise<void>;
  error: string | null;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';
const TOKEN_EXPIRY_KEY = 'token_expiry';

// Token refresh interval (5 minutes before expiry)
const REFRESH_BUFFER_MS = 5 * 60 * 1000;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isHydrated, setIsHydrated] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshTimer, setRefreshTimer] = useState<NodeJS.Timeout | null>(null);
  const router = useRouter();

  // Get tokens from localStorage
  const getTokens = (): { accessToken: string | null; refreshToken: string | null } => {
    if (typeof window === 'undefined') {
      return { accessToken: null, refreshToken: null };
    }
    return {
      accessToken: localStorage.getItem(TOKEN_KEY),
      refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY),
    };
  };

  // Store tokens in localStorage and cookies
  const storeTokens = (tokens: AuthTokens) => {
    if (typeof window === 'undefined') return;

    localStorage.setItem(TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);

    // JWT access tokens are valid for 7 days (matching backend config)
    const expiryTime = Date.now() + 7 * 24 * 60 * 60 * 1000;
    localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString());

    // Also set cookie for middleware authentication
    const expires = new Date(expiryTime).toUTCString();
    document.cookie = `auth_token=${tokens.access_token}; path=/; expires=${expires}; SameSite=Lax`;
  };

  // Clear tokens from localStorage and cookies
  const clearTokens = () => {
    if (typeof window === 'undefined') return;

    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);

    // Also clear the cookie
    document.cookie = 'auth_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  };

  // Schedule automatic token refresh
  const scheduleTokenRefresh = () => {
    if (typeof window === 'undefined') return;

    const expiryStr = localStorage.getItem(TOKEN_EXPIRY_KEY);
    if (!expiryStr) return;

    const expiry = parseInt(expiryStr, 10);
    const timeUntilRefresh = expiry - Date.now() - REFRESH_BUFFER_MS;

    if (timeUntilRefresh > 0) {
      const timer = setTimeout(() => {
        refreshTokenSilently();
      }, timeUntilRefresh);

      setRefreshTimer(timer);
    } else {
      // Token is about to expire or already expired, refresh now
      refreshTokenSilently();
    }
  };

  // Refresh token silently
  const refreshTokenSilently = async () => {
    try {
      const { refreshToken: token } = getTokens();
      if (!token) {
        // No refresh token - just clear state silently, don't redirect
        clearTokens();
        setUser(null);
        setIsLoading(false);
        return;
      }

      const response = await fetch(`${API_URL}/api/auth/refresh?refresh_token=${encodeURIComponent(token)}`, {
        method: 'POST',
      });

      if (!response.ok) {
        // Token refresh failed - clear state silently without redirect
        // User will be prompted to login when they try to access protected content
        console.warn('Token refresh failed, clearing session');
        clearTokens();
        setUser(null);
        setIsLoading(false);
        return;
      }

      const tokens: AuthTokens = await response.json();
      storeTokens(tokens);
      scheduleTokenRefresh();
    } catch (err) {
      console.error('Silent token refresh failed:', err);
      // Clear state silently without redirect to prevent page crash
      clearTokens();
      setUser(null);
      setIsLoading(false);
    }
  };

  // Fetch current user data
  const fetchUser = async () => {
    try {
      const { accessToken } = getTokens();
      if (!accessToken) {
        setIsLoading(false);
        return;
      }

      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
        scheduleTokenRefresh();
      } else if (response.status === 401) {
        // Check if session was kicked (logged in from another device)
        const sessionKicked = response.headers.get('X-Session-Kicked');
        const errorData = await response.json().catch(() => ({}));

        if (sessionKicked === 'true' || errorData.detail?.includes('another device')) {
          // Session was invalidated - user logged in elsewhere
          clearTokens();
          setUser(null);
          setError('Вашата сесија е прекината бидејќи се најавивте од друг уред.');
          router.push('/auth/login?kicked=true');
        } else {
          // Try to refresh token
          await refreshTokenSilently();
        }
      } else {
        clearTokens();
      }
    } catch (err) {
      console.error('Failed to fetch user:', err);
      clearTokens();
    } finally {
      setIsLoading(false);
    }
  };

  // Hydration guard - wait for client before accessing localStorage
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Initialize auth state on mount (only after hydration)
  useEffect(() => {
    if (!isHydrated) return;

    fetchUser();

    return () => {
      if (refreshTimer) {
        clearTimeout(refreshTimer);
      }
    };
  }, [isHydrated]);

  const login = async (email: string, password: string) => {
    try {
      setIsLoading(true);
      setError(null);

      // Login endpoint expects OAuth2 form data (username + password), not JSON
      const formData = new URLSearchParams();
      formData.append('username', email);  // OAuth2 uses 'username' field for email
      formData.append('password', password);

      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }

      const data = await response.json();
      // Backend returns { access_token, refresh_token, token_type, user }
      storeTokens({
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        token_type: data.token_type
      });
      // Set user from response instead of fetching again
      setUser(data.user);
      scheduleTokenRefresh();
      router.push('/');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, password: string, fullName?: string, referralCode?: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const body: Record<string, string | undefined> = {
        email,
        password,
        full_name: fullName,
      };
      if (referralCode) body.referral_code = referralCode;

      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Registration failed');
      }

      // Store email for resend verification
      localStorage.setItem('pending_verification_email', email);

      // Redirect to verify email page
      router.push('/auth/verify-email');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      setIsLoading(true);
      const { accessToken } = getTokens();

      if (accessToken) {
        await fetch(`${API_URL}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
          },
        });
      }
    } catch (err) {
      console.error('Logout error:', err);
    } finally {
      clearTokens();
      setUser(null);
      setIsLoading(false);
      if (refreshTimer) {
        clearTimeout(refreshTimer);
      }
      router.push('/auth/login');
    }
  };

  const refreshToken = async () => {
    await refreshTokenSilently();
  };

  const verifyEmail = async (token: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${API_URL}/api/auth/verify-email`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Email verification failed');
      }

      await fetchUser();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Email verification failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const resendVerification = async (email?: string) => {
    try {
      setIsLoading(true);
      setError(null);

      // Try to get email from user state, parameter, or localStorage
      const userEmail = email || user?.email || localStorage.getItem('pending_verification_email');

      if (!userEmail) {
        throw new Error('Email address is required');
      }

      const response = await fetch(`${API_URL}/api/auth/resend-verification`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: userEmail }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to resend verification email');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to resend verification email';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const requestPasswordReset = async (email: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${API_URL}/api/auth/forgot-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Password reset request failed');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Password reset request failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const resetPassword = async (token: string, newPassword: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${API_URL}/api/auth/reset-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ token, new_password: newPassword }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Password reset failed');
      }

      router.push('/auth/login');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Password reset failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const changePassword = async (oldPassword: string, newPassword: string) => {
    try {
      setIsLoading(true);
      setError(null);
      const { accessToken } = getTokens();

      if (!accessToken) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(`${API_URL}/api/auth/change-password`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Password change failed');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Password change failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const updateProfile = async (data: Partial<User>) => {
    try {
      setIsLoading(true);
      setError(null);
      const { accessToken } = getTokens();

      if (!accessToken) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(`${API_URL}/api/auth/me`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Profile update failed');
      }

      const updatedUser = await response.json();
      setUser(updatedUser);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Profile update failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const clearError = () => {
    setError(null);
  };

  // Set tokens from OAuth callback
  const setTokensFromOAuth = async (accessToken: string, refreshTokenStr: string) => {
    if (typeof window === 'undefined') return;

    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshTokenStr);

    // Set expiry (7 days for access tokens, matching backend JWT config)
    const expiryTime = Date.now() + 7 * 24 * 60 * 60 * 1000;
    localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString());

    // Also set cookie for middleware authentication
    const expires = new Date(expiryTime).toUTCString();
    document.cookie = `auth_token=${accessToken}; path=/; expires=${expires}; SameSite=Lax`;

    // Fetch user profile
    await fetchUser();
  };

  const value: AuthContextType = {
    user,
    isLoading,
    isAuthenticated: !!user,
    login,
    register,
    logout,
    refreshToken,
    verifyEmail,
    resendVerification,
    requestPasswordReset,
    resetPassword,
    changePassword,
    updateProfile,
    setTokens: setTokensFromOAuth,
    error,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

// Helper function to get access token (for API client)
export const getAccessToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
};

// Helper function to check if user is authenticated
export const isAuthenticated = (): boolean => {
  if (typeof window === 'undefined') return false;
  return !!localStorage.getItem(TOKEN_KEY);
};
