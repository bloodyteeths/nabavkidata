"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Filter, X, RotateCcw } from "lucide-react";
import { api } from "@/lib/api";

export interface ProductFilterState {
  search?: string;
  cpvCode?: string;
  cpvName?: string;
  year?: number;
  minPrice?: number;
  maxPrice?: number;
  procuringEntity?: string;
}

interface ProductFiltersProps {
  filters: ProductFilterState;
  onApply: (filters: ProductFilterState) => void;
  onReset: () => void;
}

const CURRENT_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: CURRENT_YEAR - 2017 }, (_, i) => CURRENT_YEAR - i);

export function ProductFilters({ filters, onApply, onReset }: ProductFiltersProps) {
  const [local, setLocal] = useState<ProductFilterState>(filters);

  // CPV autocomplete state
  const [cpvSearch, setCpvSearch] = useState("");
  const [cpvResults, setCpvResults] = useState<Array<{ code: string; name_mk?: string; name?: string }>>([]);
  const [cpvLoading, setCpvLoading] = useState(false);
  const [showCpvDropdown, setShowCpvDropdown] = useState(false);
  const cpvTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Entity autocomplete state
  const [entitySearch, setEntitySearch] = useState("");
  const [entityOptions, setEntityOptions] = useState<Array<{ entity_id: string; entity_name: string }>>([]);
  const [entityLoading, setEntityLoading] = useState(false);
  const [showEntityDropdown, setShowEntityDropdown] = useState(false);
  const entityTimerRef = useRef<NodeJS.Timeout | null>(null);

  const [hasChanges, setHasChanges] = useState(false);

  // Sync external filter changes
  useEffect(() => {
    setLocal(filters);
    setHasChanges(false);
  }, [filters]);

  // Track unsaved changes
  useEffect(() => {
    const changed =
      local.year !== filters.year ||
      local.minPrice !== filters.minPrice ||
      local.maxPrice !== filters.maxPrice ||
      local.procuringEntity !== filters.procuringEntity ||
      local.cpvCode !== filters.cpvCode;
    setHasChanges(changed);
  }, [local, filters]);

  // CPV autocomplete
  useEffect(() => {
    if (cpvTimerRef.current) clearTimeout(cpvTimerRef.current);
    if (cpvSearch.length < 2) {
      setCpvResults([]);
      setShowCpvDropdown(false);
      return;
    }
    cpvTimerRef.current = setTimeout(async () => {
      try {
        setCpvLoading(true);
        const res = await api.searchCPVCodes(cpvSearch, 10);
        setCpvResults(res.results || []);
        setShowCpvDropdown((res.results || []).length > 0);
      } catch {
        setCpvResults([]);
      } finally {
        setCpvLoading(false);
      }
    }, 300);
    return () => { if (cpvTimerRef.current) clearTimeout(cpvTimerRef.current); };
  }, [cpvSearch]);

  // Entity autocomplete
  const searchEntity = useCallback(async (search: string) => {
    if (search.length < 2) {
      setEntityOptions([]);
      setShowEntityDropdown(false);
      return;
    }
    try {
      setEntityLoading(true);
      const response = await api.searchEntities(search, 10);
      setEntityOptions(response.items || []);
      setShowEntityDropdown((response.items || []).length > 0);
    } catch {
      setEntityOptions([]);
    } finally {
      setEntityLoading(false);
    }
  }, []);

  useEffect(() => {
    if (entityTimerRef.current) clearTimeout(entityTimerRef.current);
    if (entitySearch.length < 2) {
      setEntityOptions([]);
      setShowEntityDropdown(false);
      return;
    }
    entityTimerRef.current = setTimeout(() => {
      searchEntity(entitySearch);
    }, 300);
    return () => { if (entityTimerRef.current) clearTimeout(entityTimerRef.current); };
  }, [entitySearch, searchEntity]);

  const handleApply = () => {
    onApply(local);
    setHasChanges(false);
  };

  const handleReset = () => {
    setLocal({});
    setCpvSearch("");
    setEntitySearch("");
    onReset();
  };

  const activeCount = [
    local.year,
    local.minPrice,
    local.maxPrice,
    local.procuringEntity,
    local.cpvCode,
  ].filter((v) => v !== undefined && v !== null && v !== "").length;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Filter className="h-4 w-4" />
            Филтри
            {activeCount > 0 && (
              <Badge variant="default" className="h-5 px-1.5 text-xs">
                {activeCount}
              </Badge>
            )}
          </CardTitle>
          {activeCount > 0 && (
            <Button variant="ghost" size="sm" onClick={handleReset} className="h-7 text-xs">
              <RotateCcw className="h-3 w-3 mr-1" />
              Ресетирај
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* CPV Code */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">CPV Категорија</label>
          {local.cpvCode ? (
            <div className="flex items-center gap-2 p-2 border rounded-md bg-muted/30">
              <span className="text-sm flex-1 truncate">
                <span className="font-mono text-xs mr-1">{local.cpvCode}</span>
                {local.cpvName && <span className="text-muted-foreground">- {local.cpvName}</span>}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={() => setLocal((prev) => ({ ...prev, cpvCode: undefined, cpvName: undefined }))}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ) : (
            <div className="relative">
              <Input
                placeholder="Внесете букви за опции..."
                value={cpvSearch}
                onChange={(e) => setCpvSearch(e.target.value)}
                onFocus={() => cpvResults.length > 0 && setShowCpvDropdown(true)}
                className="text-sm"
              />
              {cpvLoading && (
                <div className="absolute right-2 top-1/2 -translate-y-1/2">
                  <div className="animate-spin h-3 w-3 border-2 border-primary border-t-transparent rounded-full" />
                </div>
              )}
              {showCpvDropdown && cpvResults.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-background border rounded-md shadow-lg max-h-48 overflow-auto">
                  {cpvResults.map((r) => (
                    <button
                      key={r.code}
                      className="block w-full text-left px-3 py-2 hover:bg-accent text-sm"
                      onClick={() => {
                        setLocal((prev) => ({ ...prev, cpvCode: r.code, cpvName: r.name_mk || r.name }));
                        setCpvSearch("");
                        setShowCpvDropdown(false);
                      }}
                    >
                      <span className="font-mono text-xs mr-2">{r.code}</span>
                      {r.name_mk || r.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Year */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">Година</label>
          <Select
            value={local.year?.toString() || "all"}
            onValueChange={(v) =>
              setLocal((prev) => ({ ...prev, year: v !== "all" ? parseInt(v) : undefined }))
            }
          >
            <SelectTrigger className="text-sm">
              <SelectValue placeholder="Сите години" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Сите години</SelectItem>
              {YEARS.map((y) => (
                <SelectItem key={y} value={y.toString()}>
                  {y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Price Range */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">Ценовен опсег (МКД)</label>
          <div className="grid grid-cols-2 gap-2">
            <Input
              type="number"
              placeholder="Мин"
              value={local.minPrice ?? ""}
              onChange={(e) =>
                setLocal((prev) => ({
                  ...prev,
                  minPrice: e.target.value ? parseFloat(e.target.value) : undefined,
                }))
              }
              className="text-sm"
            />
            <Input
              type="number"
              placeholder="Макс"
              value={local.maxPrice ?? ""}
              onChange={(e) =>
                setLocal((prev) => ({
                  ...prev,
                  maxPrice: e.target.value ? parseFloat(e.target.value) : undefined,
                }))
              }
              className="text-sm"
            />
          </div>
        </div>

        {/* Procuring Entity - with autocomplete */}
        <div className="space-y-1.5">
          <label className="text-xs font-medium text-muted-foreground">Договорен орган</label>
          {local.procuringEntity ? (
            <div className="flex items-center gap-2 p-2 border rounded-md bg-muted/30">
              <span className="text-sm flex-1 truncate">
                {local.procuringEntity}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0"
                onClick={() => {
                  setLocal((prev) => ({ ...prev, procuringEntity: undefined }));
                  setEntitySearch("");
                }}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ) : (
            <div className="relative">
              <Input
                placeholder="Внесете букви за опции..."
                value={entitySearch}
                onChange={(e) => setEntitySearch(e.target.value)}
                onFocus={() => entityOptions.length > 0 && setShowEntityDropdown(true)}
                className="text-sm"
              />
              {entityLoading && (
                <div className="absolute right-2 top-1/2 -translate-y-1/2">
                  <div className="animate-spin h-3 w-3 border-2 border-primary border-t-transparent rounded-full" />
                </div>
              )}
              {showEntityDropdown && entityOptions.length > 0 && (
                <div className="absolute z-50 w-full mt-1 bg-background border rounded-md shadow-lg max-h-48 overflow-auto">
                  {entityOptions.map((opt) => (
                    <button
                      key={opt.entity_id}
                      className="block w-full text-left px-3 py-2 hover:bg-accent text-sm truncate"
                      onClick={() => {
                        setLocal((prev) => ({ ...prev, procuringEntity: opt.entity_name }));
                        setEntitySearch("");
                        setShowEntityDropdown(false);
                      }}
                    >
                      {opt.entity_name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Apply Button */}
        <Button onClick={handleApply} className="w-full relative" size="sm">
          Примени филтри
          {hasChanges && (
            <span className="absolute -top-1 -right-1 h-2.5 w-2.5 bg-orange-500 rounded-full animate-pulse" />
          )}
        </Button>
      </CardContent>
    </Card>
  );
}
