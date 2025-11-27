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
  const [dataset, setDataset] = useState<"active" | "awarded" | "cancelled">(
    "active"
  );
  const [error, setError] = useState<string | null>(null);
  const [awardedCount, setAwardedCount] = useState(0);
  const [quickFilters, setQuickFilters] = useState({
    procedureType: null as string | null,
    statusFilter: null as string | null,
  });

  const limit = 20;

  // Hydration guard
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    loadTenders();
  }, [isHydrated, page, filters, dataset, quickFilters]);

  useEffect(() => {
    if (!isHydrated) return;
    loadStats();
    loadAwardedCount();
  }, [isHydrated]);

  async function loadAwardedCount() {
    try {
      const result = await api.getTenders({
        source_category: "awarded",
        page: 1,
        page_size: 1
      });
      setAwardedCount(result.total || 0);
    } catch (err) {
      console.error("Failed to get awarded count:", err);
      setAwardedCount(0);
    }
  }

  async function loadTenders() {
    try {
      setLoading(true);
      setError(null);
      const params: Record<string, any> = {
        page: page,
        page_size: limit,
        source_category: dataset, // Filter by source_category (active, awarded, cancelled)
      };

      // Force open status only when browsing the active dataset
      if (dataset === "active") {
        params.status = "open";
      }

      if (filters.search) params.search = filters.search;
      if (filters.status) params.status = filters.status;
      if (filters.category) params.category = filters.category;
      if (filters.minBudget) params.min_estimated_mkd = filters.minBudget;
      if (filters.maxBudget) params.max_estimated_mkd = filters.maxBudget;
      if (filters.cpvCode) params.cpv_code = filters.cpvCode;
      if (filters.entity) params.procuring_entity = filters.entity;
      if (filters.dateFrom) params.date_from = filters.dateFrom;
      if (filters.dateTo) params.date_to = filters.dateTo;

      // Apply quick filters
      if (quickFilters.procedureType) params.procedure_type = quickFilters.procedureType;
      if (quickFilters.statusFilter) params.status = quickFilters.statusFilter;

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
    setQuickFilters({ procedureType: null, statusFilter: null });
    setPage(1);
  };

  const handleLoadSearch = (savedFilters: FilterState) => {
    setFilters(savedFilters);
    setPage(1);
    toast.success("Пребарувањето е вчитано");
  };

  const handleQuickProcedureFilter = (type: string) => {
    setQuickFilters(prev => ({
      ...prev,
      procedureType: prev.procedureType === type ? null : type
    }));
    setPage(1);
  };

  const handleQuickStatusFilter = (status: string) => {
    setQuickFilters(prev => ({
      ...prev,
      statusFilter: prev.statusFilter === status ? null : status
    }));
    setPage(1);
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
          Пребарувајте и филтрирајте тендери по категорија: активни, доделени или поништени
        </p>
      </div>

      {/* Dataset Tabs */}
      <div className="flex flex-wrap gap-2">
        {(["active", "awarded", "cancelled"] as const).map((key) => {
          const labels: Record<typeof key, string> = {
            active: "Активни",
            awarded: `Доделени (${awardedCount.toLocaleString()})`,
            cancelled: "Поништени",
          };
          const isActive = dataset === key;
          return (
            <Button
              key={key}
              variant={isActive ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setDataset(key);
                setPage(1);
              }}
            >
              {labels[key]}
            </Button>
          );
        })}
      </div>

      {/* Quick Filters */}
      <div className="space-y-3">
        <div className="flex flex-col gap-2">
          {/* Procedure Type Filters */}
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-muted-foreground">Брзо филтрирање по тип на постапка:</span>
            <div className="flex flex-wrap gap-2">
              {["Отворена постапка", "Ограничена постапка", "Преговарачка постапка", "Конкурентен дијалог"].map((type) => (
                <Button
                  key={type}
                  variant={quickFilters.procedureType === type ? "default" : "outline"}
                  size="sm"
                  onClick={() => handleQuickProcedureFilter(type)}
                >
                  {type}
                </Button>
              ))}
              {quickFilters.procedureType && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setQuickFilters(prev => ({ ...prev, procedureType: null }))}
                >
                  Откажи
                </Button>
              )}
            </div>
          </div>

          {/* Status Quick Filters - only show if not on specific dataset */}
          {dataset === "active" && (
            <div className="flex flex-col gap-2">
              <span className="text-sm font-medium text-muted-foreground">Брзо филтрирање по статус:</span>
              <div className="flex flex-wrap gap-2">
                {["open", "closed"].map((status) => (
                  <Button
                    key={status}
                    variant={quickFilters.statusFilter === status ? "default" : "outline"}
                    size="sm"
                    onClick={() => handleQuickStatusFilter(status)}
                  >
                    {status === "open" ? "Отворени" : "Затворени"}
                  </Button>
                ))}
                <Button
                  variant={quickFilters.statusFilter === null ? "default" : "outline"}
                  size="sm"
                  onClick={() => setQuickFilters(prev => ({ ...prev, statusFilter: null }))}
                >
                  Сите
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Stats */}
      <TenderStats
        total={stats.total}
        open={stats.open}
        closed={stats.closed}
        awarded={stats.awarded}
      />

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 md:gap-6">
        {/* Filters Sidebar */}
        <div className="lg:col-span-1 space-y-4">
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
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <p className="text-xs md:text-sm text-muted-foreground">
              {total.toLocaleString()} резултати {filters.search && `за "${filters.search}"`}
              {dataset === "active" && " · активни тендери"}
              {dataset === "awarded" && " · доделени договори"}
              {dataset === "cancelled" && " · поништени тендери"}
            </p>
            <div className="flex items-center gap-2">
              <p className="text-xs md:text-sm text-muted-foreground">
                Страна {page} од {totalPages}
              </p>
              {tenders.length > 0 && (
                <ExportButton
                  data={tenders}
                  filename={`тендери-${dataset}-${new Date().toISOString().split('T')[0]}`}
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
