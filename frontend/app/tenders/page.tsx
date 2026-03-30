"use client";

import { Suspense, useEffect, useState, useRef, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { TenderCard } from "@/components/tenders/TenderCard";
import { TenderFilters, type FilterState } from "@/components/tenders/TenderFilters";
import { TenderStats } from "@/components/tenders/TenderStats";
import { SavedSearches } from "@/components/SavedSearches";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ExportButton } from "@/components/ExportButton";
import { api, type Tender } from "@/lib/api";
import { ChevronLeft, ChevronRight, Search, SlidersHorizontal } from "lucide-react";
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
      <div className="flex gap-2">
        {[...Array(3)].map((_, i) => (
          <Skeleton key={i} className="h-10 w-32 rounded-lg" />
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
  const [stats, setStats] = useState({ total: 0, open: 0, awarded: 0 });
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  // Track whether date filter was auto-applied (not explicitly set by user)
  const [isAutoDateFilter, setIsAutoDateFilter] = useState(false);
  // Local search input state (for debounce without race condition)
  const [searchInput, setSearchInput] = useState("");
  // Sorting
  const [sortBy, setSortBy] = useState('publication_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const limit = 20;

  // Track if initial URL params have been loaded
  const initializedRef = useRef(false);
  // Debounce timer for search text
  const searchTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Sync filters to URL
  const syncFiltersToURL = useCallback((currentFilters: FilterState) => {
    const params = new URLSearchParams();

    if (currentFilters.search) {
      params.set('search', currentFilters.search);
    }
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
    router.replace(newUrl);
  }, [router]);

  // Hydration guard and URL params initialization
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    setIsHydrated(true);

    // Read initial filters from URL params
    const initialFilters: FilterState = {};

    const status = searchParams.get('status');
    if (status) initialFilters.status = status;

    const search = searchParams.get('search');
    if (search) {
      initialFilters.search = search;
      if (!status) initialFilters.status = 'all';
    }

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

    // Handle closing_within parameter
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

    // Default to last 30 days if no date filter and no search
    if (!initialFilters.search && !initialFilters.dateFrom && !initialFilters.dateTo && !initialFilters.closingDateFrom && !initialFilters.closingDateTo) {
      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
      initialFilters.dateFrom = thirtyDaysAgo.toISOString().split('T')[0];
      setIsAutoDateFilter(true);
    }

    // Initialize local search input from URL
    if (initialFilters.search) {
      setSearchInput(initialFilters.search);
    }

    // Default status to open
    if (!initialFilters.status) {
      initialFilters.status = 'open';
    }

    setFilters(initialFilters);
    if (Object.keys(initialFilters).length > 2) {
      setShowFilters(true);
    }
  }, [searchParams]);

  // Auto-load tenders when filters change (debounced for text, instant for dropdowns)
  useEffect(() => {
    if (!isHydrated) return;
    const timer = setTimeout(() => {
      loadTenders();
      syncFiltersToURL(filters);
    }, 300);
    return () => clearTimeout(timer);
  }, [isHydrated, JSON.stringify(filters), page, sortBy, sortOrder]);

  // Load global stats once
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

      if (filters.search) params.search = filters.search;

      // Status filter
      if (filters.status && filters.status !== 'all') {
        params.status = filters.status;
      } else if (!filters.status) {
        params.status = 'open';
      }

      if (filters.category) params.category = filters.category;
      if (filters.minBudget && filters.minBudget > 0) params.min_estimated_mkd = filters.minBudget;
      if (filters.maxBudget && filters.maxBudget > 0) params.max_estimated_mkd = filters.maxBudget;
      if (filters.cpvCode) params.cpv_code = filters.cpvCode;
      if (filters.entity) params.procuring_entity = filters.entity;
      if (filters.dateFrom) params.opening_date_from = filters.dateFrom;
      if (filters.dateTo) params.opening_date_to = filters.dateTo;
      if (filters.closingDateFrom) params.closing_date_from = filters.closingDateFrom;
      if (filters.closingDateTo) params.closing_date_to = filters.closingDateTo;
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
        awarded: result.awarded_tenders || 0,
      });
    } catch (error) {
      console.error("Failed to load stats:", error);
    }
  }

  const handleFiltersChange = (newFilters: FilterState) => {
    // If user explicitly changed date filters, mark as user-set
    if (newFilters.dateFrom !== filters.dateFrom || newFilters.dateTo !== filters.dateTo) {
      setIsAutoDateFilter(false);
    }
    setFilters(newFilters);
    setPage(1);
  };

  const handleStatusChange = (status: string) => {
    const newFilters = { ...filters, status };
    // When switching to "all" or "awarded", only remove auto-applied date defaults (not user-set dates)
    if (status === 'all' || status === 'awarded') {
      if (isAutoDateFilter) {
        delete newFilters.dateFrom;
        delete newFilters.dateTo;
        setIsAutoDateFilter(false);
      }
    } else if (status === 'open' && !newFilters.dateFrom && !newFilters.search) {
      // When switching to open, apply 30-day default
      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
      newFilters.dateFrom = thirtyDaysAgo.toISOString().split('T')[0];
      setIsAutoDateFilter(true);
    }
    setFilters(newFilters);
    setPage(1);
  };

  const handleSearchChange = (value: string) => {
    // Update local input immediately for responsive UI
    setSearchInput(value);
    // Debounce the actual filter update
    if (searchTimerRef.current) clearTimeout(searchTimerRef.current);
    searchTimerRef.current = setTimeout(() => {
      const newFilters = { ...filters, search: value || undefined };
      // When searching, show all statuses and remove auto date filter
      if (value && filters.status !== 'all') {
        newFilters.status = 'all';
        if (isAutoDateFilter) {
          delete newFilters.dateFrom;
          delete newFilters.dateTo;
          setIsAutoDateFilter(false);
        }
      }
      setFilters(newFilters);
      setPage(1);
    }, 500);
  };

  const searchAllStatuses = () => {
    const newFilters: FilterState = { search: filters.search, status: 'all' };
    setFilters(newFilters);
    setPage(1);
  };

  const handleReset = () => {
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
    const defaultFilters: FilterState = {
      status: 'open',
      dateFrom: thirtyDaysAgo.toISOString().split('T')[0]
    };
    setFilters(defaultFilters);
    setSearchInput("");
    setIsAutoDateFilter(true);
    setPage(1);
    router.replace('/tenders?status=open');
  };

  const handleLoadSearch = (savedFilters: FilterState) => {
    setFilters(savedFilters);
    setPage(1);
    toast.success("Пребарувањето е вчитано");
    if (window.innerWidth < 1024) {
      setShowFilters(false);
    }
  };

  const totalPages = Math.ceil(total / limit);

  // Status label for display
  const getStatusLabel = () => {
    switch (filters.status) {
      case 'open': return 'отворени';
      case 'awarded': return 'доделени';
      case 'closed': return 'затворени';
      case 'cancelled': return 'откажани';
      default: return '';
    }
  };

  if (!isHydrated) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Се вчитува...</p>
      </div>
    );
  }

  return (
    <div className="p-3 md:p-6 lg:p-8 space-y-4 md:space-y-5">
      {/* Header */}
      <div>
        <h1 className="text-xl md:text-2xl font-bold">Тендери</h1>
      </div>

      {/* Search Bar - prominent, above everything */}
      <div className="relative max-w-2xl">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Пребарај тендери по клучен збор..."
          className="pl-9 h-11 text-base"
          value={searchInput}
          onChange={(e) => handleSearchChange(e.target.value)}
        />
      </div>

      {/* Status Tabs - clickable, show counts */}
      <TenderStats
        stats={stats}
        activeStatus={filters.status || 'open'}
        onStatusChange={handleStatusChange}
        loading={loading && page === 1}
      />

      {/* Mobile Filter Toggle */}
      <div className="lg:hidden">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowFilters(!showFilters)}
        >
          <SlidersHorizontal className="mr-2 h-4 w-4" />
          {showFilters ? 'Сокриј филтри' : 'Филтри'}
        </Button>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 md:gap-6">
        {/* Filters Sidebar */}
        <div className={`lg:col-span-1 space-y-4 ${showFilters ? 'block' : 'hidden lg:block'}`}>
          <TenderFilters
            filters={filters}
            onFiltersChange={handleFiltersChange}
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
              <p className="text-sm font-medium">
                {loading ? 'Се вчитува...' : (
                  <>
                    <span className="font-bold">{total.toLocaleString()}</span>
                    {' '}{getStatusLabel()} тендери
                    {isAutoDateFilter && <span className="text-muted-foreground"> (последните 30 дена)</span>}
                    {filters.search && <span className="text-muted-foreground"> за &ldquo;{filters.search}&rdquo;</span>}
                  </>
                )}
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
              <p className="text-xs text-muted-foreground">
                Страна {page} од {totalPages || 1}
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
            <div className="rounded-md border border-destructive/50 bg-destructive/10 text-destructive p-3 text-sm flex items-center justify-between">
              <span>{error}</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => loadTenders()}
                className="ml-3 shrink-0"
              >
                Обиди се повторно
              </Button>
            </div>
          )}

          {/* Tenders */}
          {loading && page === 1 ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <Card key={i}>
                  <CardContent className="p-4">
                    <Skeleton className="h-5 w-3/4 mb-2" />
                    <Skeleton className="h-4 w-1/2" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : tenders.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center max-w-md mx-auto">
              {filters.search && filters.status !== 'all' ? (
                <>
                  <Search className="h-12 w-12 mb-3 text-muted-foreground/30" />
                  <p className="text-muted-foreground mb-1">
                    Нема отворени тендери за <strong>&ldquo;{filters.search}&rdquo;</strong>
                  </p>
                  <p className="text-sm text-muted-foreground mb-4">
                    Има <strong>{stats.awarded.toLocaleString()}</strong> доделени тендери во базата. Погледнете ги историските резултати за да видите цени, победници и спецификации.
                  </p>
                  <Button onClick={searchAllStatuses} className="mb-2">
                    <Search className="h-4 w-4 mr-2" />
                    Пребарај низ сите тендери
                  </Button>
                  <Button variant="outline" size="sm" onClick={handleReset}>
                    Ресетирај филтри
                  </Button>
                </>
              ) : filters.search ? (
                <>
                  <Search className="h-12 w-12 mb-3 text-muted-foreground/30" />
                  <p className="text-muted-foreground mb-2">
                    Нема резултати за <strong>&ldquo;{filters.search}&rdquo;</strong>
                  </p>
                  <div className="text-sm text-muted-foreground text-left space-y-1 mb-4">
                    <p>Совети за подобро пребарување:</p>
                    <ul className="list-disc list-inside space-y-0.5">
                      <li>Обидете се со пократок збор</li>
                      <li>Пробајте на кирилица и латиница</li>
                      <li>Користете CPV код ако го знаете</li>
                    </ul>
                  </div>
                  <Button variant="outline" onClick={handleReset}>
                    Ресетирај филтри
                  </Button>
                </>
              ) : (
                <>
                  <p className="text-muted-foreground">Нема пронајдено тендери</p>
                  <div className="flex gap-2 mt-4">
                    <Button variant="outline" onClick={handleReset}>
                      Ресетирај филтри
                    </Button>
                    <Button variant="outline" onClick={() => loadTenders()}>
                      Обиди се повторно
                    </Button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className="space-y-3">
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
