const API_URL = (typeof window !== 'undefined')
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://www.nabavkidata.com')
  : 'https://api.nabavkidata.com';

export interface Tender {
  tender_id: string;
  title: string;
  description?: string;
  category?: string;
  procuring_entity?: string;
  opening_date?: string;
  closing_date?: string;
  estimated_value_mkd?: number;
  estimated_value_eur?: number;
  cpv_code?: string;
  status?: string;
  created_at: string;
}

export interface RecommendedTender extends Tender {
  score: number;
  match_reasons: string[];
}

export interface CompetitorActivity {
  tender_id: string;
  title: string;
  competitor_name: string;
  status: string;
  estimated_value_mkd?: number;
}

export interface PersonalizedInsight {
  insight_type: string;
  title: string;
  description: string;
  confidence: number;
}

export interface DashboardData {
  recommended_tenders: RecommendedTender[];
  competitor_activity: CompetitorActivity[];
  insights: PersonalizedInsight[];
  stats: Record<string, any>;
}

export interface UserPreferences {
  sectors: string[];
  cpv_codes: string[];
  entities: string[];
  min_budget?: number;
  max_budget?: number;
  exclude_keywords: string[];
  competitor_companies: string[];
  notification_frequency: string;
  email_enabled: boolean;
}

export interface RAGQueryResponse {
  question: string;
  answer: string;
  sources: Array<{
    tender_id?: string;
    doc_id?: string;
    chunk_text: string;
    similarity: number;
  }>;
  confidence: string;
  query_time_ms: number;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  full_name?: string;
  avatar_url?: string;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface SubscriptionPlan {
  id: string;
  name: string;
  price_mkd: number;
  price_eur: number;
  features: string[];
  is_popular: boolean;
}

export interface UserSubscription {
  id: string;
  plan: SubscriptionPlan;
  status: string;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
}

export interface Invoice {
  id: string;
  amount: number;
  status: string;
  invoice_pdf: string;
  created_at: string;
}

export interface PaymentMethod {
  id: string;
  type: string;
  last4: string;
  brand: string;
  exp_month: number;
  exp_year: number;
}

export interface UsageStats {
  tenders_viewed: number;
  searches_made: number;
  limit: number;
  period: string;
}

class APIClient {
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

