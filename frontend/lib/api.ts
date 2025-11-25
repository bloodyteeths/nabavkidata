const API_URL = (typeof window !== 'undefined')
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : 'https://api.nabavkidata.com';

export interface Tender {
  tender_id: string;
  title: string;
  description?: string;
  category?: string;
  procuring_entity?: string;
  opening_date?: string;
  closing_date?: string;
  publication_date?: string;
  estimated_value_mkd?: number;
  estimated_value_eur?: number;
  actual_value_mkd?: number;
  actual_value_eur?: number;
  cpv_code?: string;
  status?: string;
  winner?: string;
  source_url?: string;
  language?: string;
  procedure_type?: string;
  contract_signing_date?: string;
  contract_duration?: string;
  contracting_entity_category?: string;
  procurement_holder?: string;
  bureau_delivery_date?: string;
  // Contact Information
  contact_person?: string;
  contact_email?: string;
  contact_phone?: string;
  // Additional Fields
  num_bidders?: number;
  evaluation_method?: string;
  scraped_at?: string;
  updated_at?: string;
  created_at: string;
}

export interface TenderDocument {
  doc_id: string;
  tender_id: string;
  doc_type?: string;
  file_name?: string;
  file_path?: string;
  file_url?: string;
  content_text?: string;
  extraction_status: string;
  file_size_bytes?: number;
  page_count?: number;
  mime_type?: string;
  uploaded_at: string;
}

export interface TenderBidder {
  bidder_id: string;
  company_name: string;
  tax_id?: string;
  bid_amount_mkd?: number;
  bid_amount_eur?: number;
  rank?: number;
  is_winner: boolean;
  is_disqualified: boolean;
  disqualification_reason?: string;
  bid_date?: string;
}

export interface TenderBiddersResponse {
  tender_id: string;
  total_bidders: number;
  winner?: string;
  bidders: TenderBidder[];
}

export interface TenderLot {
  lot_id: string;
  lot_number: number;
  title: string;
  description?: string;
  estimated_value_mkd?: number;
  actual_value_mkd?: number;
  cpv_code?: string;
  status?: string;
  winner?: string;
}

export interface TenderLotsResponse {
  tender_id: string;
  has_lots: boolean;
  total_lots: number;
  lots: TenderLot[];
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
  user_id: string;
  email: string;
  full_name?: string;
  email_verified: boolean;
  subscription_tier: string;
  created_at: string;
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

export interface ProductSearchResult {
  id: number;
  name: string;
  quantity?: number;
  unit?: string;
  unit_price?: number;
  total_price?: number;
  specifications?: Record<string, any>;
  cpv_code?: string;
  extraction_confidence?: number;
  tender_id: string;
  tender_title?: string;
  procuring_entity?: string;
  opening_date?: string;
  status?: string;
  winner?: string;
}

export interface ProductSearchResponse {
  query: string;
  total: number;
  page: number;
  page_size: number;
  items: ProductSearchResult[];
}

export interface ProductAggregation {
  product_name: string;
  total_quantity?: number;
  avg_unit_price?: number;
  min_unit_price?: number;
  max_unit_price?: number;
  tender_count: number;
  years: number[];
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

  private getCSRFToken(): string | null {
    if (typeof window === 'undefined') return null;

    // Check if token exists and is valid
    try {
      const stored = sessionStorage.getItem('csrf_token');
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Date.now() < parsed.expiry) {
          return parsed.token;
        }
      }
    } catch (e) {
      // Ignore errors
    }

    // Generate new token
    const array = new Uint8Array(32);
    crypto.getRandomValues(array);
    const token = Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
    const tokenData = {
      token,
      expiry: Date.now() + 60 * 60 * 1000, // 1 hour
    };

    sessionStorage.setItem('csrf_token', JSON.stringify(tokenData));
    return token;
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

