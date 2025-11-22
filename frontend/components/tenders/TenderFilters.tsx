"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, SlidersHorizontal, X } from "lucide-react";

export interface FilterState {
  search?: string;
  status?: string;
  category?: string;
  minBudget?: number;
  maxBudget?: number;
  cpvCode?: string;
}

interface TenderFiltersProps {
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  onReset: () => void;
}

export function TenderFilters({ filters, onFiltersChange, onReset }: TenderFiltersProps) {
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
          <Input
            placeholder="Внеси CPV код"
            value={filters.cpvCode || ""}
            onChange={(e) => updateFilter("cpvCode", e.target.value)}
          />
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
