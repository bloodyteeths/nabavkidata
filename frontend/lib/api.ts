const API_URL = (typeof window !== 'undefined')
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : 'https://api.nabavkidata.com';

export interface PriceDataPoint {
  period: string;
  tender_count: number;
  avg_estimated_mkd: number;
  avg_awarded_mkd: number;
  avg_discount_pct: number;
  avg_bidders: number;
}

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
  // Requirements fields
  payment_terms?: string;
  delivery_location?: string;
  security_deposit_mkd?: number;
  performance_guarantee_mkd?: number;
  scraped_at?: string;
  updated_at?: string;
  created_at: string;
  // Embedded bidders/lots from raw_data_json (for awarded tenders)
  bidders?: Array<{
    company_name: string;
    bid_amount_mkd?: number;
    is_winner?: boolean;
    rank?: number;
    disqualified?: boolean;
  }>;
  lots?: Array<{
    lot_number?: number;
    title?: string;
    estimated_value_mkd?: number;
    actual_value_mkd?: number;
    winner?: string;
  }>;
  raw_data_json?: Record<string, any>;
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

export interface EnhancedTender extends Tender {
  bidders: TenderBidder[];
  price_analysis: {
    estimated_value: number;
    winning_bid: number;
    lowest_bid: number;
    highest_bid: number;
    num_bidders: number;
  };
  data_completeness: number;
  documents: TenderDocument[];
}

export interface Supplier {
  supplier_id: string;
  company_name: string;
  tax_id?: string;
  address?: string;
  city?: string;
  country?: string;
  contact_person?: string;
  contact_email?: string;
  contact_phone?: string;
  website?: string;
  total_bids: number;
  total_wins: number;
  win_rate?: number;
  total_value_won_mkd?: number;
  created_at?: string;
}

export interface SupplierTenderParticipation {
  tender_id: string;
  title: string;
  procuring_entity: string;
  bid_amount_mkd?: number;
  rank?: number;
  is_winner: boolean;
  status: string;
  closing_date?: string;
}

export interface SupplierDetail extends Supplier {
  recent_participations: SupplierTenderParticipation[];
  wins_by_category: Record<string, number>;
  wins_by_entity: Record<string, number>;
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
  role?: string;
  created_at: string;
}

export interface SubscriptionPlan {
  id: string;
  tier?: string;  // Backend uses 'tier' instead of 'id'
  name: string;
  price_mkd: number;
  price_eur: number;
  features: string[];
  is_popular?: boolean;
  stripe_price_id?: string | null;
  limits?: {
    rag_queries_per_month?: number;
    saved_alerts?: number;
    export_results?: boolean;
    alerts_per_day?: number;
    api_access?: boolean;
  };
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

