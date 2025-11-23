'use client';

import { useState, useCallback } from 'react';
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

interface AuthState {
  isLoading: boolean;
  error: string | null;
  user: User | null;
}

const API_URL = (typeof window !== 'undefined')
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : (process.env.NEXT_PUBLIC_API_URL || 'https://api.nabavkidata.com');
const TOKEN_KEY = 'auth_token';
const REFRESH_TOKEN_KEY = 'refresh_token';

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    isLoading: false,
    error: null,
    user: null,
  });
  const router = useRouter();

  const setLoading = (isLoading: boolean) => {
    setState((prev) => ({ ...prev, isLoading }));
  };

  const setError = (error: string | null) => {
    setState((prev) => ({ ...prev, error }));
  };

  const setUser = (user: User | null) => {
    setState((prev) => ({ ...prev, user }));
  };

  const getTokens = useCallback(() => {
    if (typeof window === 'undefined') {
      return { accessToken: null, refreshToken: null };
    }
    return {
      accessToken: localStorage.getItem(TOKEN_KEY),
      refreshToken: localStorage.getItem(REFRESH_TOKEN_KEY),
    };
  }, []);

  const storeTokens = useCallback((tokens: AuthTokens) => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(TOKEN_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refresh_token);
  }, []);

  const clearTokens = useCallback(() => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<User> => {
    try {
      setLoading(true);
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
      storeTokens(data);

      // Fetch user data
      const userResponse = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${data.access_token}`,
        },
      });

      if (!userResponse.ok) {
        throw new Error('Failed to fetch user data');
      }

      const user: User = await userResponse.json();
      setUser(user);
      return user;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [storeTokens]);

  const register = useCallback(async (email: string, password: string, fullName?: string): Promise<User> => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_URL}/api/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          email,
          password,
          confirm_password: password,  // Backend requires this field
          full_name: fullName,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Registration failed');
      }

      // Registration successful - returns message, not tokens
      // User needs to verify email (if enabled) and then login
      const data = await response.json();

      // Return a placeholder user object since registration doesn't return user data
      const placeholderUser: User = {
        id: '',
        email: email,
        is_verified: false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      return placeholderUser;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registration failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    try {
      setLoading(true);
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
      setLoading(false);
      router.push('/login');
    }
  }, [getTokens, clearTokens, router]);

  const refreshToken = useCallback(async (): Promise<void> => {
    try {
      setLoading(true);
      setError(null);
      const { refreshToken: token } = getTokens();

      if (!token) {
        throw new Error('No refresh token available');
      }

      const response = await fetch(`${API_URL}/api/auth/refresh`, {
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
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Token refresh failed';
      setError(message);
      clearTokens();
      router.push('/login');
      throw err;
    } finally {
      setLoading(false);
    }
  }, [getTokens, storeTokens, clearTokens, router]);

  const verifyEmail = useCallback(async (token: string): Promise<void> => {
    try {
      setLoading(true);
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
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Email verification failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const resendVerification = useCallback(async (): Promise<void> => {
    try {
      setLoading(true);
      setError(null);
      const { accessToken } = getTokens();

      if (!accessToken) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(`${API_URL}/api/auth/resend-verification`, {
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
      setLoading(false);
    }
  }, [getTokens]);

  const requestPasswordReset = useCallback(async (email: string): Promise<void> => {
    try {
      setLoading(true);
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
      setLoading(false);
    }
  }, []);

  const resetPassword = useCallback(async (token: string, newPassword: string): Promise<void> => {
    try {
      setLoading(true);
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

      router.push('/login');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Password reset failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [router]);

  const changePassword = useCallback(async (oldPassword: string, newPassword: string): Promise<void> => {
    try {
      setLoading(true);
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
      setLoading(false);
    }
  }, [getTokens]);

  const updateProfile = useCallback(async (data: Partial<User>): Promise<User> => {
    try {
      setLoading(true);
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

      const user: User = await response.json();
      return user;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Profile update failed';
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [getTokens]);

  const getCurrentUser = useCallback(async (): Promise<User | null> => {
    try {
      setLoading(true);
      const { accessToken } = getTokens();

      if (!accessToken) {
        setUser(null);
        return null;
      }

      const response = await fetch(`${API_URL}/api/auth/me`, {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch user');
      }

      const user: User = await response.json();
      setUser(user);
      return user;
    } catch (err) {
      console.error('Get current user error:', err);
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, [getTokens]);

  return {
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
    getCurrentUser,
    user: state.user,
    loading: state.isLoading,
    isLoading: state.isLoading,
    error: state.error,
    clearError: () => setError(null),
  };
}
