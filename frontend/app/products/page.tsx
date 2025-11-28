"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ExportButton } from "@/components/ExportButton";
import { CPVBrowser } from "@/components/cpv/CPVBrowser";
import { api, type ProductSearchResult, type ProductAggregation } from "@/lib/api";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Package,
  TrendingUp,
  Building2,
  Calendar,
  ExternalLink,
  Filter,
  SlidersHorizontal,
  X
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatDate } from "@/lib/utils";

// Utility functions
function formatPrice(price: number | undefined): string {
  if (!price) return "-";
  return new Intl.NumberFormat("mk-MK", {
    style: "currency",
    currency: "MKD",
    maximumFractionDigits: 0,
  }).format(price);
}

function formatQuantity(qty: number | undefined, unit: string | undefined): string {
  if (!qty) return "-";
  return `${qty.toLocaleString("mk-MK")} ${unit || ""}`.trim();
}

interface Filters {
  year?: number;
  cpv_code?: string;
  min_price?: number;
  max_price?: number;
  procuring_entity?: string;
}

type SortOption = "date_desc" | "date_asc" | "price_asc" | "price_desc" | "quantity_desc";

export default function ProductsPage() {
  // Hydration guard
  const [isHydrated, setIsHydrated] = useState(false);

  // Search state
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);

  // Data state
  const [products, setProducts] = useState<ProductSearchResult[]>([]);
  const [aggregations, setAggregations] = useState<ProductAggregation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [cpvCodes, setCpvCodes] = useState<Array<{ cpv_code: string; title?: string; tender_count?: number; total_value_mkd?: number | null }> | null>(null);

  // Pagination & Filters
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Filters>({});
  const [showFilters, setShowFilters] = useState(false);
  const [sortBy, setSortBy] = useState<SortOption>("date_desc");

  // Stats
  const [stats, setStats] = useState<{
    total_products: number;
    tenders_with_products: number;
    unique_products: number;
  } | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  // Refs
  const searchInputRef = useRef<HTMLInputElement>(null);
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  const pageSize = 20;

  // Hydration effect
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Load stats on mount
  useEffect(() => {
    if (!isHydrated) return;
    loadStats();
    loadCpvCodes();
  }, [isHydrated]);

  async function loadStats() {
    try {
      const result = await api.getProductStats();
      setStats(result);
    } catch (error) {
      console.error("Failed to load product stats:", error);
    }
  }

  async function loadCpvCodes() {
    try {
      const result = await api.getCPVCodes();
      setCpvCodes(result.cpv_codes || []);
    } catch (error) {
      console.error("Failed to load CPV codes:", error);
      setCpvCodes(null);
    }
  }

  // Debounced search - trigger suggestions and instant search
  useEffect(() => {
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (query.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      setDebouncedQuery("");
      return;
    }

    // Debounce for 300ms
    debounceTimerRef.current = setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [query]);

  // Fetch suggestions when debounced query changes
  useEffect(() => {
    if (debouncedQuery.length >= 2) {
      fetchSuggestions(debouncedQuery);
    }
  }, [debouncedQuery]);

  // Auto-search when debounced query changes and we have searched before
  useEffect(() => {
    if (debouncedQuery.length >= 2 && hasSearched) {
      searchProducts(debouncedQuery, 1);
    }
  }, [debouncedQuery, filters, sortBy]);

  async function fetchSuggestions(searchQuery: string) {
    if (searchQuery.length < 2) return;

    try {
      setLoadingSuggestions(true);
      const result = await api.getProductSuggestions(searchQuery, 10);
      setSuggestions(result.suggestions);
      setShowSuggestions(result.suggestions.length > 0);
    } catch (error) {
      console.error("Failed to fetch suggestions:", error);
    } finally {
      setLoadingSuggestions(false);
    }
  }

  const searchProducts = useCallback(async (searchQuery: string, searchPage: number = 1) => {
    if (!searchQuery.trim()) {
      toast.error("Please enter a search term");
      return;
    }

    try {
      setLoading(true);
      setHasSearched(true);
      setShowSuggestions(false);

      const [searchResult, aggResult] = await Promise.all([
        api.searchProducts({
          q: searchQuery,
          page: searchPage,
          page_size: pageSize,
          ...filters,
        }),
        searchPage === 1 ? api.getProductAggregations(searchQuery) : Promise.resolve(null),
      ]);

      // Apply client-side sorting
      let sortedProducts = [...searchResult.items];
      switch (sortBy) {
        case "price_asc":
          sortedProducts.sort((a, b) => (a.unit_price || 0) - (b.unit_price || 0));
          break;
        case "price_desc":
          sortedProducts.sort((a, b) => (b.unit_price || 0) - (a.unit_price || 0));
          break;
        case "quantity_desc":
          sortedProducts.sort((a, b) => (b.quantity || 0) - (a.quantity || 0));
          break;
        case "date_asc":
          sortedProducts.sort((a, b) => {
            const dateA = a.opening_date ? new Date(a.opening_date).getTime() : 0;
            const dateB = b.opening_date ? new Date(b.opening_date).getTime() : 0;
            return dateA - dateB;
          });
          break;
        case "date_desc":
        default:
          sortedProducts.sort((a, b) => {
            const dateA = a.opening_date ? new Date(a.opening_date).getTime() : 0;
            const dateB = b.opening_date ? new Date(b.opening_date).getTime() : 0;
            return dateB - dateA;
          });
          break;
      }

      setProducts(sortedProducts);
      setTotal(searchResult.total);
      setPage(searchPage);

      if (aggResult) {
        setAggregations(aggResult.aggregations);
      }
    } catch (error) {
      console.error("Product search failed:", error);
      toast.error("Search failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [filters, sortBy]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      searchProducts(query, 1);
    }
  };

  const handlePageChange = (newPage: number) => {
    searchProducts(query, newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    setShowSuggestions(false);
    searchProducts(suggestion, 1);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedSuggestionIndex((prev) =>
          prev < suggestions.length - 1 ? prev + 1 : prev
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedSuggestionIndex((prev) => (prev > 0 ? prev - 1 : -1));
        break;
      case "Enter":
        if (selectedSuggestionIndex >= 0) {
          e.preventDefault();
          handleSuggestionClick(suggestions[selectedSuggestionIndex]);
          setSelectedSuggestionIndex(-1);
        }
        break;
      case "Escape":
        setShowSuggestions(false);
        setSelectedSuggestionIndex(-1);
        break;
    }
  };

  const clearFilters = () => {
    setFilters({});
    toast.success("Filters cleared");
  };

  const hasActiveFilters = Object.values(filters).some(v => v !== undefined && v !== "");

  const totalPages = Math.ceil(total / pageSize);

  // Calculate price statistics from aggregations
  const priceStats = aggregations.length > 0 ? {
    min: Math.min(...aggregations.map(a => a.min_unit_price || Infinity).filter(p => p !== Infinity)),
    max: Math.max(...aggregations.map(a => a.max_unit_price || 0)),
    avg: aggregations.reduce((sum, a) => sum + (a.avg_unit_price || 0), 0) / aggregations.length,
  } : null;

  // Get available years from data
  const availableYears = Array.from(
    new Set(
      aggregations.flatMap(a => a.years)
    )
  ).sort((a, b) => b - a);

  // Wait for hydration
  if (!isHydrated) {
    return (
      <div className="flex items-center justify-center h-full p-8">
        <p className="text-muted-foreground">Се вчитува...</p>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl md:text-3xl font-bold flex items-center gap-2">
          <Package className="h-8 w-8" />
          Product Research
        </h1>
        <p className="text-sm md:text-base text-muted-foreground mt-1">
          Search and analyze products, medicines, equipment, and services across all tenders
        </p>
      </div>

      {/* Stats Cards */}
      {stats && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">{stats.total_products.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">Total Products</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">{stats.unique_products.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">Unique Products</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">{stats.tenders_with_products.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground">Tenders with Products</p>
              </CardContent>
            </Card>
      </div>
          {stats.total_products === 0 && (
            <Card className="border-dashed">
              <CardContent className="pt-6 text-center">
                <Package className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                <h3 className="font-medium mb-2">Податоците за производи се во подготовка</h3>
                <p className="text-sm text-muted-foreground">
                  Извлекувањето на детални информации за производи од тендерската документација е во тек.
                  Оваа функционалност ќе биде достапна наскоро.
                </p>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* CPV Browser (only when data exists) */}
      {cpvCodes && cpvCodes.length > 0 && (
        <CPVBrowser onSelect={(code) => setFilters((prev) => ({ ...prev, cpv_code: code }))} />
      )}

      {/* Search Form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Search Products</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <form onSubmit={handleSearch} className="relative">
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Input
                  ref={searchInputRef}
                  placeholder="Search for products (e.g., paracetamol, intraocular lens, medical equipment...)"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                  className="flex-1"
                  autoComplete="off"
                />
                {loadingSuggestions && (
                  <div className="absolute right-3 top-1/2 -translate-y-1/2">
                    <div className="animate-spin h-4 w-4 border-2 border-primary border-t-transparent rounded-full" />
                  </div>
                )}

                {/* Auto-suggestions dropdown */}
                {showSuggestions && suggestions.length > 0 && (
                  <div
                    ref={suggestionsRef}
                    className="absolute z-50 w-full mt-1 bg-background border rounded-md shadow-lg max-h-60 overflow-auto"
                  >
                    {suggestions.map((suggestion, index) => (
                      <button
                        key={index}
                        type="button"
                        onClick={() => handleSuggestionClick(suggestion)}
                        className={`w-full px-4 py-2 text-left hover:bg-accent transition-colors ${
                          index === selectedSuggestionIndex ? 'bg-accent' : ''
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Search className="h-4 w-4 text-muted-foreground" />
                          <span>{suggestion}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <Button type="submit" disabled={loading || !query.trim()}>
                <Search className="h-4 w-4 mr-2" />
                Search
              </Button>
              <Button
                type="button"
                variant="outline"
                onClick={() => setShowFilters(!showFilters)}
                className={hasActiveFilters ? "border-primary" : ""}
              >
                <SlidersHorizontal className="h-4 w-4 mr-2" />
                Filters
                {hasActiveFilters && (
                  <Badge variant="default" className="ml-2 h-5 px-1.5">
                    {Object.values(filters).filter(v => v !== undefined && v !== "").length}
                  </Badge>
                )}
              </Button>
            </div>
          </form>

          {/* Quick examples */}
          <div className="flex flex-wrap gap-2">
            <span className="text-xs text-muted-foreground">Examples:</span>
            {["paracetamol", "intraocular lens", "medical equipment", "IT services"].map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => {
                  setQuery(example);
                  searchProducts(example, 1);
                }}
                className="text-xs text-primary hover:underline"
              >
                {example}
              </button>
            ))}
          </div>

          {/* Filters Panel */}
          {showFilters && (
            <div className="border rounded-lg p-4 space-y-4 bg-muted/20">
              <div className="flex items-center justify-between">
                <h3 className="font-medium flex items-center gap-2">
                  <Filter className="h-4 w-4" />
                  Advanced Filters
                </h3>
                {hasActiveFilters && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearFilters}
                    className="text-xs"
                  >
                    <X className="h-3 w-3 mr-1" />
                    Clear all
                  </Button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {/* Year filter */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Year</label>
                  <Select
                    value={filters.year?.toString() || "all"}
                    onValueChange={(value) =>
                      setFilters(prev => ({ ...prev, year: value && value !== "all" ? parseInt(value) : undefined }))
                    }
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="All years" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All years</SelectItem>
                      {availableYears.map(year => (
                        <SelectItem key={year} value={year.toString()}>
                          {year}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* CPV Code filter */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">CPV Code</label>
                  <Input
                    placeholder="e.g., 33600000"
                    value={filters.cpv_code || ""}
                    onChange={(e) =>
                      setFilters(prev => ({ ...prev, cpv_code: e.target.value || undefined }))
                    }
                  />
                </div>

                {/* Procuring Entity filter */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Procuring Entity</label>
                  <Input
                    placeholder="e.g., Hospital name"
                    value={filters.procuring_entity || ""}
                    onChange={(e) =>
                      setFilters(prev => ({ ...prev, procuring_entity: e.target.value || undefined }))
                    }
                  />
                </div>

                {/* Min Price filter */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Min Price (MKD)</label>
                  <Input
                    type="number"
                    placeholder="0"
                    value={filters.min_price || ""}
                    onChange={(e) =>
                      setFilters(prev => ({
                        ...prev,
                        min_price: e.target.value ? parseFloat(e.target.value) : undefined
                      }))
                    }
                  />
                </div>

                {/* Max Price filter */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Max Price (MKD)</label>
                  <Input
                    type="number"
                    placeholder="No limit"
                    value={filters.max_price || ""}
                    onChange={(e) =>
                      setFilters(prev => ({
                        ...prev,
                        max_price: e.target.value ? parseFloat(e.target.value) : undefined
                      }))
                    }
                  />
                </div>

                {/* Sort by */}
                <div className="space-y-2">
                  <label className="text-sm font-medium">Sort By</label>
                  <Select
                    value={sortBy}
                    onValueChange={(value) => setSortBy(value as SortOption)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="date_desc">Date (Newest first)</SelectItem>
                      <SelectItem value="date_asc">Date (Oldest first)</SelectItem>
                      <SelectItem value="price_asc">Price (Low to High)</SelectItem>
                      <SelectItem value="price_desc">Price (High to Low)</SelectItem>
                      <SelectItem value="quantity_desc">Quantity (High to Low)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      {hasSearched && (
        <>
          {/* Price Statistics */}
          {priceStats && aggregations.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="text-lg font-bold text-green-600">{formatPrice(priceStats.min)}</div>
                  <p className="text-xs text-muted-foreground">Lowest Price</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-lg font-bold">{formatPrice(priceStats.avg)}</div>
                  <p className="text-xs text-muted-foreground">Average Price</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-lg font-bold text-red-600">{formatPrice(priceStats.max)}</div>
                  <p className="text-xs text-muted-foreground">Highest Price</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-lg font-bold">{aggregations.length}</div>
                  <p className="text-xs text-muted-foreground">Product Variants</p>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Aggregations Table */}
          {aggregations.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <TrendingUp className="h-5 w-5" />
                  Price Analysis by Product
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">Product</th>
                        <th className="text-right p-2">Avg. Price</th>
                        <th className="text-right p-2">Min Price</th>
                        <th className="text-right p-2">Max Price</th>
                        <th className="text-right p-2">Total Qty</th>
                        <th className="text-right p-2">Tenders</th>
                      </tr>
                    </thead>
                    <tbody>
                      {aggregations.slice(0, 10).map((agg, i) => (
                        <tr key={i} className="border-b last:border-0 hover:bg-muted/50">
                          <td className="p-2 font-medium">{agg.product_name}</td>
                          <td className="text-right p-2">{formatPrice(agg.avg_unit_price)}</td>
                          <td className="text-right p-2 text-green-600">{formatPrice(agg.min_unit_price)}</td>
                          <td className="text-right p-2 text-red-600">{formatPrice(agg.max_unit_price)}</td>
                          <td className="text-right p-2">{agg.total_quantity?.toLocaleString() || "-"}</td>
                          <td className="text-right p-2">{agg.tender_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {aggregations.length > 10 && (
                  <p className="text-xs text-muted-foreground mt-2 text-center">
                    Showing top 10 of {aggregations.length} variants
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Results Header */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <p className="text-sm text-muted-foreground">
                {total.toLocaleString()} results for "{query}"
              </p>
              {hasActiveFilters && (
                <p className="text-xs text-muted-foreground">
                  Filtered by: {Object.entries(filters)
                    .filter(([_, v]) => v !== undefined && v !== "")
                    .map(([k, v]) => `${k}=${v}`)
                    .join(", ")}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {totalPages > 1 && (
                <p className="text-sm text-muted-foreground">
                  Page {page} of {totalPages}
                </p>
              )}
              {products.length > 0 && (
                <ExportButton
                  data={products}
                  filename={`products-${query.replace(/\s+/g, '-')}-${new Date().toISOString().split('T')[0]}`}
                  columns={[
                    { key: 'name', label: 'Product Name' },
                    { key: 'quantity', label: 'Quantity' },
                    { key: 'unit', label: 'Unit' },
                    { key: 'unit_price', label: 'Unit Price (MKD)' },
                    { key: 'total_price', label: 'Total Price (MKD)' },
                    { key: 'cpv_code', label: 'CPV Code' },
                    { key: 'tender_title', label: 'Tender' },
                    { key: 'procuring_entity', label: 'Entity' },
                    { key: 'opening_date', label: 'Date' },
                  ]}
                />
              )}
            </div>
          </div>

          {/* Product Cards */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin h-8 w-8 border-4 border-primary border-t-transparent rounded-full mx-auto mb-4" />
                <p className="text-muted-foreground">Searching products...</p>
              </div>
            </div>
          ) : products.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Package className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-muted-foreground">No products found for "{query}"</p>
              <p className="text-xs text-muted-foreground mt-1">
                Try different search terms, adjust filters, or check spelling
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {products.map((product) => (
                <Card key={product.id} className="hover:border-primary/50 transition-colors">
                  <CardContent className="pt-6">
                    <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                      {/* Product Info */}
                      <div className="flex-1 space-y-2">
                        <h3 className="font-semibold text-lg">{product.name}</h3>

                        <div className="flex flex-wrap gap-2 text-sm">
                          {product.quantity && (
                            <Badge variant="secondary">
                              Qty: {formatQuantity(product.quantity, product.unit)}
                            </Badge>
                          )}
                          {product.unit_price && (
                            <Badge variant="outline">
                              Unit: {formatPrice(product.unit_price)}
                            </Badge>
                          )}
                          {product.total_price && (
                            <Badge className="bg-green-100 text-green-800 hover:bg-green-200">
                              Total: {formatPrice(product.total_price)}
                            </Badge>
                          )}
                          {product.cpv_code && (
                            <Badge variant="outline" className="font-mono">
                              CPV: {product.cpv_code}
                            </Badge>
                          )}
                        </div>

                        {/* Specifications */}
                        {product.specifications && Object.keys(product.specifications).length > 0 && (
                          <div className="text-xs text-muted-foreground pt-1">
                            <p className="font-medium">Specifications:</p>
                            <div className="flex flex-wrap gap-2 mt-1">
                              {Object.entries(product.specifications).slice(0, 3).map(([key, value]) => (
                                <span key={key} className="bg-muted px-2 py-1 rounded">
                                  {key}: {String(value)}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Tender Context */}
                        <div className="pt-2 border-t mt-2">
                          <div className="flex items-start gap-2 text-sm text-muted-foreground">
                            <Building2 className="h-4 w-4 mt-0.5 shrink-0" />
                            <div>
                              <p className="font-medium text-foreground">
                                {product.tender_title || "Untitled Tender"}
                              </p>
                              <p>{product.procuring_entity}</p>
                            </div>
                          </div>

                          <div className="flex flex-wrap gap-4 mt-2 text-xs text-muted-foreground">
                            {product.opening_date && (
                              <span className="flex items-center gap-1">
                                <Calendar className="h-3 w-3" />
                                {formatDate(product.opening_date)}
                              </span>
                            )}
                            {product.status && (
                              <Badge variant="outline" className="text-xs">
                                {product.status}
                              </Badge>
                            )}
                            {product.winner && (
                              <span className="text-green-600">
                                Winner: {product.winner}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex md:flex-col gap-2">
                        <Link href={`/tenders/${encodeURIComponent(product.tender_id)}`}>
                          <Button variant="outline" size="sm">
                            <ExternalLink className="h-4 w-4 mr-1" />
                            View Tender
                          </Button>
                        </Link>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 1 || loading}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(page + 1)}
                disabled={page === totalPages || loading}
              >
                Next
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