    // Debug logging for failed requests
    console.log(`[API] ${options?.method || 'GET'} ${endpoint}`, { hasToken: !!token, tokenLength: token?.length });

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
      credentials: 'include',
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
              credentials: 'include',
            });

            if (retryResponse.ok) {
              return retryResponse.json();
            }
          }
        } catch (err) {
          // Refresh failed - only redirect to login for auth endpoints
          if (endpoint.includes('/auth/me') || endpoint.includes('/auth/refresh')) {
            if (typeof window !== 'undefined') {
              localStorage.removeItem('auth_token');
              localStorage.removeItem('refresh_token');
              window.location.href = '/auth/login';
            }
          }
          throw new Error('Authentication failed. Please login again.');
        }
      }

      // No refresh token or refresh failed
      // Only redirect to login for auth endpoints - let other endpoints handle errors gracefully
      if (endpoint.includes('/auth/me') || endpoint.includes('/auth/refresh')) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/auth/login';
        }
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
    // Filter out null, undefined, and empty string values to prevent URLSearchParams issues
    const cleanParams = Object.entries(params || {})
      .filter(([_, value]) => value !== null && value !== undefined && value !== '')
      .reduce((acc, [key, value]) => ({ ...acc, [key]: value }), {});

    const query = new URLSearchParams(cleanParams).toString();
    return this.request<{ total: number; items: Tender[] }>(`/api/tenders?${query}`);
  }

  async getTender(id: string) {
    const encodedId = encodeURIComponent(id);
    return this.request<Tender>(`/api/tenders/${encodedId}`);
  }

  async getEnhancedTender(id: string) {
    const encodedId = encodeURIComponent(id);
    return this.request<EnhancedTender>(`/api/tenders/${encodedId}/enhanced`);
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

  async getTenderCategories() {
    return this.request<{ total: number; categories: Array<{ category: string; count: number }> }>(
      '/api/tenders/categories'
    );
  }

  async getCpvCodes(prefix?: string, limit: number = 100) {
    const params = new URLSearchParams();
    if (prefix) params.append('prefix', prefix);
    params.append('limit', limit.toString());
    return this.request<{
      total: number;
      prefix_filter: string | null;
      cpv_codes: Array<{
        cpv_code: string;
        tender_count: number;
        total_value_mkd: number | null;
        avg_value_mkd: number | null;
      }>;
    }>(`/api/tenders/cpv-codes?${params.toString()}`);
  }

  // CPV APIs (expanded)
  async searchCPVCodes(prefix: string, limit: number = 20) {
    const params = new URLSearchParams();
    params.append('prefix', prefix);
    params.append('limit', String(limit));
    return this.request<{
      results: Array<{
        code: string;
        name: string;
        name_mk: string;
        tender_count?: number;
        total_value_mkd?: number;
      }>;
    }>(`/api/cpv-codes/search?${params.toString()}`);
  }

  async getCPVCodes(limit: number = 100) {
    const params = new URLSearchParams();
    params.append('limit', String(limit));
    const response = await this.request<{
      total: number;
      cpv_codes: Array<{
        code: string;
        name: string;
        name_mk: string;
        parent_code?: string;
        level?: number;
        tender_count?: number;
        total_value_mkd?: number;
      }>;
    }>(`/api/cpv-codes?${params.toString()}`);
    // Map response to expected format
    return {
      cpv_codes: response.cpv_codes.map(c => ({
        cpv_code: c.code,
        title: c.name_mk || c.name,
        level: c.level,
        parent: c.parent_code,
        tender_count: c.tender_count,
        total_value_mkd: c.total_value_mkd,
      }))
    };
  }

  async getCPVDivisions() {
    const response = await this.request<{
      total: number;
      divisions: Array<{
        code: string;
        name: string;
        name_mk: string;
        tender_count?: number;
        total_value_mkd?: number;
      }>;
    }>(`/api/cpv-codes/divisions`);
    // Map response to expected format
    return {
      divisions: response.divisions.map(d => ({
        cpv_code: d.code,
        title: d.name_mk || d.name,
        level: 2, // Divisions are level 2 in CPV hierarchy
      }))
    };
  }

  async getCPVCode(code: string) {
    const response = await this.request<{
      code: string;
      name: string;
      name_mk: string;
      parent_code?: string;
      level?: number;
      tender_count?: number;
      total_value_mkd?: number;
      recent_tenders?: Array<any>;
      top_entities?: Array<any>;
      monthly_trend?: Array<any>;
    }>(`/api/cpv-codes/${encodeURIComponent(code)}`);
    // The CPVBrowser expects cpv_code and title fields with children
    // Since we don't have children from API, return empty array
    return {
      cpv_code: response.code,
      title: response.name_mk || response.name,
      path: [],
      children: [],
    };
  }

  // Saved Searches
  async getSavedSearches() {
    return this.request<{ items: Array<{ id: string; name: string; filters: Record<string, any>; created_at: string }> }>(
      `/api/search/saved`
    );
  }

  async createSavedSearch(payload: { name: string; filters: Record<string, any> }) {
    return this.request<{ id: string; name: string; filters: Record<string, any>; created_at: string }>(`/api/search/saved`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  }

  async deleteSavedSearch(id: string) {
    return this.request<{ message: string }>(`/api/search/saved/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
  }

  // Analytics
  async getMarketOverview(params?: { start_date?: string; end_date?: string }) {
    const query = new URLSearchParams(params as any).toString();
    return this.request<{ cards: any; charts: any }>(`/api/analytics/market-overview${query ? `?${query}` : ''}`);
  }

  async getCompetitorAnalysis(params?: { period?: string; limit?: number }) {
    const query = new URLSearchParams(params as any).toString();
    return this.request<{ competitors: any[]; summary: any }>(`/api/analytics/top-competitors${query ? `?${query}` : ''}`);
  }

  async getCategoryTrends(params?: { start_date?: string; end_date?: string; cpv_code?: string }) {
    const query = new URLSearchParams(params as any).toString();
    return this.request<{ trends: any[]; summary: any }>(`/api/analytics/category-trends${query ? `?${query}` : ''}`);
  }

  // Supplier strength
  async getSupplierStrength(supplierId: string) {
    return this.request<{ supplier_id: string; score: number; metrics: any; breakdown: any }>(
      `/api/analytics/supplier-strength/${encodeURIComponent(supplierId)}`
    );
  }

  // Tender price history
  async getTenderPriceHistory(tenderId: string) {
    return this.request<{ tender_id: string; points: Array<{ date: string; estimated_value_mkd?: number; awarded_value_mkd?: number }> }>(
      `/api/tenders/by-id/${encodeURIComponent(tenderId)}/price_history`
    );
  }

  // CPV code price history
  async getPriceHistory(
    cpvCode?: string,
    months?: number,
    params?: {
      category?: string;
      entity?: string;
      period?: '30d' | '90d' | '1y' | 'all';
    }
  ): Promise<{
    cpv_code?: string;
    data_points: PriceDataPoint[];
    trend: string;
    trend_pct: number;
    total_tenders: number;
  }> {
    const queryParams = new URLSearchParams();
    if (cpvCode) queryParams.append('cpv_code', cpvCode);
    if (params?.category) queryParams.append('category', params.category);
    if (params?.entity) queryParams.append('entity', params.entity);
    if (params?.period) queryParams.append('period', params.period);

    const response = await this.request<{
      period: string;
      filters: {
        cpv_code?: string;
        category?: string;
        entity?: string;
      };
      data_points: number;
      time_series: Array<{
        period: string;
        year: number;
        month: number;
        tender_count: number;
        avg_estimated_mkd?: number;
        avg_estimated_eur?: number;
        avg_awarded_mkd?: number;
        avg_awarded_eur?: number;
        total_estimated_mkd?: number;
        total_awarded_mkd?: number;
      }>;
    }>(`/api/tenders/price_history?${queryParams.toString()}`);

    // Calculate trend from first to last data point
    const timeSeries = response.time_series;
    let trend = 'stable';
    let trendPct = 0;

    if (timeSeries.length >= 2) {
      const first = timeSeries[0].avg_estimated_mkd || 0;
      const last = timeSeries[timeSeries.length - 1].avg_estimated_mkd || 0;

      if (first > 0) {
        trendPct = ((last - first) / first) * 100;
        if (Math.abs(trendPct) < 5) {
          trend = 'stable';
        } else if (trendPct > 0) {
          trend = 'increasing';
        } else {
          trend = 'decreasing';
        }
      }
    }

    // Transform API response to match component interface
    const dataPoints: PriceDataPoint[] = timeSeries.map(point => ({
      period: point.period,
      tender_count: point.tender_count,
      avg_estimated_mkd: point.avg_estimated_mkd || 0,
      avg_awarded_mkd: point.avg_awarded_mkd || 0,
      avg_discount_pct:
        point.avg_estimated_mkd && point.avg_awarded_mkd
          ? ((1 - point.avg_awarded_mkd / point.avg_estimated_mkd) * 100)
          : 0,
      avg_bidders: 0, // Not provided by this endpoint
    }));

    return {
      cpv_code: response.filters.cpv_code,
      data_points: dataPoints,
      trend,
      trend_pct: Math.abs(trendPct),
      total_tenders: timeSeries.reduce((sum, p) => sum + p.tender_count, 0),
    };
  }

  // Tender AI summary
  async getTenderAISummary(tenderId: string) {
    return this.request<{
      tender_id: string;
      title: string;
      summary: {
        overview: string;
        key_requirements: string[];
        estimated_complexity: string;
        complexity_factors: string[];
        suggested_cpv_codes: string[];
        deadline_urgency: string;
        days_remaining: number | null;
        competition_level: string;
      };
      generated_at: string;
      model: string;
      note: string;
    }>(
      `/api/tenders/by-id/${encodeURIComponent(tenderId)}/ai_summary`
    );
  }

  // Tender raw JSON
  async getTenderRawJSON(tenderId: string) {
    return this.request<{ tender_id: string; raw: Record<string, any> }>(`/api/tenders/${encodeURIComponent(tenderId)}/raw`);
  }

  // Epazar price history and supplier stats
  async getEpazarItemPriceHistory(itemId: string) {
    return this.request<{ item_id: string; points: Array<{ date: string; price_mkd?: number }> }>(
      `/api/epazar/items/${encodeURIComponent(itemId)}/price-history`
    );
  }

  async getEpazarSupplierStats(supplierId: string) {
    return this.request<{ supplier_id: string; stats: any }>(`/api/epazar/suppliers/${encodeURIComponent(supplierId)}/stats`);
  }

  // Tender comparison
  async compareTenders(tenderIds: string[]) {
    return this.request<{ items: Array<any> }>(`/api/tenders/compare`, {
      method: 'POST',
      body: JSON.stringify({ tender_ids: tenderIds }),
    });
  }

  // Entities (Procuring Organizations)
  async getEntities(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    sort_by?: string;
    sort_order?: string;
  }) {
    const query = new URLSearchParams(
      Object.entries(params || {})
        .filter(([_, v]) => v !== undefined && v !== null)
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return this.request<{
      total: number;
      page: number;
      page_size: number;
      items: Array<{
        entity_id: string;
        entity_name: string;
        entity_type?: string;
        category?: string;
        total_tenders: number;
        total_value_mkd: number | null;
      }>;
    }>(`/api/entities?${query}`);
  }

  async searchEntities(search: string, limit: number = 10) {
    return this.request<{
      total: number;
      items: Array<{
        entity_id: string;
        entity_name: string;
        total_tenders: number;
        total_value_mkd: number | null;
      }>;
    }>(`/api/entities?search=${encodeURIComponent(search)}&page_size=${limit}`);
  }

  // Suppliers
  async getSuppliers(params?: {
    page?: number;
    page_size?: number;
    search?: string;
    city?: string;
    min_wins?: number;
    sort_by?: string;
    sort_order?: string;
  }) {
    const query = new URLSearchParams(
      Object.entries(params || {})
        .filter(([_, v]) => v !== undefined && v !== null)
        .map(([k, v]) => [k, String(v)])
    ).toString();
    return this.request<{
      total: number;
      page: number;
      page_size: number;
      items: Supplier[];
    }>(`/api/suppliers?${query}`);
  }

  async getSupplier(supplierId: string) {
    return this.request<SupplierDetail>(`/api/suppliers/${supplierId}`);
  }

  async searchSuppliers(companyName: string, limit: number = 10) {
    return this.request<Supplier[]>(`/api/suppliers/search/${encodeURIComponent(companyName)}?limit=${limit}`);
  }

  async getKnownWinners(search?: string, limit: number = 50) {
    const params = new URLSearchParams();
    if (search) params.append('search', search);
    params.append('limit', limit.toString());
    return this.request<{
      total: number;
      winners: Array<{
        company_name: string;
        total_wins: number;
        total_bids: number;
        total_contract_value: number | null;
      }>;
    }>(`/api/suppliers/winners?${params.toString()}`);
  }

  async getTenderDocuments(tenderId: string) {
    // Always use /by-id/ endpoint which handles all formats (UUID and number/year)
    const encodedId = encodeURIComponent(tenderId);
    return this.request<{
      tender_id: string;
      total: number;
      documents: TenderDocument[];
    }>(`/api/tenders/by-id/${encodedId}/documents`);
  }

  async getDocumentContent(docId: string) {
    return this.request<{
      doc_id: string;
      content_text: string;
      ai_summary?: string;
      key_requirements?: string[];
      items_mentioned?: string[];
    }>(`/api/documents/${encodeURIComponent(docId)}/content`);
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
  async getPersonalizedDashboard(_userId?: string) {
    // user_id is extracted from auth token on the backend, no need to pass it
    return this.request<DashboardData>(`/api/personalization/dashboard`);
  }

  async refreshInterestVector() {
    // Refresh user interest vector for fresh analysis
    return this.request<{ message: string }>(`/api/personalization/interest-vector/refresh`, {
      method: 'POST',
    });
  }

  async getPreferences(_userId?: string) {
    // user_id is extracted from auth token on the backend
    return this.request<UserPreferences>(`/api/personalization/preferences`);
  }

  async createPreferences(_userId: string, prefs: Partial<UserPreferences>) {
    // user_id is extracted from auth token on the backend
    return this.request<UserPreferences>(`/api/personalization/preferences`, {
      method: 'POST',
      body: JSON.stringify(prefs),
    });
  }

  async updatePreferences(_userId: string, prefs: Partial<UserPreferences>) {
    // user_id is extracted from auth token on the backend
    return this.request<UserPreferences>(`/api/personalization/preferences`, {
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

  async logBehavior(_userId: string, behavior: { tender_id: string; action: string; duration_seconds?: number }) {
    // user_id is extracted from auth token on the backend
    return this.request(`/api/personalization/behavior`, {
      method: 'POST',
      body: JSON.stringify(behavior),
    });
  }

  // Search History Tracking
  async logSearch(_userId: string, search: {
    query_text?: string;
    filters?: Record<string, any>;
    results_count?: number;
    clicked_tender_id?: string;
  }) {
    // user_id is extracted from auth token on the backend
    return this.request(`/api/personalization/search-history`, {
      method: 'POST',
      body: JSON.stringify(search),
    });
  }

  async getSearchHistory(_userId: string, limit: number = 20) {
    // user_id is extracted from auth token on the backend
    return this.request<{ total: number; items: Array<{
      id: string;
      query_text?: string;
      filters?: string;
      results_count?: number;
      clicked_tender_id?: string;
      created_at?: string;
    }> }>(`/api/personalization/search-history?limit=${limit}`);
  }

  async getPopularSearches(limit: number = 10) {
    return this.request<{ items: Array<{ query: string; count: number }> }>(
      `/api/personalization/popular-searches?limit=${limit}`
    );
  }

  // RAG/AI
  async queryRAG(
    question: string,
    tenderId?: string,
    conversationHistory?: Array<{ role: string; content: string }>
  ) {
    return this.request<RAGQueryResponse>('/api/rag/query', {
      method: 'POST',
      body: JSON.stringify({
        question,
        tender_id: tenderId,
        conversation_history: conversationHistory
      }),
    });
  }

  async sendTenderChat(
    tenderNumber: string,
    tenderYear: string,
    question: string,
    conversationHistory?: Array<{ role: string; content: string }>
  ) {
    return this.request<{
      answer: string;
      sources: Array<{
        doc_id: string;
        file_name: string;
        excerpt: string;
      }>;
      confidence: number;
    }>(`/api/tenders/by-id/${tenderNumber}/${tenderYear}/chat`, {
      method: 'POST',
      body: JSON.stringify({
        question,
        conversation_history: conversationHistory || [],
      }),
    });
  }

  async semanticSearch(query: string, topK: number = 10) {
    return this.request<{ results: any[] }>('/api/rag/search', {
      method: 'POST',
      body: JSON.stringify({ query, top_k: topK }),
    });
  }

  async submitChatFeedback(data: {
    session_id?: string;
    message_id: string;
    question: string;
    answer: string;
    helpful: boolean;
    comment?: string;
  }) {
    return this.request<{ success: boolean; feedback_id: number; message: string }>('/api/rag/feedback', {
      method: 'POST',
      body: JSON.stringify(data),
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
    const response = await this.request<{ plans: any[]; trial_days?: number }>('/api/billing/plans');
    // Normalize backend response (tier -> id)
    return response.plans.map(plan => ({
      ...plan,
      id: plan.tier || plan.id,
      is_popular: plan.tier === 'professional',
    })) as SubscriptionPlan[];
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
  async getDigests(_userId?: string, limit: number = 50, offset: number = 0) {
    // user_id is extracted from auth token on the backend
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
    }>(`/api/personalization/digests?limit=${limit}&offset=${offset}`);
  }

  async getDigestDetail(digestId: string, _userId?: string) {
    // user_id is extracted from auth token on the backend
    return this.request<{
      id: string;
      date: string;
      tender_count: number;
      competitor_activity_count: number;
      html: string;
      text: string;
      sent: boolean;
      sent_at: string | null;
    }>(`/api/personalization/digests/${digestId}`);
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

  async getAIExtractedProducts(tenderId: string) {
    return this.request<{
      tender_id: string;
      extraction_status: 'success' | 'no_documents' | 'extraction_failed';
      products: Array<{
        name: string;
        quantity?: string;
        unit?: string;
        unit_price?: string;
        total_price?: string;
        specifications?: string;
        category?: string;
      }>;
      summary?: string;
      source_documents: number;
    }>(`/api/tenders/by-id/${encodeURIComponent(tenderId)}/ai-products`);
  }

  async getPriceBenchmarks(category?: string, cpvCode?: string) {
    const params: Record<string, string> = {};
    if (category) params.category = category;
    if (cpvCode) params.cpv_prefix = cpvCode;
    const query = new URLSearchParams(params).toString();
    return this.request<{
      category: string;
      benchmarks: Array<{
        cpv_division: string;
        cpv_division_name: string | null;
        avg_value: number | null;
        median_value: number | null;
        min_value: number | null;
        max_value: number | null;
        tender_count: number;
      }>;
      total_divisions: number;
    }>(`/api/insights/price-benchmarks${query ? `?${query}` : ''}`);
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

  async searchEPazarItems(params?: Record<string, any>) {
    const query = new URLSearchParams(params || {}).toString();
    return this.request<EPazarItemsSearchResponse>(`/api/epazar/items?${query}`);
  }

  async getEPazarItemsAggregations(search?: string) {
    const query = search ? `?search=${encodeURIComponent(search)}` : '';
    return this.request<EPazarItemsAggregationsResponse>(`/api/epazar/items/aggregations${query}`);
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

  // ============================================================================
  // TRACKED COMPETITORS
  // ============================================================================

  async getTrackedCompetitors() {
    return this.request<{
      tracked_competitors: string[];
      count: number;
    }>('/api/personalization/tracked-competitors');
  }

  async addTrackedCompetitor(companyName: string) {
    return this.request<{
      message: string;
      tracked_competitors: string[];
    }>('/api/personalization/tracked-competitors', {
      method: 'POST',
      body: JSON.stringify({ company_name: companyName }),
    });
  }

  async removeTrackedCompetitor(companyName: string) {
    return this.request<{
      message: string;
      tracked_competitors: string[];
    }>('/api/personalization/tracked-competitors', {
      method: 'DELETE',
      body: JSON.stringify({ company_name: companyName }),
    });
  }

  async getTrackedCompetitorActivity(limit: number = 20) {
    return this.request<{
      activities: Array<{
        tender_id: string;
        title: string;
        competitor_name: string;
        status: string;
        estimated_value_mkd?: number;
        closing_date?: string;
        bid_amount_mkd?: number;
        is_winner?: boolean;
        rank?: number;
        activity_type: 'win' | 'bid';
      }>;
      total: number;
      tracked_count: number;
    }>(`/api/personalization/tracked-competitors/activity?limit=${limit}`);
  }

  // Competitor Stats (lightweight version of analyzeCompany)
  async getCompetitorStats(companyName: string) {
    return this.request<{
      name: string;
      wins: number;
      bids_count: number;
      win_rate: number;
      avg_discount?: number;
      total_value_mkd: number;
      specialty_areas?: string[];
    }>('/api/analytics/competitor-stats', {
      method: 'POST',
      body: JSON.stringify({ company_name: companyName }),
    });
  }

  // AI Company Analysis
  async analyzeCompany(companyName: string) {
    return this.request<{
      company_name: string;
      summary: string;
      tender_stats: {
        total_bids: number;
        total_wins: number;
        win_rate: number;
        avg_bid_value_mkd?: number;
        total_won_value_mkd?: number;
        first_bid_date?: string;
        last_bid_date?: string;
      };
      recent_wins: Array<{
        tender_id: string;
        title: string;
        procuring_entity: string;
        category: string;
        cpv_code: string;
        contract_value_mkd?: number;
        date?: string;
      }>;
      common_categories: Array<{
        category: string;
        bid_count: number;
        win_count: number;
        won_value_mkd: number;
      }>;
      frequent_institutions: Array<{
        institution: string;
        bid_count: number;
        win_count: number;
        avg_bid_mkd?: number;
      }>;
      product_specifications: Array<{
        item_name: string;
        unit?: string;
        unit_price_mkd?: number;
        quantity?: number;
        tender_title?: string;
        institution?: string;
      }>;
      ai_insights: string;
      analysis_timestamp: string;
    }>('/api/ai/company-analysis', {
      method: 'POST',
      body: JSON.stringify({ company_name: companyName }),
    });
  }

  // Bid Advice / Recommendation
  async getBidAdvice(tenderNumber: string, tenderYear: string) {
    return this.request<{
      tender_id: string;
      estimated_value: number;
      market_analysis: {
        avg_discount: number;
        typical_bidders: number;
        price_trend: string;
      };
      recommendations: Array<{
        strategy: string;
        recommended_bid: number;
        win_probability: number;
        reasoning: string;
      }>;
      competitor_insights: Array<{
        company: string;
        win_rate: number;
        avg_discount: number;
      }>;
      ai_summary: string;
    }>(`/api/tenders/by-id/${tenderNumber}/${tenderYear}/bid-advice`);
  }

  // Item Price Search
  async searchItemPrices(query: string, limit?: number): Promise<{
    query: string;
    results: Array<{
      item_name: string;
      unit_price?: number;
      total_price?: number;
      quantity?: number;
      unit?: string;
      tender_id: string;
      tender_title: string;
      date?: string;
      source: 'epazar' | 'nabavki' | 'document';
    }>;
    statistics: {
      count: number;
      min_price?: number;
      max_price?: number;
      avg_price?: number;
      median_price?: number;
    };
  }> {
    const params = new URLSearchParams();
    params.append('query', query);
    if (limit) params.append('limit', limit.toString());
    return this.request(`/api/ai/item-prices?${params.toString()}`);
  }

  // Head-to-Head Competitor Comparison
  async getHeadToHead(companyA: string, companyB: string, limit?: number): Promise<HeadToHeadResponse> {
    const params = new URLSearchParams();
    params.append('company_a', companyA);
    params.append('company_b', companyB);
    if (limit) params.append('limit', limit.toString());
    return this.request(`/api/competitors/head-to-head?${params.toString()}`);
  }

  // Competitor Activity Feed
  async getCompetitorActivity(companyNames: string[], limit: number = 50) {
    const params = new URLSearchParams();
    companyNames.forEach(name => params.append('company_names', name));
    params.append('limit', limit.toString());

    return this.request<{
      activities: Array<{
        type: 'won' | 'bid' | 'lost';
        company_name: string;
        tender_id: string;
        tender_title: string;
        amount?: number;
        timestamp?: string;
        details?: {
          estimated_value?: number;
          discount_percent?: number;
          num_bidders?: number;
          rank?: number;
        };
      }>;
      total_count: number;
      period: string;
    }>(`/api/competitors/activity?${params.toString()}`);
  }

  // ============================================================================
  // ALERTS API
  // ============================================================================

  async getAlerts() {
    return this.request<{
      alerts: Array<{
        id: string;
        name: string;
        alert_type: string;
        criteria: any;
        channels: string[];
        is_active: boolean;
        match_count?: number;
        created_at: string;
        updated_at?: string;
      }>;
      total: number;
    }>('/api/alerts');
  }

  async createAlert(alert: {
    name: string;
    alert_type: string;
    criteria: any;
    notification_channels?: string[];
  }) {
    return this.request<{
      id: string;
      name: string;
      alert_type: string;
      criteria: any;
      channels: string[];
      is_active: boolean;
      created_at: string;
    }>('/api/alerts', {
      method: 'POST',
      body: JSON.stringify(alert),
    });
  }

  async updateAlert(id: string, updates: {
    name?: string;
    criteria?: any;
    channels?: string[];
    is_active?: boolean;
  }) {
    return this.request<{
      id: string;
      name: string;
      alert_type: string;
      criteria: any;
      channels: string[];
      is_active: boolean;
      updated_at: string;
    }>(`/api/alerts/${encodeURIComponent(id)}`, {
      method: 'PUT',
      body: JSON.stringify(updates),
    });
  }

  async deleteAlert(id: string) {
    return this.request<{ message: string }>(`/api/alerts/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
  }

  async getAlertMatches(alertId?: string) {
    const params = alertId ? `?alert_id=${encodeURIComponent(alertId)}` : '';
    return this.request<{
      matches: Array<{
        match_id: string;
        alert_id: string;
        alert_name: string;
        tender_id: string;
        tender_title: string;
        match_score: number;
        match_reasons: string[];
        is_read: boolean;
        matched_at: string;
        tender?: {
          procuring_entity?: string;
          estimated_value_mkd?: number;
          closing_date?: string;
          cpv_code?: string;
        };
      }>;
      total: number;
    }>(`/api/alerts/matches${params}`);
  }

  async markMatchesRead(matchIds: string[]) {
    return this.request<{ message: string; updated_count: number }>('/api/alerts/matches/read', {
      method: 'POST',
      body: JSON.stringify({ match_ids: matchIds }),
    });
  }

  // ============================================================================
  // BRIEFINGS / DAILY DIGEST METHODS
  // ============================================================================

  async getTodayBriefing() {
    return this.request<DailyBriefing>('/api/briefings/today');
  }

  async getBriefingHistory(page: number = 1) {
    return this.request<BriefingHistoryResponse>(`/api/briefings/history?page=${page}`);
  }

  async getBriefingByDate(date: string) {
    return this.request<DailyBriefing>(`/api/briefings/${date}`);
  }

  async regenerateBriefing() {
    return this.request<DailyBriefing>('/api/briefings/generate', {
      method: 'POST',
    });
  }

  // ============================================================================
  // NOTIFICATIONS
  // ============================================================================

  async getNotifications(page: number = 1, pageSize: number = 20, unreadOnly: boolean = false, type?: string) {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize)
    });
    if (unreadOnly) params.append('unread', 'true');
    if (type) params.append('type', type);
    return this.request<{
      total: number;
      page: number;
      page_size: number;
      items: Array<{
        notification_id: string;
        user_id: string;
        type: string;
        title: string;
        message?: string;
        data: Record<string, any>;
        tender_id?: string;
        alert_id?: string;
        is_read: boolean;
        created_at: string;
      }>;
    }>(`/api/notifications?${params.toString()}`);
  }

  async getUnreadCount() {
    return this.request<{ unread_count: number }>('/api/notifications/unread-count');
  }

  async markNotificationRead(notificationIds: string | string[]) {
    const ids = Array.isArray(notificationIds) ? notificationIds : [notificationIds];
    return this.request<{ message: string; updated: number }>('/api/notifications/mark-read', {
      method: 'POST',
      body: JSON.stringify({ notification_ids: ids }),
    });
  }

  async markAllRead() {
    return this.request<{ message: string; updated: number }>('/api/notifications/mark-all-read', {
      method: 'POST',
    });
  }

  async deleteNotification(notificationId: string) {
    return this.request<{ message: string }>(`/api/notifications/${notificationId}`, {
      method: 'DELETE',
    });
  }

  // ============================================================================
  // INSIGHTS API
  // ============================================================================

  async getUpcomingOpportunities(cpvCode?: string) {
    const params = cpvCode ? new URLSearchParams({ cpv_prefix: cpvCode }) : '';
    return this.request<{
      closing_soon: Array<{
        tender_id: string;
        title: string;
        estimated_value_mkd: number | null;
        closing_date: string;
        days_left: number;
        category: string | null;
        procuring_entity: string | null;
        cpv_code: string | null;
      }>;
      closing_this_month: Array<{
        tender_id: string;
        title: string;
        estimated_value_mkd: number | null;
        closing_date: string;
        days_left: number;
        category: string | null;
        procuring_entity: string | null;
        cpv_code: string | null;
      }>;
      upcoming: Array<{
        tender_id: string;
        title: string;
        estimated_value_mkd: number | null;
        closing_date: string;
        days_left: number;
        category: string | null;
        procuring_entity: string | null;
        cpv_code: string | null;
      }>;
      total: number;
    }>(`/api/insights/upcoming-opportunities${params ? `?${params}` : ''}`);
  }

  async getActiveBuyers(category?: string) {
    const params = category ? `?category=${encodeURIComponent(category)}` : '';
    return this.request<{
      buyers: Array<{
        entity_name: string;
        tender_count: number;
        total_value: number | null;
        categories_breakdown: Record<string, number>; // e.g., {"Стоки": 5, "Услуги": 3}
        trend?: number; // percentage change from previous period
      }>;
      total: number;
    }>(`/api/insights/active-buyers${params}`);
  }

  async getTopWinners(cpvCode?: string) {
    const params = cpvCode ? new URLSearchParams({ cpv_prefix: cpvCode }) : new URLSearchParams();
    return this.request<{
      winners: Array<{
        name: string;
        win_count: number;
        total_value_won: number | null;
        categories: string[];
        avg_contract_value: number | null;
      }>;
      total: number;
    }>(`/api/insights/top-winners?${params.toString()}`);
  }

  async getSeasonalPatterns() {
    return this.request<{
      patterns: Array<{
        month: string; // "2024-01", "2024-02", etc.
        month_name: string; // "January 2025", etc.
        tender_count: number;
        total_value: number | null;
        avg_value: number | null;
        category_breakdown: Record<string, number>;
      }>;
      total_months: number;
    }>('/api/insights/seasonal-patterns');
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

export interface EPazarItemWithTender extends EPazarItem {
  tender_title?: string;
  contracting_authority?: string;
  tender_status?: string;
  tender_closing_date?: string;
}

export interface EPazarItemsSearchResponse {
  total: number;
  page: number;
  page_size: number;
  items: EPazarItemWithTender[];
}

export interface EPazarItemAggregation {
  item_name: string;
  unit?: string;
  occurrence_count: number;
  min_unit_price?: number;
  max_unit_price?: number;
  avg_unit_price?: number;
  total_quantity?: number;
  tender_count: number;
}

export interface EPazarItemsAggregationsResponse {
  aggregations: EPazarItemAggregation[];
}

// Head-to-Head Comparison Types
export interface HeadToHeadCategoryDominance {
  category: string;
  cpv_code?: string;
  win_count: number;
  total_count: number;
  win_rate: number;
}

export interface HeadToHeadConfrontation {
  tender_id: string;
  title: string;
  winner: string;
  company_a_bid: number | null;
  company_b_bid: number | null;
  date: string | null;
  estimated_value: number | null;
  num_bidders: number | null;
}

export interface HeadToHeadResponse {
  company_a: string;
  company_b: string;
  total_confrontations: number;
  company_a_wins: number;
  company_b_wins: number;
  ties: number;
  avg_bid_difference: number | null;
  company_a_categories: HeadToHeadCategoryDominance[];
  company_b_categories: HeadToHeadCategoryDominance[];
  recent_confrontations: HeadToHeadConfrontation[];
  ai_insights: string | null;
}

// Briefing Types
export interface BriefingTenderMatch {
  tender_id: string;
  title: string;
  procuring_entity?: string;
  estimated_value_mkd?: number;
  closing_date?: string;
  publication_date?: string;
  category?: string;
  cpv_code?: string;
  match_score: number;
  match_reasons: string[];
  alert_name?: string;
  days_remaining?: number;
  ai_recommendation?: string;
}

export interface DailyBriefing {
  date: string;
  user_id: string;
  total_new_tenders: number;
  total_matches: number;
  high_priority_count: number;
  high_priority: BriefingTenderMatch[];
  all_matches: BriefingTenderMatch[];
  ai_summary?: string;
  stats?: {
    total_new: number;
    matches: number;
    high_priority: number;
    competitors_active?: number;
  };
  generated_at?: string;
}

export interface BriefingHistoryItem {
  date: string;
  total_matches: number;
  high_priority_count: number;
  generated_at?: string;
}

export interface BriefingHistoryResponse {
  total: number;
  page: number;
  items: BriefingHistoryItem[];
}

export const api = new APIClient();
