/**
 * Billing Service
 * Handles all Stripe billing and subscription operations
 */

const API_URL = (typeof window !== 'undefined')
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : 'https://api.nabavkidata.com';

export interface BillingPlan {
  tier: string;
  name: string;
  price_monthly_mkd: number;
  price_yearly_mkd: number;
  price_monthly_id: string;
  price_yearly_id: string;
  daily_queries: number;
  trial_days: number;
  allow_vpn: boolean;
  features: string[];
}

export interface TierLimits {
  tier: string;
  daily_queries: number;
  monthly_queries: number;
  trial_days: number;
  allow_vpn: boolean;
  features: string[];
}

export interface CheckoutSession {
  url: string;
  session_id: string;
}

export interface BillingPortalSession {
  url: string;
}

export interface UserSubscriptionStatus {
  tier: string;
  status: string;
  trial_ends_at?: string;
  is_trial_expired: boolean;
  daily_queries_used: number;
  daily_queries_limit: number;
  is_blocked: boolean;
  block_reason?: string;
}

class BillingService {
  private baseURL: string;

  constructor() {
    this.baseURL = API_URL;
  }

  private getAuthToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('auth_token');
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const token = this.getAuthToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options?.headers as Record<string, string>),
    };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `API Error: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get all available billing plans with MKD pricing
   */
  async getPlans(): Promise<BillingPlan[]> {
    const response = await this.request<{ plans: any[] }>('/api/billing/plans');

    // Transform backend response to frontend format
    return [
      {
        tier: 'free',
        name: 'Free',
        price_monthly_mkd: 0,
        price_yearly_mkd: 0,
        price_monthly_id: '',
        price_yearly_id: '',
        daily_queries: 3,
        trial_days: 14,
        allow_vpn: false,
        features: [
          '3 AI пребарувања дневно',
          '14-дневен пробен период',
          'Основно пребарување',
          'Email поддршка'
        ]
      },
      {
        tier: 'starter',
        name: 'Starter',
        price_monthly_mkd: 899,
        price_yearly_mkd: 8990,
        price_monthly_id: 'price_1SYdj7HkVI5icjTla0nOYXpg',
        price_yearly_id: 'price_1SYdj7HkVI5icjTlpqVwQbQT',
        daily_queries: 5,
        trial_days: 14,
        allow_vpn: true,
        features: [
          '5 AI пребарувања дневно',
          '14-дневен пробен период',
          'Напредни филтри',
          'CSV/PDF експорт',
          'Приоритетна поддршка'
        ]
      },
      {
        tier: 'professional',
        name: 'Professional',
        price_monthly_mkd: 2399,
        price_yearly_mkd: 23990,
        price_monthly_id: 'price_1SYdj8HkVI5icjTlqUWXb8QJ',
        price_yearly_id: 'price_1SYdj8HkVI5icjTl7A9x3Glo',
        daily_queries: 20,
        trial_days: 14,
        allow_vpn: true,
        features: [
          '20 AI пребарувања дневно',
          '14-дневен пробен период',
          'Аналитика',
          'Интеграции',
          'Дедицирана поддршка'
        ]
      },
      {
        tier: 'enterprise',
        name: 'Enterprise',
        price_monthly_mkd: 5999,
        price_yearly_mkd: 59990,
        price_monthly_id: 'price_1SYdj8HkVI5icjTlop9VVjAd',
        price_yearly_id: 'price_1SYdj9HkVI5icjTl1Bq2xtGw',
        daily_queries: -1, // Unlimited
        trial_days: 14,
        allow_vpn: true,
        features: [
          'Неограничени AI пребарувања',
          '14-дневен пробен период',
          'White-label',
          'API пристап',
          '24/7 поддршка'
        ]
      }
    ];
  }

  /**
   * Get tier limits from fraud prevention endpoint
   */
  async getTierLimits(): Promise<Record<string, TierLimits>> {
    return this.request<Record<string, TierLimits>>('/api/fraud/tier-limits');
  }

  /**
   * Create Stripe checkout session
   * @param tier - The subscription tier (free, starter, professional, enterprise)
   * @param interval - monthly or yearly
   */
  async createCheckoutSession(tier: string, interval: 'monthly' | 'yearly' = 'monthly'): Promise<CheckoutSession> {
    const response = await this.request<CheckoutSession>('/api/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ tier, interval }),
    });

    return response;
  }

  /**
   * Open Stripe billing portal for subscription management
   */
  async openBillingPortal(): Promise<BillingPortalSession> {
    const response = await this.request<BillingPortalSession>('/api/billing/portal', {
      method: 'POST',
    });

    return response;
  }

  /**
   * Get current user's subscription status
   */
  async getSubscriptionStatus(): Promise<UserSubscriptionStatus> {
    return this.request<UserSubscriptionStatus>('/api/billing/status');
  }

  /**
   * Get user's current usage statistics
   */
  async getUsage(): Promise<{
    daily_query_count: number;
    monthly_query_count: number;
    total_query_count: number;
    daily_reset_at: string;
    subscription_tier: string;
    is_blocked: boolean;
  }> {
    return this.request('/api/billing/usage');
  }

  /**
   * Cancel subscription
   */
  async cancelSubscription(): Promise<void> {
    await this.request('/api/billing/cancel', {
      method: 'POST',
    });
  }
}

export const billing = new BillingService();
