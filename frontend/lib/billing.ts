/**
 * Billing Service
 * Handles all Stripe billing and subscription operations
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface BillingPlan {
  tier: string;
  name: string;
  price_monthly_eur: number;
  price_yearly_eur: number;
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
   * Get all available billing plans with EUR pricing
   */
  async getPlans(): Promise<BillingPlan[]> {
    const response = await this.request<{ plans: any[] }>('/api/billing/plans');

    // Transform backend response to frontend format
    return [
      {
        tier: 'free',
        name: 'Free',
        price_monthly_eur: 0,
        price_yearly_eur: 0,
        price_monthly_id: '',
        price_yearly_id: '',
        daily_queries: 3,
        trial_days: 14,
        allow_vpn: false,
        features: [
          '3 AI queries per day',
          '14-day trial period',
          'Basic tender search',
          'Email support'
        ]
      },
      {
        tier: 'starter',
        name: 'Starter',
        price_monthly_eur: 14.99,
        price_yearly_eur: 149.99,
        price_monthly_id: 'price_1SWeAsHkVI5icjTl9GZ8Ciui',
        price_yearly_id: 'price_1SWeAsHkVI5icjTlGRvOP17d',
        daily_queries: 5,
        trial_days: 14,
        allow_vpn: true,
        features: [
          '5 AI queries per day',
          '14-day free trial',
          'Advanced search filters',
          'Export to CSV/PDF',
          'Priority email support'
        ]
      },
      {
        tier: 'professional',
        name: 'Professional',
        price_monthly_eur: 39.99,
        price_yearly_eur: 399.99,
        price_monthly_id: 'price_1SWeAtHkVI5icjTl8UxSYNYX',
        price_yearly_id: 'price_1SWeAuHkVI5icjTlrbC5owFk',
        daily_queries: 20,
        trial_days: 14,
        allow_vpn: true,
        features: [
          '20 AI queries per day',
          '14-day free trial',
          'All Starter features',
          'Advanced analytics',
          'Custom integrations',
          'Dedicated support'
        ]
      },
      {
        tier: 'enterprise',
        name: 'Enterprise',
        price_monthly_eur: 99.99,
        price_yearly_eur: 999.99,
        price_monthly_id: 'price_1SWeAvHkVI5icjTlF8eFK8kh',
        price_yearly_id: 'price_1SWeAvHkVI5icjTlcKi7RFu7',
        daily_queries: -1, // Unlimited
        trial_days: 14,
        allow_vpn: true,
        features: [
          'Unlimited AI queries',
          '14-day free trial',
          'All Professional features',
          'White-label options',
          'API access',
          '24/7 premium support',
          'Custom training'
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