    // Auto-attach Authorization header if token exists
    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers,
    });

    // Handle 401 Unauthorized - token refresh needed
    if (response.status === 401) {
      const refreshToken = typeof window !== 'undefined' ? localStorage.getItem('refresh_token') : null;

      if (refreshToken && !endpoint.includes('/auth/')) {
        try {
          // Attempt token refresh
          const refreshResponse = await fetch(`${this.baseURL}/api/auth/refresh`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });

          if (refreshResponse.ok) {
            const tokens: AuthTokens = await refreshResponse.json();
            if (typeof window !== 'undefined') {
              localStorage.setItem('auth_token', tokens.access_token);
              localStorage.setItem('refresh_token', tokens.refresh_token);
            }

            // Retry original request with new token
            headers['Authorization'] = `Bearer ${tokens.access_token}`;
            const retryResponse = await fetch(`${this.baseURL}${endpoint}`, {
              ...options,
              headers,
            });

            if (retryResponse.ok) {
              return retryResponse.json();
            }
          }
        } catch (err) {
          // Refresh failed, redirect to login
          if (typeof window !== 'undefined') {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('refresh_token');
            window.location.href = '/login';
          }
          throw new Error('Authentication failed. Please login again.');
        }
      }

      // No refresh token or refresh failed
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
      throw new Error('Unauthorized. Please login again.');
    }

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || `API Error: ${response.statusText}`);
    }

    return response.json();
  }

  // Tenders
  async getTenders(params?: Record<string, any>) {
    const query = new URLSearchParams(params).toString();
    return this.request<{ total: number; items: Tender[] }>(`/api/tenders?${query}`);
  }

  async getTender(id: string) {
    return this.request<Tender>(`/api/tenders/${id}`);
  }

  async searchTenders(query: any) {
    return this.request<{ total: number; items: Tender[] }>('/api/tenders/search', {
      method: 'POST',
      body: JSON.stringify(query),
    });
  }

  async getTenderStats() {
    return this.request<any>('/api/tenders/stats/overview');
  }

  // Personalization
  async getPersonalizedDashboard(userId: string) {
    return this.request<DashboardData>(`/api/personalized/dashboard?user_id=${userId}`);
  }

  async getPreferences(userId: string) {
    return this.request<UserPreferences>(`/api/personalization/preferences?user_id=${userId}`);
  }

  async updatePreferences(userId: string, prefs: Partial<UserPreferences>) {
    return this.request<UserPreferences>(`/api/personalization/preferences?user_id=${userId}`, {
      method: 'PUT',
      body: JSON.stringify(prefs),
    });
  }

  async logBehavior(userId: string, behavior: { tender_id: string; action: string; duration_seconds?: number }) {
    return this.request(`/api/personalization/behavior?user_id=${userId}`, {
      method: 'POST',
      body: JSON.stringify(behavior),
    });
  }

  // RAG/AI
  async queryRAG(question: string, tenderId?: string) {
    return this.request<RAGQueryResponse>('/api/rag/query', {
      method: 'POST',
      body: JSON.stringify({ question, tender_id: tenderId }),
    });
  }

  async semanticSearch(query: string, topK: number = 10) {
    return this.request<{ results: any[] }>('/api/rag/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    });
  }

  // Authentication
  async authRegister(email: string, password: string, fullName?: string) {
    return this.request<AuthTokens>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email,
        password,
        full_name: fullName,
      }),
    });
  }

  async authLogin(email: string, password: string) {
    return this.request<AuthTokens>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async authRefresh(refreshToken: string) {
    return this.request<AuthTokens>('/api/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  }

  async authLogout() {
    return this.request<void>('/api/auth/logout', {
      method: 'POST',
    });
  }

  async authVerifyEmail(token: string) {
    return this.request<{ message: string }>('/api/auth/verify-email', {
      method: 'POST',
      body: JSON.stringify({ token }),
    });
  }

  async authResendVerification() {
    return this.request<{ message: string }>('/api/auth/resend-verification', {
      method: 'POST',
    });
  }

  async authForgotPassword(email: string) {
    return this.request<{ message: string }>('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  async authResetPassword(token: string, newPassword: string) {
    return this.request<{ message: string }>('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword }),
    });
  }

  async authChangePassword(oldPassword: string, newPassword: string) {
    return this.request<{ message: string }>('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
  }

  async authGetMe() {
    return this.request<User>('/api/auth/me');
  }

  async authUpdateMe(data: Partial<User>) {
    return this.request<User>('/api/auth/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // Billing Methods
  async getPlans() {
    return this.request<SubscriptionPlan[]>('/api/billing/plans');
  }

  async getCurrentSubscription() {
    return this.request<UserSubscription | null>('/api/billing/subscription');
  }

  async createCheckoutSession(tier: string, interval: 'monthly' | 'yearly' = 'monthly') {
    return this.request<{ checkout_url: string; session_id: string }>('/api/billing/checkout', {
      method: 'POST',
      body: JSON.stringify({ tier, interval }),
    });
  }

  async createPortalSession() {
    return this.request<{ url: string }>('/api/billing/portal', {
      method: 'POST',
    });
  }

  async getSubscriptionStatus() {
    return this.request<{
      tier: string;
      status: string;
      trial_ends_at?: string;
      is_trial_expired: boolean;
      daily_queries_used: number;
      daily_queries_limit: number;
      is_blocked: boolean;
      block_reason?: string;
    }>('/api/billing/status');
  }

  async cancelSubscription() {
    return this.request<void>('/api/billing/cancel', {
      method: 'POST',
    });
  }

  async getInvoices() {
    return this.request<Invoice[]>('/api/billing/invoices');
  }

  async getPaymentMethods() {
    return this.request<PaymentMethod[]>('/api/billing/payment-methods');
  }

  async getUsage() {
    return this.request<UsageStats>('/api/billing/usage');
  }

  // Fraud Prevention Methods
  async getTierLimits() {
    return this.request<{
      free: { tier: string; daily_queries: number; monthly_queries: number; trial_days: number; allow_vpn: boolean; features: string[] };
      starter: { tier: string; daily_queries: number; monthly_queries: number; trial_days: number; allow_vpn: boolean; features: string[] };
      professional: { tier: string; daily_queries: number; monthly_queries: number; trial_days: number; allow_vpn: boolean; features: string[] };
      enterprise: { tier: string; daily_queries: number; monthly_queries: number; trial_days: number; allow_vpn: boolean; features: string[] };
    }>('/api/fraud/tier-limits');
  }

  async validateEmail(email: string) {
    return this.request<{ email: string; is_allowed: boolean; reason: string | null }>('/api/fraud/validate-email', {
      method: 'POST',
      body: JSON.stringify({ email }),
    });
  }

  // Admin Methods
  async getDashboardStats() {
    return this.request<{
      total_users: number;
      total_tenders: number;
      active_subscriptions: number;
      pending_approvals: number;
    }>('/api/admin/stats');
  }

  async getUsers(filters?: {
    search?: string;
    role?: string;
    status?: string;
    page?: number;
    limit?: number;
  }) {
    const query = new URLSearchParams(filters as any).toString();
    return this.request<{
      total: number;
      items: Array<{
        id: string;
        email: string;
        full_name?: string;
        role: string;
        status: string;
        is_verified: boolean;
        is_banned: boolean;
        created_at: string;
        last_login?: string;
      }>;
    }>(`/api/admin/users?${query}`);
  }

  async getUser(userId: string) {
    return this.request<{
      id: string;
      email: string;
      full_name?: string;
      role: string;
      status: string;
      is_verified: boolean;
      is_banned: boolean;
      created_at: string;
      updated_at: string;
      last_login?: string;
      subscription?: any;
      stats?: {
        tenders_viewed: number;
        searches_made: number;
        total_spent: number;
      };
    }>(`/api/admin/users/${userId}`);
  }

  async updateUser(userId: string, data: {
    full_name?: string;
    email?: string;
    role?: string;
    status?: string;
  }) {
    return this.request<{ message: string }>(`/api/admin/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteUser(userId: string) {
    return this.request<{ message: string }>(`/api/admin/users/${userId}`, {
      method: 'DELETE',
    });
  }

  async banUser(userId: string, reason?: string) {
    return this.request<{ message: string }>(`/api/admin/users/${userId}/ban`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  }

  async unbanUser(userId: string) {
    return this.request<{ message: string }>(`/api/admin/users/${userId}/unban`, {
      method: 'POST',
    });
  }

  async approveTender(tenderId: string) {
    return this.request<{ message: string }>(`/api/admin/tenders/${tenderId}/approve`, {
      method: 'POST',
    });
  }

  async deleteTender(tenderId: string) {
    return this.request<{ message: string }>(`/api/admin/tenders/${tenderId}`, {
      method: 'DELETE',
    });
  }

  async getAnalytics(params?: {
    start_date?: string;
    end_date?: string;
    metric?: string;
  }) {
    const query = new URLSearchParams(params as any).toString();
    return this.request<{
      user_growth: Array<{ date: string; count: number }>;
      revenue: Array<{ date: string; amount: number }>;
      tender_stats: {
        total: number;
        active: number;
        closed: number;
        pending: number;
      };
      engagement: {
        daily_active_users: number;
        weekly_active_users: number;
        monthly_active_users: number;
      };
    }>(`/api/admin/analytics?${query}`);
  }

  async getLogs(filters?: {
    level?: string;
    user_id?: string;
    action?: string;
    start_date?: string;
    end_date?: string;
    page?: number;
    limit?: number;
  }) {
    const query = new URLSearchParams(filters as any).toString();
    return this.request<{
      total: number;
      items: Array<{
        id: string;
        timestamp: string;
        level: string;
        user_id?: string;
        user_email?: string;
        action: string;
        details?: any;
        ip_address?: string;
      }>;
    }>(`/api/admin/logs?${query}`);
  }

  async triggerScraper(params?: {
    force?: boolean;
    category?: string;
  }) {
    return this.request<{
      message: string;
      job_id: string;
      status: string;
    }>('/api/admin/scraper/trigger', {
      method: 'POST',
      body: JSON.stringify(params || {}),
    });
  }

  async getScraperStatus() {
    return this.request<{
      status: string;
      last_run?: string;
      next_run?: string;
      running: boolean;
      current_job?: {
        id: string;
        started_at: string;
        progress: number;
        items_processed: number;
      };
      stats: {
        total_runs: number;
        successful_runs: number;
        failed_runs: number;
        last_error?: string;
      };
    }>('/api/admin/scraper/status');
  }

  async sendBroadcast(data: {
    subject: string;
    message: string;
    recipients: 'all' | 'active' | 'premium' | string[];
    channel: 'email' | 'notification' | 'both';
  }) {
    return this.request<{
      message: string;
      recipients_count: number;
      broadcast_id: string;
    }>('/api/admin/broadcast', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }
}

export const api = new APIClient();
