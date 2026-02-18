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

export interface ReferralStats {
  total_referrals: number;
  active_referrals: number;
  total_earned_cents: number;
  total_paid_out_cents: number;
  pending_balance_cents: number;
  currency: string;
}

export interface ReferralEarning {
  earning_id: string;
  referred_email: string;
  amount_cents: number;
  currency: string;
  created_at: string;
}

export interface ConnectStatus {
  connected: boolean;
  status: string | null;  // null, 'pending', 'active', 'restricted'
  charges_enabled: boolean;
  payouts_enabled: boolean;
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
        daily_queries: 2,
        trial_days: 7,
        allow_vpn: false,
        features: [
          'Преглед на листа тендери',
          'Основно пребарување',
          '2 AI прашања дневно',
          'Без извоз и известувања'
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
        daily_queries: 5,
        trial_days: 7,
        allow_vpn: true,
        features: [
          '5 AI прашања дневно',
          'AI резимеа на тендери',
          'Основна аналитика',
          'Профили на добавувачи',
          'CSV извоз (2/ден)',
          '3 зачувани известувања'
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
        daily_queries: 25,
        trial_days: 7,
        allow_vpn: true,
        features: [
          '25 AI прашања дневно',
          'Анализа на ризик и корупција',
          'AI совети за понуди',
          'Ценовна интелигенција и трендови',
          'CSV и PDF извоз (10/ден)',
          '15 зачувани известувања'
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
        daily_queries: 100,
        trial_days: 7,
        allow_vpn: true,
        features: [
          'Сè од Про планот',
          '100 AI прашања дневно',
          'API пристап (100 повици/ден)',
          'До 5 членови на тим',
          'Неограничени известувања и извоз',
          'Приоритетна поддршка'
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

  // ============================================================================
  // REFERRAL PROGRAM
  // ============================================================================

  async getReferralCode(): Promise<{ code: string; referral_url: string }> {
    return this.request('/api/referrals/my-code');
  }

  async getReferralStats(): Promise<ReferralStats> {
    return this.request('/api/referrals/stats');
  }

  async getReferralEarnings(skip = 0, limit = 20): Promise<{ earnings: ReferralEarning[]; total: number }> {
    return this.request(`/api/referrals/earnings?skip=${skip}&limit=${limit}`);
  }

  async requestPayout(data: { bank_name?: string; account_holder?: string; iban?: string }): Promise<{ message: string }> {
    return this.request('/api/referrals/request-payout', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Stripe Connect
  async startConnectOnboarding(): Promise<{ url: string }> {
    return this.request('/api/referrals/connect/onboard', { method: 'POST' });
  }

  async getConnectStatus(): Promise<ConnectStatus> {
    return this.request('/api/referrals/connect/status');
  }
}

export const billing = new BillingService();
