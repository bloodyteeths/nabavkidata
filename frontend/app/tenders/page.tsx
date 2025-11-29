"use client";

import { useEffect, useState } from "react";
import { TenderCard } from "@/components/tenders/TenderCard";
import { TenderFilters, type FilterState } from "@/components/tenders/TenderFilters";
import { TenderStats } from "@/components/tenders/TenderStats";
import { SavedSearches } from "@/components/SavedSearches";
import { Button } from "@/components/ui/button";
import { ExportButton } from "@/components/ExportButton";
import { api, type Tender } from "@/lib/api";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { toast } from "sonner";

export default function TendersPage() {
  const [isHydrated, setIsHydrated] = useState(false);
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<FilterState>({});
  const [stats, setStats] = useState({ total: 0, open: 0, closed: 0, awarded: 0 });
  const [error, setError] = useState<string | null>(null);
  const limit = 20;

  const [showFilters, setShowFilters] = useState(false);

  // Hydration guard
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Track if we should trigger a load (for manual apply button)
  const [shouldLoad, setShouldLoad] = useState(0);

  useEffect(() => {
    if (!isHydrated) return;
    loadTenders();
  }, [isHydrated, page, shouldLoad]);

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
      };

      // Apply text search
      if (filters.search) params.search = filters.search;

      // Status filter
      if (filters.status) {
        params.status = filters.status;
      }

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
    setFilters({});
    setPage(1);
    setShouldLoad(prev => prev + 1);
  };

  const handleLoadSearch = (savedFilters: FilterState) => {
    setFilters(savedFilters);
    setPage(1);
    setShouldLoad(prev => prev + 1);
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
    <div className="p-4 md:p-6 lg:p-8 space-y-4 md:space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold">Истражувач на Тендери</h1>
        <p className="text-sm md:text-base text-muted-foreground">
          Пребарувајте и филтрирајте тендери по статус, категорија, буџет и други критериуми
        </p>
      </div>

      {/* Stats */}
      <TenderStats
        total={stats.total}
        open={stats.open}
        closed={stats.closed}
        awarded={stats.awarded}
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
          <TenderFilters
            filters={filters}
            onFiltersChange={handleFiltersChange}
            onApplyFilters={() => {
              // Increment shouldLoad to trigger useEffect after state updates
              setShouldLoad(prev => prev + 1);
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
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <p className="text-xs md:text-sm text-muted-foreground">
              {total.toLocaleString()} резултати {filters.search && `за "${filters.search}"`}
            </p>
            <div className="flex items-center gap-2">
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
                    { key: 'procuring_entity', label: 'Наручилац' },
                    { key: 'estimated_value_mkd', label: 'Проценета вредност (МКД)' },
                    { key: 'closing_date', label: 'Краен рок' },
                    { key: 'status', label: 'Статус' },
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