    // Add CSRF token for state-changing operations on billing endpoints
    if (
      options?.method &&
      ['POST', 'PUT', 'DELETE', 'PATCH'].includes(options.method) &&
      endpoint.includes('/billing')
    ) {
      const csrfToken = this.getCSRFToken();
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
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
            window.location.href = '/auth/login';
          }
          throw new Error('Authentication failed. Please login again.');
        }
      }

      // No refresh token or refresh failed
      if (typeof window !== 'undefined') {
        localStorage.removeItem('auth_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/auth/login';
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
    const encodedId = encodeURIComponent(id);
    return this.request<Tender>(`/api/tenders/${encodedId}`);
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

  async getTenderDocuments(tenderId: string) {
    const encodedId = encodeURIComponent(tenderId);
    return this.request<{
      tender_id: string;
      total: number;
      documents: TenderDocument[];
    }>(`/api/tenders/${encodedId}/documents`);
  }

  async getTenderBidders(tenderNumber: string, tenderYear: string) {
    return this.request<TenderBiddersResponse>(
      `/api/tenders/by-id/${tenderNumber}/${tenderYear}/bidders`
    );
  }

  async getTenderLots(tenderNumber: string, tenderYear: string) {
    return this.request<TenderLotsResponse>(
      `/api/tenders/by-id/${tenderNumber}/${tenderYear}/lots`
    );
  }

  // Personalization
  async getPersonalizedDashboard(userId: string) {
    return this.request<DashboardData>(`/api/personalization/dashboard?user_id=${userId}`);
  }

  async getPreferences(userId: string) {
    return this.request<UserPreferences>(`/api/personalization/preferences?user_id=${userId}`);
  }

  async createPreferences(userId: string, prefs: Partial<UserPreferences>) {
    return this.request<UserPreferences>(`/api/personalization/preferences?user_id=${userId}`, {
      method: 'POST',
      body: JSON.stringify(prefs),
    });
  }

  async updatePreferences(userId: string, prefs: Partial<UserPreferences>) {
    return this.request<UserPreferences>(`/api/personalization/preferences?user_id=${userId}`, {
      method: 'PUT',
      body: JSON.stringify(prefs),
    });
  }

  async savePreferences(userId: string, prefs: Partial<UserPreferences>) {
    // Try update first, create if 404
    try {
      return await this.updatePreferences(userId, prefs);
    } catch (error: any) {
      if (error.message?.includes('not found') || error.message?.includes('404')) {
        return await this.createPreferences(userId, prefs);
      }
      throw error;
    }
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
    }>('/api/admin/dashboard');
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
    const encodedId = encodeURIComponent(tenderId);
    return this.request<{ message: string }>(`/api/admin/tenders/${encodedId}/approve`, {
      method: 'POST',
    });
  }

  async deleteTender(tenderId: string) {
    const encodedId = encodeURIComponent(tenderId);
    return this.request<{ message: string }>(`/api/admin/tenders/${encodedId}`, {
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

  // Digest Methods
  async getDigests(userId: string, limit: number = 50, offset: number = 0) {
    return this.request<{
      total: number;
      items: Array<{
        id: string;
        date: string;
        tender_count: number;
        competitor_activity_count: number;
        sent: boolean;
        sent_at: string | null;
        preview: {
          text: string;
        };
      }>;
    }>(`/api/personalization/digests?user_id=${userId}&limit=${limit}&offset=${offset}`);
  }

  async getDigestDetail(digestId: string, userId: string) {
    return this.request<{
      id: string;
      date: string;
      tender_count: number;
      competitor_activity_count: number;
      html: string;
      text: string;
      sent: boolean;
      sent_at: string | null;
    }>(`/api/personalization/digests/${digestId}?user_id=${userId}`);
  }

  // Product Search Methods
  async searchProducts(params: {
    q: string;
    year?: number;
    cpv_code?: string;
    min_price?: number;
    max_price?: number;
    procuring_entity?: string;
    page?: number;
    page_size?: number;
  }) {
    const query = new URLSearchParams();
    query.append('q', params.q);
    if (params.year) query.append('year', params.year.toString());
    if (params.cpv_code) query.append('cpv_code', params.cpv_code);
    if (params.min_price) query.append('min_price', params.min_price.toString());
    if (params.max_price) query.append('max_price', params.max_price.toString());
    if (params.procuring_entity) query.append('procuring_entity', params.procuring_entity);
    if (params.page) query.append('page', params.page.toString());
    if (params.page_size) query.append('page_size', params.page_size.toString());
    return this.request<ProductSearchResponse>(`/api/products/search?${query.toString()}`);
  }

  async getProductAggregations(query: string) {
    return this.request<{ query: string; aggregations: ProductAggregation[] }>(
      `/api/products/aggregate?q=${encodeURIComponent(query)}`
    );
  }

  async getProductsByTender(tenderId: string) {
    return this.request<ProductSearchResult[]>(
      `/api/products/by-tender/${encodeURIComponent(tenderId)}`
    );
  }

  async getProductSuggestions(query: string, limit: number = 10) {
    return this.request<{ suggestions: string[] }>(
      `/api/products/suggestions?q=${encodeURIComponent(query)}&limit=${limit}`
    );
  }

  async getProductStats() {
    return this.request<{
      total_products: number;
      tenders_with_products: number;
      unique_products: number;
      avg_confidence: number | null;
    }>('/api/products/stats');
  }

  // ============================================================================
  // E-PAZAR METHODS
  // ============================================================================

  async getEPazarTenders(params?: Record<string, any>) {
    const query = new URLSearchParams(params).toString();
    return this.request<{ total: number; page: number; page_size: number; items: EPazarTender[] }>(
      `/api/epazar/tenders?${query}`
    );
  }

  async getEPazarTender(tenderId: string) {
    const encodedId = encodeURIComponent(tenderId);
    return this.request<EPazarTenderDetail>(`/api/epazar/tenders/${encodedId}`);
  }

  async getEPazarItems(tenderId: string) {
    const encodedId = encodeURIComponent(tenderId);
    return this.request<EPazarItem[]>(`/api/epazar/tenders/${encodedId}/items`);
  }

  async getEPazarOffers(tenderId: string) {
    const encodedId = encodeURIComponent(tenderId);
    return this.request<EPazarOffer[]>(`/api/epazar/tenders/${encodedId}/offers`);
  }

  async getEPazarAwardedItems(tenderId: string) {
    const encodedId = encodeURIComponent(tenderId);
    return this.request<EPazarAwardedItem[]>(`/api/epazar/tenders/${encodedId}/awarded-items`);
  }

  async getEPazarDocuments(tenderId: string) {
    const encodedId = encodeURIComponent(tenderId);
    return this.request<EPazarDocument[]>(`/api/epazar/tenders/${encodedId}/documents`);
  }

  async getEPazarSuppliers(params?: Record<string, any>) {
    const query = new URLSearchParams(params).toString();
    return this.request<{ total: number; page: number; page_size: number; items: EPazarSupplier[] }>(
      `/api/epazar/suppliers?${query}`
    );
  }

  async getEPazarSupplier(supplierId: string) {
    return this.request<EPazarSupplierDetail>(`/api/epazar/suppliers/${supplierId}`);
  }

  async getEPazarStats() {
    return this.request<EPazarStats>('/api/epazar/stats/overview');
  }

  async summarizeEPazarTender(tenderId: string) {
    const encodedId = encodeURIComponent(tenderId);
    return this.request<{ tender_id: string; summary: string; items_count: number; offers_count: number }>(
      `/api/epazar/tenders/${encodedId}/summarize`,
      { method: 'POST' }
    );
  }

  async analyzeEPazarSupplier(supplierId: string) {
    return this.request<{ supplier_id: string; company_name: string; analysis: string; total_offers_analyzed: number }>(
      `/api/epazar/suppliers/${supplierId}/analyze`,
      { method: 'POST' }
    );
  }
}

// E-Pazar Types
export interface EPazarTender {
  tender_id: string;
  title: string;
  description?: string;
  contracting_authority?: string;
  contracting_authority_id?: string;
  estimated_value_mkd?: number;
  estimated_value_eur?: number;
  awarded_value_mkd?: number;
  awarded_value_eur?: number;
  procedure_type?: string;
  status: string;
  publication_date?: string;
  closing_date?: string;
  award_date?: string;
  contract_date?: string;
  contract_number?: string;
  contract_duration?: string;
  cpv_code?: string;
  category?: string;
  source_url?: string;
  source_category: string;
  language: string;
  scraped_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface EPazarTenderDetail extends EPazarTender {
  items: EPazarItem[];
  offers: EPazarOffer[];
  awarded_items: EPazarAwardedItem[];
  documents: EPazarDocument[];
}

export interface EPazarItem {
  item_id: string;
  tender_id: string;
  line_number: number;
  item_name: string;
  item_description?: string;
  item_code?: string;
  cpv_code?: string;
  quantity: number;
  unit?: string;
  estimated_unit_price_mkd?: number;
  estimated_unit_price_eur?: number;
  estimated_total_price_mkd?: number;
  estimated_total_price_eur?: number;
  specifications?: Record<string, any>;
  delivery_date?: string;
  delivery_location?: string;
  notes?: string;
  created_at?: string;
}

export interface EPazarOffer {
  offer_id: string;
  tender_id: string;
  supplier_name: string;
  supplier_tax_id?: string;
  supplier_address?: string;
  supplier_city?: string;
  supplier_contact_email?: string;
  supplier_contact_phone?: string;
  offer_number?: string;
  offer_date?: string;
  total_bid_mkd: number;
  total_bid_eur?: number;
  evaluation_score?: number;
  ranking?: number;
  is_winner: boolean;
  offer_status: string;
  rejection_reason?: string;
  disqualified: boolean;
  disqualification_date?: string;
  documents_submitted?: Record<string, any>;
  notes?: Record<string, any>;
  items_count?: number;
  created_at?: string;
}

export interface EPazarAwardedItem {
  awarded_item_id: string;
  tender_id: string;
  item_id?: string;
  offer_id?: string;
  supplier_name: string;
  supplier_tax_id?: string;
  contract_item_number?: string;
  contracted_quantity: number;
  contracted_unit_price_mkd: number;
  contracted_total_mkd: number;
  contracted_unit_price_eur?: number;
  contracted_total_eur?: number;
  planned_delivery_date?: string;
  actual_delivery_date?: string;
  delivery_location?: string;
  received_quantity?: number;
  quality_score?: number;
  quality_notes?: string;
  on_time?: boolean;
  billed_amount_mkd?: number;
  paid_amount_mkd?: number;
  payment_date?: string;
  status: string;
  completion_date?: string;
  item_name?: string;
  item_description?: string;
  created_at?: string;
}

export interface EPazarDocument {
  doc_id: string;
  tender_id: string;
  doc_type?: string;
  doc_category?: string;
  file_name?: string;
  file_path?: string;
  file_url?: string;
  content_text?: string;
  extraction_status: string;
  file_size_bytes?: number;
  page_count?: number;
  mime_type?: string;
  file_hash?: string;
  upload_date?: string;
  created_at?: string;
}

export interface EPazarSupplier {
  supplier_id: string;
  company_name: string;
  tax_id?: string;
  company_type?: string;
  address?: string;
  city?: string;
  contact_person?: string;
  contact_email?: string;
  contact_phone?: string;
  website?: string;
  total_offers: number;
  total_wins: number;
  win_rate?: number;
  total_contract_value_mkd?: number;
  avg_bid_amount_mkd?: number;
  industries?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface EPazarSupplierDetail extends EPazarSupplier {
  recent_offers: EPazarOffer[];
  recent_wins: EPazarOffer[];
}

export interface EPazarStats {
  total_tenders: number;
  total_items: number;
  total_offers: number;
  total_suppliers: number;
  total_documents: number;
  total_value_mkd: number;
  awarded_value_mkd: number;
  status_breakdown: Record<string, { count: number; total_value: number }>;
  recent_tenders: EPazarTender[];
  top_suppliers: EPazarSupplier[];
}

export const api = new APIClient();
