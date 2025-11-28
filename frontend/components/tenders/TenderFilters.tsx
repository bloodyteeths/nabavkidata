"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, SlidersHorizontal, X, Loader2, Filter } from "lucide-react";
import { api } from "@/lib/api";

export interface FilterState {
  search?: string;
  status?: string;
  category?: string;
  minBudget?: number;
  maxBudget?: number;
  cpvCode?: string;
  entity?: string;
  dateFrom?: string;
  dateTo?: string;
}

interface TenderFiltersProps {
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  onApplyFilters: () => void;
  onReset: () => void;
}

export function TenderFilters({ filters, onFiltersChange, onApplyFilters, onReset }: TenderFiltersProps) {
  // Local state for pending filter changes (not applied yet)
  const [pendingFilters, setPendingFilters] = useState<FilterState>(filters);

  // CPV autocomplete state
  const [cpvSearch, setCpvSearch] = useState("");
  const [cpvOptions, setCpvOptions] = useState<Array<{ code: string; name: string; name_mk: string }>>([]);
  const [cpvLoading, setCpvLoading] = useState(false);
  const [showCpvDropdown, setShowCpvDropdown] = useState(false);

  // Entity autocomplete state
  const [entitySearch, setEntitySearch] = useState("");
  const [entityOptions, setEntityOptions] = useState<Array<{ entity_id: string; entity_name: string }>>([]);
  const [entityLoading, setEntityLoading] = useState(false);
  const [showEntityDropdown, setShowEntityDropdown] = useState(false);

  // Initialize date filters with last 2 months on first render
  useEffect(() => {
    // Only set defaults if no filters are set yet
    if (!filters.dateFrom && !filters.dateTo && Object.keys(filters).length === 0) {
      const now = new Date();
      const twoMonthsAgo = new Date(now.getFullYear(), now.getMonth() - 2, now.getDate());
      const defaultFilters = {
        dateFrom: twoMonthsAgo.toISOString().split('T')[0],
        dateTo: now.toISOString().split('T')[0],
      };
      setPendingFilters(defaultFilters);
    }
  }, []);

  // Sync pending filters with parent filters
  useEffect(() => {
    setPendingFilters(filters);
  }, [filters]);

  const updatePendingFilter = (key: keyof FilterState, value: any) => {
    setPendingFilters(prev => ({ ...prev, [key]: value }));
  };

  // Apply all pending filters
  const handleApply = () => {
    onFiltersChange(pendingFilters);
    onApplyFilters();
  };

  // Reset all filters
  const handleReset = () => {
    setPendingFilters({});
    setCpvSearch("");
    setEntitySearch("");
    onReset();
  };

  // CPV search with debounce
  const searchCPV = useCallback(async (search: string) => {
    if (search.length < 2) {
      setCpvOptions([]);
      return;
    }
    setCpvLoading(true);
    try {
      const response = await api.searchCPVCodes(search, 15);
      setCpvOptions(response.results || []);
    } catch (error) {
      console.error("CPV search failed:", error);
      setCpvOptions([]);
    } finally {
      setCpvLoading(false);
    }
  }, []);

  // Entity search with debounce
  const searchEntity = useCallback(async (search: string) => {
    if (search.length < 2) {
      setEntityOptions([]);
      return;
    }
    setEntityLoading(true);
    try {
      const response = await api.searchEntities(search, 15);
      setEntityOptions(response.items || []);
    } catch (error) {
      console.error("Entity search failed:", error);
      setEntityOptions([]);
    } finally {
      setEntityLoading(false);
    }
  }, []);

  // Debounced CPV search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (cpvSearch) searchCPV(cpvSearch);
    }, 300);
    return () => clearTimeout(timer);
  }, [cpvSearch, searchCPV]);

  // Debounced entity search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (entitySearch) searchEntity(entitySearch);
    }, 300);
    return () => clearTimeout(timer);
  }, [entitySearch, searchEntity]);

  return (
    <Card>
      <CardHeader className="pb-4">
        <CardTitle className="text-base flex items-center gap-2">
          <SlidersHorizontal className="h-4 w-4" />
          Филтри
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Пребарај тендери..."
            className="pl-9"
            value={pendingFilters.search || ""}
            onChange={(e) => updatePendingFilter("search", e.target.value)}
          />
        </div>

        {/* Status - Using correct values */}
        <div>
          <label className="text-sm font-medium mb-2 block">Статус</label>
          <Select
            value={pendingFilters.status || "all"}
            onValueChange={(value) => updatePendingFilter("status", value === "all" ? undefined : value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Сите" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Сите</SelectItem>
              <SelectItem value="open">Отворени</SelectItem>
              <SelectItem value="closed">Затворени</SelectItem>
              <SelectItem value="awarded">Доделени</SelectItem>
              <SelectItem value="cancelled">Откажани</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Category - Using actual DB values */}
        <div>
          <label className="text-sm font-medium mb-2 block">Категорија</label>
          <Select
            value={pendingFilters.category || "all"}
            onValueChange={(value) => updatePendingFilter("category", value === "all" ? undefined : value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Сите" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Сите</SelectItem>
              <SelectItem value="Стоки">Стоки</SelectItem>
              <SelectItem value="Услуги">Услуги</SelectItem>
              <SelectItem value="Работи">Работи</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Budget Range - No immediate filtering */}
        <div>
          <label className="text-sm font-medium mb-2 block">Буџет (МКД)</label>
          <div className="grid grid-cols-2 gap-2">
            <Input
              type="number"
              placeholder="Од"
              value={pendingFilters.minBudget || ""}
              onChange={(e) => updatePendingFilter("minBudget", e.target.value ? Number(e.target.value) : undefined)}
            />
            <Input
              type="number"
              placeholder="До"
              value={pendingFilters.maxBudget || ""}
              onChange={(e) => updatePendingFilter("maxBudget", e.target.value ? Number(e.target.value) : undefined)}
            />
          </div>
        </div>

        {/* CPV Code - Dropdown with search */}
        <div>
          <label className="text-sm font-medium mb-2 block">CPV Код</label>
          <p className="text-xs text-muted-foreground mb-1">
            Внесете код (пр. 33) или категорија (пр. медицинска)
          </p>
          <div className="relative">
            <Input
              placeholder="33 или медицинска опрема..."
              value={cpvSearch || pendingFilters.cpvCode || ""}
              onChange={(e) => {
                setCpvSearch(e.target.value);
                setShowCpvDropdown(true);
                if (!e.target.value) {
                  updatePendingFilter("cpvCode", undefined);
                }
              }}
              onFocus={() => setShowCpvDropdown(true)}
              onBlur={() => setTimeout(() => setShowCpvDropdown(false), 200)}
            />
            {cpvLoading && (
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground absolute right-3 top-1/2 -translate-y-1/2" />
            )}

            {/* CPV Dropdown */}
            {showCpvDropdown && cpvOptions.length > 0 && (
              <div className="absolute z-50 w-full mt-1 max-h-48 overflow-auto border rounded-md bg-background shadow-lg">
                {cpvOptions.map((opt) => (
                  <button
                    key={opt.code}
                    type="button"
                    className="w-full text-left text-sm hover:bg-accent px-3 py-2 border-b last:border-b-0"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      updatePendingFilter("cpvCode", opt.code);
                      setCpvSearch(opt.code);
                      setShowCpvDropdown(false);
                    }}
                  >
                    <span className="font-mono text-xs text-primary mr-2">{opt.code}</span>
                    <span className="text-muted-foreground">{opt.name_mk || opt.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {pendingFilters.cpvCode && (
            <div className="mt-1 text-xs text-muted-foreground flex items-center gap-1">
              Избрано: <span className="font-mono">{pendingFilters.cpvCode}</span>
              <button
                type="button"
                className="text-destructive hover:underline"
                onClick={() => {
                  updatePendingFilter("cpvCode", undefined);
                  setCpvSearch("");
                }}
              >
                (отстрани)
              </button>
            </div>
          )}
        </div>

        {/* Entity - Dropdown with search */}
        <div>
          <label className="text-sm font-medium mb-2 block">Институција</label>
          <div className="relative">
            <Input
              placeholder="Пребарај институција..."
              value={entitySearch || pendingFilters.entity || ""}
              onChange={(e) => {
                setEntitySearch(e.target.value);
                setShowEntityDropdown(true);
                if (!e.target.value) {
                  updatePendingFilter("entity", undefined);
                }
              }}
              onFocus={() => setShowEntityDropdown(true)}
              onBlur={() => setTimeout(() => setShowEntityDropdown(false), 200)}
            />
            {entityLoading && (
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground absolute right-3 top-1/2 -translate-y-1/2" />
            )}

            {/* Entity Dropdown */}
            {showEntityDropdown && entityOptions.length > 0 && (
              <div className="absolute z-50 w-full mt-1 max-h-48 overflow-auto border rounded-md bg-background shadow-lg">
                {entityOptions.map((opt) => (
                  <button
                    key={opt.entity_id}
                    type="button"
                    className="w-full text-left text-sm hover:bg-accent px-3 py-2 border-b last:border-b-0 truncate"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      updatePendingFilter("entity", opt.entity_name);
                      setEntitySearch(opt.entity_name);
                      setShowEntityDropdown(false);
                    }}
                  >
                    {opt.entity_name}
                  </button>
                ))}
              </div>
            )}
          </div>
          {pendingFilters.entity && (
            <div className="mt-1 text-xs text-muted-foreground flex items-center gap-1">
              <span className="truncate max-w-[180px]">{pendingFilters.entity}</span>
              <button
                type="button"
                className="text-destructive hover:underline flex-shrink-0"
                onClick={() => {
                  updatePendingFilter("entity", undefined);
                  setEntitySearch("");
                }}
              >
                (отстрани)
              </button>
            </div>
          )}
        </div>

        {/* Date Range */}
        <div>
          <label className="text-sm font-medium mb-2 block">Период</label>
          <div className="space-y-2">
            <Input
              type="date"
              placeholder="Од"
              value={pendingFilters.dateFrom || ""}
              onChange={(e) => updatePendingFilter("dateFrom", e.target.value)}
            />
            <Input
              type="date"
              placeholder="До"
              value={pendingFilters.dateTo || ""}
              onChange={(e) => updatePendingFilter("dateTo", e.target.value)}
            />
          </div>
        </div>

        {/* Actions - Apply and Reset */}
        <div className="space-y-2 pt-2">
          <Button
            className="w-full"
            onClick={handleApply}
          >
            <Filter className="h-4 w-4 mr-2" />
            Примени филтри
          </Button>
          <Button
            variant="outline"
            className="w-full"
            onClick={handleReset}
          >
            <X className="h-4 w-4 mr-2" />
            Ресетирај
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
