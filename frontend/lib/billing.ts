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
  price_monthly_eur?: number;
  price_yearly_eur?: number;
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

export interface TrialCredit {
  total: number;
  used: number;
  remaining: number;
}

export interface TrialCredits {
  ai_messages?: TrialCredit;
  doc_extractions?: TrialCredit;
  exports?: TrialCredit;
  competitor_alerts?: TrialCredit;
}

export interface UserSubscriptionStatus {
  tier: string;
  status: string;
  trial?: {
    eligible: boolean;
    active: boolean;
    days_remaining: number;
    ends_at?: string;
    credits?: TrialCredits;
  };
  plan?: {
    name: string;
    features: string[];
    limits: Record<string, number | boolean>;
  };
  daily_queries_used: number;
  daily_queries_limit: number;
  is_blocked: boolean;
  block_reason?: string;
}

export interface UseCreditResult {
  allowed: boolean;
  remaining: number;
  upgrade_required: boolean;
  message?: string;
}

export interface FeatureCheckResult {
  feature: string;
  allowed: boolean;
  current_tier: string;
  tier_required?: string;
  upgrade_url?: string;
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
        name: 'Бесплатен',
        price_monthly_mkd: 0,
        price_yearly_mkd: 0,
        price_monthly_id: '',
        price_yearly_id: '',
        daily_queries: 3,
        trial_days: 7,
        allow_vpn: false,
        features: [
          '3 AI прашања дневно',
          'Основно пребарување',
          'Преглед на тендери'
        ]
      },
      {
        tier: 'starter',
        name: 'Стартуј',
        price_monthly_mkd: 1990,
        price_yearly_mkd: 19900,
        price_monthly_eur: 39,
        price_yearly_eur: 390,
        price_monthly_id: 'price_1Si1UMHkVI5icjTlgX63qyG6',
        price_yearly_id: 'price_1Si1UMHkVI5icjTlrze0oUdX',
        daily_queries: 15,
        trial_days: 7,
        allow_vpn: true,
        features: [
          '15 AI прашања дневно',
          '10 зачувани известувања',
          'CSV извоз',
          '5 известувања за конкуренти'
        ]
      },
      {
        tier: 'professional',
        name: 'Про',
        price_monthly_mkd: 5990,
        price_yearly_mkd: 59900,
        price_monthly_eur: 99,
        price_yearly_eur: 990,
        price_monthly_id: 'price_1Si1UNHkVI5icjTlaKDnWZuE',
        price_yearly_id: 'price_1Si1UNHkVI5icjTlRiW5safT',
        daily_queries: 50,
        trial_days: 7,
        allow_vpn: true,
        features: [
          '50 AI прашања дневно',
          '50 зачувани известувања',
          'CSV извоз',
          'Анализа на ризик',
          '20 известувања за конкуренти'
        ]
      },
      {
        tier: 'enterprise',
        name: 'Претпријатие',
        price_monthly_mkd: 12990,
        price_yearly_mkd: 129900,
        price_monthly_eur: 199,
        price_yearly_eur: 1990,
        price_monthly_id: 'price_1Si1UNHkVI5icjTlJrHnLL7K',
        price_yearly_id: 'price_1Si1UOHkVI5icjTlhmTPVZSv',
        daily_queries: -1, // Unlimited
        trial_days: 7,
        allow_vpn: true,
        features: [
          'Неограничени AI прашања',
          'Неограничени известувања',
          'Неограничен CSV извоз',
          'Анализа на ризик',
          'API пристап',
          'До 10 членови на тим',
          'Неограничени конкуренти'
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
   * @param currency - mkd or eur
   */
  async createCheckoutSession(tier: string, interval: 'monthly' | 'yearly' = 'monthly', currency: 'mkd' | 'eur' = 'mkd'): Promise<CheckoutSession> {
    const response = await this.request<CheckoutSession>('/api/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ tier, interval, currency }),
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

  /**
   * Use a trial credit for a specific action
   * Call before performing AI, export, or other limited actions
   */
  async useCredit(creditType: 'ai_messages' | 'doc_extractions' | 'exports' | 'competitor_alerts'): Promise<UseCreditResult> {
    return this.request<UseCreditResult>('/api/billing/use-credit', {
      method: 'POST',
      body: JSON.stringify({ credit_type: creditType }),
    });
  }

  /**
   * Check if user has access to a specific feature
   */
  async checkFeature(feature: string): Promise<FeatureCheckResult> {
    return this.request<FeatureCheckResult>(`/api/billing/check-feature/${feature}`);
  }
}

export const billing = new BillingService();
