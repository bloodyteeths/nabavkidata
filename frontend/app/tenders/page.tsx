"use client";

import { useEffect, useState } from "react";
import { TenderCard } from "@/components/tenders/TenderCard";
import { TenderFilters, type FilterState } from "@/components/tenders/TenderFilters";
import { TenderStats } from "@/components/tenders/TenderStats";
import { Button } from "@/components/ui/button";
import { api, type Tender } from "@/lib/api";
import { ChevronLeft, ChevronRight } from "lucide-react";

export default function TendersPage() {
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<FilterState>({});
  const [stats, setStats] = useState({ total: 0, open: 0, closed: 0, awarded: 0 });

  const limit = 20;

  useEffect(() => {
    loadTenders();
    loadStats();
  }, [page, filters]);

  async function loadTenders() {
    try {
      setLoading(true);
      const params: Record<string, any> = {
        page: page,
        page_size: limit,
      };

      if (filters.search) params.search = filters.search;
      if (filters.status) params.status = filters.status;
      if (filters.category) params.category = filters.category;
      if (filters.minBudget) params.min_value = filters.minBudget;
      if (filters.maxBudget) params.max_value = filters.maxBudget;
      if (filters.cpvCode) params.cpv_code = filters.cpvCode;

      const result = await api.getTenders(params);
      setTenders(result.items);
      setTotal(result.total);
    } catch (error) {
      console.error("Failed to load tenders:", error);
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
        awarded: 0, // Backend doesn't track awarded status
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
  };

  const totalPages = Math.ceil(total / limit);

  if (loading && page === 1) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground">Се вчитува...</p>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Истражувач на Тендери</h1>
        <p className="text-muted-foreground">
          Пребарувајте и филтрирајте тендери од целата база
        </p>
      </div>

      {/* Stats */}
      <TenderStats
        total={stats.total}
        open={stats.open}
        closed={stats.closed}
        awarded={stats.awarded}
      />

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Filters Sidebar */}
        <div className="lg:col-span-1">
          <TenderFilters
            filters={filters}
            onFiltersChange={handleFiltersChange}
            onReset={handleReset}
          />
        </div>

        {/* Tenders List */}
        <div className="lg:col-span-3 space-y-4">
          {/* Results Header */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              {total} резултати {filters.search && `за "${filters.search}"`}
            </p>
            <p className="text-sm text-muted-foreground">
              Страна {page} од {totalPages}
            </p>
          </div>

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
            <div className="flex items-center justify-center gap-2 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4" />
                Претходна
              </Button>
              <span className="text-sm text-muted-foreground px-4">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(page + 1)}
                disabled={page === totalPages}
              >
                Следна
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
