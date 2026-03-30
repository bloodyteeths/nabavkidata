"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, SlidersHorizontal, X, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { api } from "@/lib/api";

export interface FilterState {
  search?: string;
  status?: string;
  category?: string;
  procedureType?: string;
  minBudget?: number;
  maxBudget?: number;
  cpvCode?: string;
  entity?: string;
  dateFrom?: string;
  dateTo?: string;
  closingDateFrom?: string;
  closingDateTo?: string;
}

interface TenderFiltersProps {
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  onReset: () => void;
}

export function TenderFilters({ filters, onFiltersChange, onReset }: TenderFiltersProps) {
  const [showAdvanced, setShowAdvanced] = useState(false);

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

  // Show advanced section if any advanced filter is active
  useEffect(() => {
    if (filters.procedureType || filters.minBudget || filters.maxBudget || filters.cpvCode || filters.entity || filters.dateFrom || filters.dateTo || filters.closingDateFrom || filters.closingDateTo) {
      setShowAdvanced(true);
    }
  }, [filters]);

  // Direct filter update — no pending state, no apply button
  const updateFilter = (key: keyof FilterState, value: any) => {
    onFiltersChange({ ...filters, [key]: value });
  };

  // Reset all filters
  const handleReset = () => {
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

  // Check if any filter is active (for showing reset button)
  const hasActiveFilters = filters.category || filters.procedureType || filters.minBudget || filters.maxBudget || filters.cpvCode || filters.entity || filters.dateFrom || filters.dateTo || filters.closingDateFrom || filters.closingDateTo;

  return (
    <Card>
      <CardContent className="p-4 space-y-3">
        {/* Primary: Category */}
        <div>
          <label className="text-sm font-medium mb-1.5 block">Категорија</label>
          <Select
            value={filters.category || "all"}
            onValueChange={(value) => updateFilter("category", value === "all" ? undefined : value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Сите" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Сите категории</SelectItem>
              <SelectItem value="Стоки">Стоки</SelectItem>
              <SelectItem value="Услуги">Услуги</SelectItem>
              <SelectItem value="Работи">Работи</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Advanced Filters Toggle */}
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-between text-muted-foreground hover:text-foreground"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          <span className="flex items-center gap-2">
            <SlidersHorizontal className="h-3.5 w-3.5" />
            Напредни филтри
          </span>
          {showAdvanced ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        </Button>

        {/* Advanced Filters */}
        {showAdvanced && (
          <div className="space-y-3 pt-1 border-t">
            {/* Procedure Type */}
            <div>
              <label className="text-sm font-medium mb-1.5 block">Тип на постапка</label>
              <Select
                value={filters.procedureType || "all"}
                onValueChange={(value) => updateFilter("procedureType", value === "all" ? undefined : value)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Сите" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Сите</SelectItem>
                  <SelectItem value="Отворена постапка">Отворена постапка</SelectItem>
                  <SelectItem value="Ограничена постапка">Ограничена постапка</SelectItem>
                  <SelectItem value="Постапка со преговарање">Постапка со преговарање</SelectItem>
                  <SelectItem value="Директно договарање">Директно договарање</SelectItem>
                  <SelectItem value="Поедноставена постапка">Поедноставена постапка</SelectItem>
                  <SelectItem value="Рамковна спогодба">Рамковна спогодба</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Budget Range */}
            <div>
              <label className="text-sm font-medium mb-1.5 block">Буџет (МКД)</label>
              <div className="grid grid-cols-2 gap-2">
                <Input
                  type="number"
                  placeholder="Од"
                  value={filters.minBudget || ""}
                  onChange={(e) => updateFilter("minBudget", e.target.value ? Number(e.target.value) : undefined)}
                />
                <Input
                  type="number"
                  placeholder="До"
                  value={filters.maxBudget || ""}
                  onChange={(e) => updateFilter("maxBudget", e.target.value ? Number(e.target.value) : undefined)}
                />
              </div>
            </div>

            {/* CPV Code */}
            <div>
              <label className="text-sm font-medium mb-1.5 block">CPV Код</label>
              <div className="relative">
                <Input
                  placeholder="33 или медицинска опрема..."
                  value={cpvSearch || filters.cpvCode || ""}
                  onChange={(e) => {
                    setCpvSearch(e.target.value);
                    setShowCpvDropdown(true);
                    if (!e.target.value) {
                      updateFilter("cpvCode", undefined);
                    }
                  }}
                  onFocus={() => setShowCpvDropdown(true)}
                  onBlur={() => setTimeout(() => setShowCpvDropdown(false), 200)}
                />
                {cpvLoading && (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground absolute right-3 top-1/2 -translate-y-1/2" />
                )}
                {showCpvDropdown && cpvOptions.length > 0 && (
                  <div className="absolute z-50 w-full mt-1 max-h-48 overflow-auto border rounded-md bg-background shadow-lg">
                    {cpvOptions.map((opt) => (
                      <button
                        key={opt.code}
                        type="button"
                        className="w-full text-left text-sm hover:bg-accent px-3 py-2 border-b last:border-b-0"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          updateFilter("cpvCode", opt.code);
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
              {filters.cpvCode && (
                <div className="mt-1 text-xs text-muted-foreground flex items-center gap-1">
                  Избрано: <span className="font-mono">{filters.cpvCode}</span>
                  <button
                    type="button"
                    className="text-destructive hover:underline"
                    onClick={() => {
                      updateFilter("cpvCode", undefined);
                      setCpvSearch("");
                    }}
                  >
                    (отстрани)
                  </button>
                </div>
              )}
            </div>

            {/* Entity */}
            <div>
              <label className="text-sm font-medium mb-1.5 block">Институција</label>
              <div className="relative">
                <Input
                  placeholder="Пребарај институција..."
                  value={entitySearch || filters.entity || ""}
                  onChange={(e) => {
                    setEntitySearch(e.target.value);
                    setShowEntityDropdown(true);
                    if (!e.target.value) {
                      updateFilter("entity", undefined);
                    }
                  }}
                  onFocus={() => setShowEntityDropdown(true)}
                  onBlur={() => setTimeout(() => setShowEntityDropdown(false), 200)}
                />
                {entityLoading && (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground absolute right-3 top-1/2 -translate-y-1/2" />
                )}
                {showEntityDropdown && entityOptions.length > 0 && (
                  <div className="absolute z-50 w-full mt-1 max-h-48 overflow-auto border rounded-md bg-background shadow-lg">
                    {entityOptions.map((opt) => (
                      <button
                        key={opt.entity_id}
                        type="button"
                        className="w-full text-left text-sm hover:bg-accent px-3 py-2 border-b last:border-b-0 truncate"
                        onMouseDown={(e) => {
                          e.preventDefault();
                          updateFilter("entity", opt.entity_name);
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
              {filters.entity && (
                <div className="mt-1 text-xs text-muted-foreground flex items-center gap-1">
                  <span className="truncate max-w-[180px]">{filters.entity}</span>
                  <button
                    type="button"
                    className="text-destructive hover:underline flex-shrink-0"
                    onClick={() => {
                      updateFilter("entity", undefined);
                      setEntitySearch("");
                    }}
                  >
                    (отстрани)
                  </button>
                </div>
              )}
            </div>

            {/* Closing Date Range */}
            <div>
              <label className="text-sm font-medium mb-1.5 block">Краен рок</label>
              <div className="space-y-2">
                <Input
                  type="date"
                  value={filters.closingDateFrom || ""}
                  onChange={(e) => updateFilter("closingDateFrom", e.target.value)}
                />
                <Input
                  type="date"
                  value={filters.closingDateTo || ""}
                  onChange={(e) => updateFilter("closingDateTo", e.target.value)}
                />
              </div>
            </div>

            {/* Publication Date Range */}
            <div>
              <label className="text-sm font-medium mb-1.5 block">Датум на објава</label>
              <div className="space-y-2">
                <Input
                  type="date"
                  value={filters.dateFrom || ""}
                  onChange={(e) => updateFilter("dateFrom", e.target.value)}
                />
                <Input
                  type="date"
                  value={filters.dateTo || ""}
                  onChange={(e) => updateFilter("dateTo", e.target.value)}
                />
              </div>
            </div>
          </div>
        )}

        {/* Reset Button - only when filters are active */}
        {hasActiveFilters && (
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={handleReset}
          >
            <X className="h-3.5 w-3.5 mr-1.5" />
            Ресетирај филтри
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
