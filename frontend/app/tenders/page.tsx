"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { TenderCard } from "@/components/tenders/TenderCard";
import { TenderFilters, type FilterState } from "@/components/tenders/TenderFilters";
import { TenderStats } from "@/components/tenders/TenderStats";
import { SavedSearches } from "@/components/SavedSearches";
import { Button } from "@/components/ui/button";
import { ExportButton } from "@/components/ExportButton";
import { api, type Tender } from "@/lib/api";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";

// Loading fallback for Suspense
function TendersLoadingFallback() {
  return (
    <div className="p-3 md:p-6 lg:p-8 space-y-4 md:space-y-6">
      <div>
        <Skeleton className="h-8 w-64 mb-2" />
        <Skeleton className="h-4 w-96" />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <Skeleton className="h-4 w-20 mb-2" />
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="space-y-4">
        {[...Array(5)].map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <Skeleton className="h-5 w-3/4 mb-2" />
              <Skeleton className="h-4 w-1/2" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

// Main content wrapped in Suspense boundary
export default function TendersPage() {
  return (
    <Suspense fallback={<TendersLoadingFallback />}>
      <TendersPageContent />
    </Suspense>
  );
}

function TendersPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [isHydrated, setIsHydrated] = useState(false);
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<FilterState>({});
  // Initialize with cached approximate values to avoid showing zeros while loading
  const [stats, setStats] = useState({ total: 273772, open: 833, closed: 545, awarded: 268491, cancelled: 2083 });
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  // Track if we should trigger a load (for manual apply button)
  const [shouldLoad, setShouldLoad] = useState(0);
  // Sorting
  const [sortBy, setSortBy] = useState('publication_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const limit = 20;

  // Sync filters to URL
  const syncFiltersToURL = (currentFilters: FilterState) => {
    const params = new URLSearchParams();

    if (currentFilters.search) {
      params.set('search', currentFilters.search);
    }
    // Only include status if explicitly set by user
    if (currentFilters.status && currentFilters.status !== 'all') {
      params.set('status', currentFilters.status);
    }
    if (currentFilters.category) {
      params.set('category', currentFilters.category);
    }
    if (currentFilters.cpvCode) {
      params.set('cpv_code', currentFilters.cpvCode);
    }
    if (currentFilters.entity) {
      params.set('entity', currentFilters.entity);
    }
    if (currentFilters.minBudget && currentFilters.minBudget > 0) {
      params.set('min_budget', currentFilters.minBudget.toString());
    }
    if (currentFilters.maxBudget && currentFilters.maxBudget > 0) {
      params.set('max_budget', currentFilters.maxBudget.toString());
    }
    if (currentFilters.dateFrom) {
      params.set('date_from', currentFilters.dateFrom);
    }
    if (currentFilters.dateTo) {
      params.set('date_to', currentFilters.dateTo);
    }
    if (currentFilters.procedureType) {
      params.set('procedure_type', currentFilters.procedureType);
    }
    if (currentFilters.closingDateFrom) {
      params.set('closing_date_from', currentFilters.closingDateFrom);
    }
    if (currentFilters.closingDateTo) {
      params.set('closing_date_to', currentFilters.closingDateTo);
    }

    const queryString = params.toString();
    const newUrl = queryString ? `/tenders?${queryString}` : '/tenders';

    // Use replace to avoid polluting browser history
    router.replace(newUrl);
  };

  // Hydration guard and URL params initialization
  useEffect(() => {
    setIsHydrated(true);

    // Read initial filters from URL params
    const initialFilters: FilterState = {};

    const status = searchParams.get('status');
    if (status) initialFilters.status = status;

    const search = searchParams.get('search');
    if (search) initialFilters.search = search;

    const category = searchParams.get('category');
    if (category) initialFilters.category = category;

    const cpvCode = searchParams.get('cpv_code');
    if (cpvCode) initialFilters.cpvCode = cpvCode;

    const entity = searchParams.get('entity');
    if (entity) initialFilters.entity = entity;

    const minBudget = searchParams.get('min_budget');
    if (minBudget) {
      const parsed = parseFloat(minBudget);
      if (!isNaN(parsed)) initialFilters.minBudget = parsed;
    }

    const maxBudget = searchParams.get('max_budget');
    if (maxBudget) {
      const parsed = parseFloat(maxBudget);
      if (!isNaN(parsed)) initialFilters.maxBudget = parsed;
    }

    const dateFrom = searchParams.get('date_from');
    if (dateFrom) initialFilters.dateFrom = dateFrom;

    const dateTo = searchParams.get('date_to');
    if (dateTo) initialFilters.dateTo = dateTo;

    const procedureType = searchParams.get('procedure_type');
    if (procedureType) initialFilters.procedureType = procedureType;

    const closingDateFrom = searchParams.get('closing_date_from');
    if (closingDateFrom) initialFilters.closingDateFrom = closingDateFrom;

    const closingDateTo = searchParams.get('closing_date_to');
    if (closingDateTo) initialFilters.closingDateTo = closingDateTo;

    // Handle closing_within parameter - convert to closing_date_to
    const closingWithin = searchParams.get('closing_within');
    if (closingWithin) {
      const days = parseInt(closingWithin, 10);
      if (!isNaN(days)) {
        const today = new Date();
        const futureDate = new Date();
        futureDate.setDate(today.getDate() + days);
        initialFilters.closingDateFrom = today.toISOString().split('T')[0];
        initialFilters.closingDateTo = futureDate.toISOString().split('T')[0];
      }
    }

    setFilters(initialFilters);
    if (Object.keys(initialFilters).length > 1) { // More than just status
      setShowFilters(true); // Show filters panel when filters are applied from URL
    }
    // Trigger reload with new filters
    setShouldLoad(prev => prev + 1);
  }, [searchParams]);

  useEffect(() => {
    if (!isHydrated) return;
    loadTenders();
  }, [isHydrated, page, shouldLoad, sortBy, sortOrder]);

  useEffect(() => {
    if (!isHydrated) return;
    loadStats();
  }, [isHydrated]);

  async function loadTenders() {
    try {
      setLoading(true);
      setError(null);
      const params: Record<string, any> = {
        page: page,
        page_size: limit,
        sort_by: sortBy,
        sort_order: sortOrder,
      };

      // Apply text search
      if (filters.search) params.search = filters.search;

      // Status filter - default to "open" (active tenders) if not specified
      // "all" means user explicitly wants all statuses (no filter)
      if (filters.status && filters.status !== 'all') {
        params.status = filters.status;
      } else if (!filters.status) {
        params.status = 'open';  // Show only active tenders by default
      }
      // If filters.status === 'all', don't add status param (shows all)

      // Category filter - pass exactly as selected
      if (filters.category) params.category = filters.category;

      // Budget filters - map to backend parameter names
      if (filters.minBudget && filters.minBudget > 0) {
        params.min_estimated_mkd = filters.minBudget;
      }
      if (filters.maxBudget && filters.maxBudget > 0) {
        params.max_estimated_mkd = filters.maxBudget;
      }

      // CPV code filter
      if (filters.cpvCode) params.cpv_code = filters.cpvCode;

      // Entity filter
      if (filters.entity) params.procuring_entity = filters.entity;

      // Date filters - map to backend parameter names (opening_date_from/to)
      if (filters.dateFrom) params.opening_date_from = filters.dateFrom;
      if (filters.dateTo) params.opening_date_to = filters.dateTo;

      // Closing date filters
      if (filters.closingDateFrom) params.closing_date_from = filters.closingDateFrom;
      if (filters.closingDateTo) params.closing_date_to = filters.closingDateTo;

      // Procedure type filter
      if (filters.procedureType) params.procedure_type = filters.procedureType;

      const result = await api.getTenders(params);
      setTenders(result.items);
      setTotal(result.total);
    } catch (error) {
      console.error("Failed to load tenders:", error);
      setError("Не успеавме да ги вчитаме тендерите. Обидете се повторно.");
      toast.error("Грешка при вчитување на тендери");
    } finally {
      setLoading(false);
    }
  }

  async function loadStats() {
    try {
      const result = await api.getTenderStats();
      setStats({
        total: result.total_tenders || 0,
        open: result.open_tenders || 0,
        closed: result.closed_tenders || 0,
        awarded: result.awarded_tenders || 0,
        cancelled: result.cancelled_tenders || 0,
      });
    } catch (error) {
      console.error("Failed to load stats:", error);
    }
  }

  const handleFiltersChange = (newFilters: FilterState) => {
    setFilters(newFilters);
    setPage(1);
  };

  const handleReset = () => {
    const defaultFilters = { status: 'open' };
    setFilters(defaultFilters);
    setPage(1);
    setShouldLoad(prev => prev + 1);
    // Clear URL params
    router.replace('/tenders?status=open');
  };

  const handleLoadSearch = (savedFilters: FilterState) => {
    setFilters(savedFilters);
    setPage(1);
    setShouldLoad(prev => prev + 1);
    syncFiltersToURL(savedFilters);
    toast.success("Пребарувањето е вчитано");
    // On mobile, close filters after loading a search
    if (window.innerWidth < 1024) {
      setShowFilters(false);
    }
  };

  const totalPages = Math.ceil(total / limit);

  if (!isHydrated || (loading && page === 1)) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Се вчитува...</p>
      </div>
    );
  }

  return (
    <div className="p-3 md:p-6 lg:p-8 space-y-4 md:space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-3xl font-bold">Истражувач на Тендери</h1>
        <p className="text-xs md:text-base text-muted-foreground">
          Пребарувајте и филтрирајте тендери по статус, категорија, буџет и други критериуми
        </p>
      </div>

      {/* Stats */}
      <TenderStats
        total={stats.total}
        open={stats.open}
        closed={stats.closed}
        awarded={stats.awarded}
        cancelled={stats.cancelled}
      />

      {/* Mobile Filter Toggle */}
      <div className="lg:hidden">
        <Button
          variant="outline"
          className="w-full"
          onClick={() => setShowFilters(!showFilters)}
        >
          <ChevronRight className={`mr-2 h-4 w-4 transition-transform ${showFilters ? 'rotate-90' : ''}`} />
          {showFilters ? 'Сокриј филтри' : 'Прикажи филтри'}
        </Button>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 md:gap-6">
        {/* Filters Sidebar */}
        <div className={`lg:col-span-1 space-y-4 ${showFilters ? 'block' : 'hidden lg:block'}`}>
          {/* Active Filters Display */}
          {(filters.status || filters.category || filters.procedureType || filters.search || filters.cpvCode || filters.entity || filters.minBudget || filters.maxBudget || filters.dateFrom || filters.dateTo || filters.closingDateFrom || filters.closingDateTo) && (
            <Card className="bg-muted/50">
              <CardContent className="p-3">
                <p className="text-xs font-medium mb-2 text-muted-foreground">Активни филтри:</p>
                <div className="flex flex-wrap gap-1.5">
                  {filters.status && filters.status !== 'all' && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-primary/10 text-primary">
                      Статус: {filters.status === 'open' ? 'Отворени' : filters.status === 'closed' ? 'Затворени' : filters.status === 'awarded' ? 'Доделени' : 'Откажани'}
                    </span>
                  )}
                  {filters.category && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                      Категорија: {filters.category}
                    </span>
                  )}
                  {filters.procedureType && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                      Постапка: {filters.procedureType}
                    </span>
                  )}
                  {filters.search && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300">
                      Пребарување: {filters.search}
                    </span>
                  )}
                  {filters.cpvCode && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300">
                      CPV: {filters.cpvCode}
                    </span>
                  )}
                  {filters.entity && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300">
                      Институција: {filters.entity.length > 20 ? filters.entity.substring(0, 20) + '...' : filters.entity}
                    </span>
                  )}
                  {(filters.minBudget || filters.maxBudget) && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300">
                      Буџет: {filters.minBudget ? `${filters.minBudget.toLocaleString()}+` : ''}{filters.minBudget && filters.maxBudget ? ' - ' : ''}{filters.maxBudget ? `${filters.maxBudget.toLocaleString()}` : ''}
                    </span>
                  )}
                  {(filters.closingDateFrom || filters.closingDateTo) && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300">
                      Краен рок: {filters.closingDateFrom || '...'} - {filters.closingDateTo || '...'}
                    </span>
                  )}
                  {(filters.dateFrom || filters.dateTo) && (
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-300">
                      Објава: {filters.dateFrom || '...'} - {filters.dateTo || '...'}
                    </span>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
          <TenderFilters
            filters={filters}
            onFiltersChange={handleFiltersChange}
            onApplyFilters={() => {
              // Increment shouldLoad to trigger useEffect after state updates
              setShouldLoad(prev => prev + 1);
              // Sync filters to URL for sharing
              syncFiltersToURL(filters);
              // On mobile, close filters after applying
              if (window.innerWidth < 1024) {
                setShowFilters(false);
              }
            }}
            onReset={handleReset}
          />
          <SavedSearches
            currentFilters={filters}
            onLoadSearch={handleLoadSearch}
          />
        </div>

        {/* Tenders List */}
        <div className="lg:col-span-3 space-y-4">
          {/* Results Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-2">
            <div className="flex items-center gap-3">
              <p className="text-xs md:text-sm text-muted-foreground">
                {total.toLocaleString()} резултати {filters.search && `за "${filters.search}"`}
              </p>
              {/* Sort Dropdown */}
              <select
                value={`${sortBy}-${sortOrder}`}
                onChange={(e) => {
                  const [newSortBy, newSortOrder] = e.target.value.split('-');
                  setSortBy(newSortBy);
                  setSortOrder(newSortOrder as 'asc' | 'desc');
                  setPage(1);
                }}
                className="text-xs md:text-sm bg-background border border-input rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-ring"
              >
                <option value="publication_date-desc">Најнови прво</option>
                <option value="publication_date-asc">Најстари прво</option>
                <option value="closing_date-asc">Краен рок (наскоро)</option>
                <option value="closing_date-desc">Краен рок (подоцна)</option>
                <option value="estimated_value_mkd-desc">Вредност (највисока)</option>
                <option value="estimated_value_mkd-asc">Вредност (најниска)</option>
              </select>
            </div>
            <div className="flex items-center justify-between sm:justify-end gap-2 w-full sm:w-auto">
              <p className="text-xs md:text-sm text-muted-foreground">
                Страна {page} од {totalPages}
              </p>
              {tenders.length > 0 && (
                <ExportButton
                  data={tenders}
                  filename={`тендери-${new Date().toISOString().split('T')[0]}`}
                  columns={[
                    { key: 'tender_id', label: 'ID' },
                    { key: 'title', label: 'Наслов' },
                    { key: 'procuring_entity', label: 'Наручител' },
                    { key: 'category', label: 'Категорија' },
                    { key: 'cpv_code', label: 'CPV Код' },
                    { key: 'procedure_type', label: 'Вид постапка' },
                    { key: 'estimated_value_mkd', label: 'Проценета вредност (МКД)' },
                    { key: 'actual_value_mkd', label: 'Договорена вредност (МКД)' },
                    { key: 'publication_date', label: 'Датум на објава' },
                    { key: 'opening_date', label: 'Датум на отворање' },
                    { key: 'closing_date', label: 'Краен рок' },
                    { key: 'status', label: 'Статус' },
                    { key: 'winner', label: 'Победник' },
                    { key: 'num_bidders', label: 'Број на понуди' },
                    { key: 'source_url', label: 'Линк' },
                  ]}
                />
              )}
            </div>
          </div>

          {error && (
            <div className="rounded-md border border-destructive/50 bg-destructive/10 text-destructive p-3 text-sm">
              {error}
            </div>
          )}

          {/* Tenders */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <p className="text-muted-foreground">Се вчитува...</p>
            </div>
          ) : tenders.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <p className="text-muted-foreground">Нема пронајдено тендери</p>
              <Button variant="outline" className="mt-4" onClick={handleReset}>
                Ресетирај филтри
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {tenders.map((tender) => (
                <TenderCard key={tender.tender_id} tender={tender} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex flex-col sm:flex-row items-center justify-center gap-2 sm:gap-4 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
                className="w-full sm:w-auto"
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                <span className="hidden sm:inline">Претходна</span>
                <span className="sm:hidden">Назад</span>
              </Button>
              <span className="text-xs md:text-sm text-muted-foreground px-2 sm:px-4">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page + 1)}
                disabled={page === totalPages}
                className="w-full sm:w-auto"
              >
                <span className="hidden sm:inline">Следна</span>
                <span className="sm:hidden">Напред</span>
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
