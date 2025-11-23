'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';

export interface User {
  id: string;
  email: string;
  full_name?: string;
  avatar_url?: string;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
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
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  verifyEmail: (token: string) => Promise<void>;
  resendVerification: () => Promise<void>;
  requestPasswordReset: (email: string) => Promise<void>;
  resetPassword: (token: string, newPassword: string) => Promise<void>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
  updateProfile: (data: Partial<User>) => Promise<void>;
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

  // Store tokens in localStorage
  const storeTokens = (tokens: AuthTokens) => {
    if (typeof window === 'undefined') return;

    localStorage.setItem(TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);

    // JWT tokens are typically valid for 15-30 minutes
    // Store expiry time (default to 15 minutes)
    const expiryTime = Date.now() + 15 * 60 * 1000;
    localStorage.setItem(TOKEN_EXPIRY_KEY, expiryTime.toString());
  };

  // Clear tokens from localStorage
  const clearTokens = () => {
    if (typeof window === 'undefined') return;

    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
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
        throw new Error('No refresh token available');
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ refresh_token: token }),
      });

      if (!response.ok) {
        throw new Error('Token refresh failed');
      }

      const tokens: AuthTokens = await response.json();
      storeTokens(tokens);
      scheduleTokenRefresh();
    } catch (err) {
      console.error('Silent token refresh failed:', err);
      // If refresh fails, logout user
      await logout();
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

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
        scheduleTokenRefresh();
      } else if (response.status === 401) {
        // Try to refresh token
        await refreshTokenSilently();
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

  // Initialize auth state on mount
  useEffect(() => {
    fetchUser();

    return () => {
      if (refreshTimer) {
        clearTimeout(refreshTimer);
      }
    };
  }, []);

  const login = async (email: string, password: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Login failed');
      }

      const tokens: AuthTokens = await response.json();
      storeTokens(tokens);
      await fetchUser();
      router.push('/');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (email: string, password: string, fullName?: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          full_name: fullName,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Registration failed');
      }

      const tokens: AuthTokens = await response.json();
      storeTokens(tokens);
      await fetchUser();
      router.push('/');
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
        await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/logout`, {
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
      router.push('/login');
    }
  };

  const refreshToken = async () => {
    await refreshTokenSilently();
  };

  const verifyEmail = async (token: string) => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/verify-email`, {
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

  const resendVerification = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const { accessToken } = getTokens();

      if (!accessToken) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/resend-verification`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
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

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/forgot-password`, {
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

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/reset-password`, {
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

      router.push('/login');
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

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/change-password`, {
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

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/me`, {
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
