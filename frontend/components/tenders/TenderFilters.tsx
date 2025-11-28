"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, SlidersHorizontal, X, Loader2 } from "lucide-react";

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
  onReset: () => void;
  cpvAutocomplete?: {
    value: string;
    onChange: (v: string) => void;
    options: Array<{ cpv_code: string; title: string }>;
    loading: boolean;
    onSelect: (code: string) => void;
  };
}

export function TenderFilters({ filters, onFiltersChange, onReset, cpvAutocomplete }: TenderFiltersProps) {
  const updateFilter = (key: keyof FilterState, value: any) => {
    onFiltersChange({ ...filters, [key]: value });
  };

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
            value={filters.search || ""}
            onChange={(e) => updateFilter("search", e.target.value)}
          />
        </div>

        {/* Status */}
        <div>
          <label className="text-sm font-medium mb-2 block">Статус</label>
          <Select
            value={filters.status || "all"}
            onValueChange={(value) => updateFilter("status", value === "all" ? undefined : value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Сите" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Сите</SelectItem>
              <SelectItem value="open">Отворени</SelectItem>
              <SelectItem value="closed">Затворени</SelectItem>
              <SelectItem value="awarded">Доделени</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Category */}
        <div>
          <label className="text-sm font-medium mb-2 block">Категорија</label>
          <Select
            value={filters.category || "all"}
            onValueChange={(value) => updateFilter("category", value === "all" ? undefined : value)}
          >
            <SelectTrigger>
              <SelectValue placeholder="Сите" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Сите</SelectItem>
              <SelectItem value="it">ИТ</SelectItem>
              <SelectItem value="construction">Градежништво</SelectItem>
              <SelectItem value="consulting">Консултинг</SelectItem>
              <SelectItem value="equipment">Опрема</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Budget Range */}
        <div>
          <label className="text-sm font-medium mb-2 block">Буџет (МКД)</label>
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
          <label className="text-sm font-medium mb-2 block">CPV Код</label>
          <div className="space-y-2">
            <div className="relative">
              <Input
                placeholder="Внеси или пребарај CPV"
                value={cpvAutocomplete ? cpvAutocomplete.value : filters.cpvCode || ""}
                onChange={(e) => {
                  if (cpvAutocomplete) {
                    cpvAutocomplete.onChange(e.target.value);
                  } else {
                    updateFilter("cpvCode", e.target.value);
                  }
                }}
              />
              {cpvAutocomplete?.loading && (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground absolute right-3 top-1/2 -translate-y-1/2" />
              )}
            </div>
            {cpvAutocomplete && cpvAutocomplete.options.length > 0 && (
              <div className="max-h-40 overflow-auto border rounded-md p-2 space-y-1 bg-background">
                {cpvAutocomplete.options.map((opt) => (
                  <button
                    key={opt.cpv_code}
                    className="w-full text-left text-sm hover:bg-accent rounded px-2 py-1"
                    onClick={() => {
                      cpvAutocomplete.onSelect(opt.cpv_code);
                    }}
                  >
                    <span className="font-mono text-xs mr-2">{opt.cpv_code}</span>
                    {opt.title}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Entity */}
        <div>
          <label className="text-sm font-medium mb-2 block">Институција</label>
          <Input
            placeholder="Пребарај институција..."
            value={filters.entity || ""}
            onChange={(e) => updateFilter("entity", e.target.value)}
          />
        </div>

        {/* Date Range */}
        <div>
          <label className="text-sm font-medium mb-2 block">Период</label>
          <div className="space-y-2">
            <Input
              type="date"
              placeholder="Од"
              value={filters.dateFrom || ""}
              onChange={(e) => updateFilter("dateFrom", e.target.value)}
            />
            <Input
              type="date"
              placeholder="До"
              value={filters.dateTo || ""}
              onChange={(e) => updateFilter("dateTo", e.target.value)}
            />
          </div>
        </div>

        {/* Actions */}
        <Button
          variant="outline"
          className="w-full"
          onClick={onReset}
        >
          <X className="h-4 w-4 mr-2" />
          Ресетирај
        </Button>
      </CardContent>
    </Card>
  );
}
