"use client";

import { Suspense, useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ExportButton } from "@/components/ExportButton";
import { CategoryGrid, type Division } from "@/components/products/CategoryGrid";
import { ProductCard } from "@/components/products/ProductCard";
import { ProductFilters, type ProductFilterState } from "@/components/products/ProductFilters";
import { api, type ProductSearchResult, type ProductAggregation } from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Package,
  TrendingUp,
  ArrowLeft,
  SlidersHorizontal,
  DollarSign,
  Lock,
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import { UpgradePrompt } from "@/components/billing/UpgradePrompt";

// Sort options
type SortOption = "date_desc" | "date_asc" | "price_asc" | "price_desc" | "quantity_desc";

const SORT_LABELS: Record<SortOption, string> = {
  date_desc: "Најнови прво",
  date_asc: "Најстари прво",
  price_asc: "Цена (ниска → висока)",
  price_desc: "Цена (висока → ниска)",
  quantity_desc: "Количина (најголема)",
};

// Example searches for browse mode
const EXAMPLE_SEARCHES = [
  "парацетамол",
  "канцелариски мебел",
  "медицинска опрема",
  "ИТ услуги",
  "градежни работи",
  "храна",
];

function formatPrice(price: number | undefined): string {
  if (!price) return "-";
  return new Intl.NumberFormat("mk-MK", {
    style: "currency",
    currency: "MKD",
    maximumFractionDigits: 0,
  }).format(price);
}

// Loading fallback for Suspense
function ProductsLoadingFallback() {
  return (
    <div className="p-3 md:p-6 lg:p-8 space-y-6">
      <div>
        <Skeleton className="h-8 w-64 mb-2" />
        <Skeleton className="h-4 w-96" />
      </div>
      <Skeleton className="h-12 w-full max-w-2xl mx-auto" />
      <div className="flex gap-2 justify-center">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-7 w-24 rounded-full" />
        ))}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {[...Array(12)].map((_, i) => (
          <Card key={i}>
            <CardContent className="p-4">
              <Skeleton className="h-8 w-8 rounded-md mb-2" />
              <Skeleton className="h-4 w-3/4 mb-1" />
              <Skeleton className="h-3 w-1/2" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export default function ProductsPage() {
  return (
    <Suspense fallback={<ProductsLoadingFallback />}>
      <ProductsPageContent />
    </Suspense>
  );
}

function ProductsPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  // Hydration guard
  const [isHydrated, setIsHydrated] = useState(false);

  // Browse mode state
  const [divisions, setDivisions] = useState<Division[]>([]);
  const [divisionsLoading, setDivisionsLoading] = useState(true);

  // Search state
  const [searchInput, setSearchInput] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = useState(-1);
  const suggestionsTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Results state
  const [products, setProducts] = useState<ProductSearchResult[]>([]);
  const [aggregations, setAggregations] = useState<ProductAggregation[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState<SortOption>("date_desc");

  // Filters
  const [filters, setFilters] = useState<ProductFilterState>({});
  const [showMobileFilters, setShowMobileFilters] = useState(false);

  // Price gating & quota
  const [priceGated, setPriceGated] = useState(false);
  const [priceViewsRemaining, setPriceViewsRemaining] = useState<number | null>(null);
  const [priceViewsLimit, setPriceViewsLimit] = useState<number | null>(null);

  // Popular product names for current category
  const [popularNames, setPopularNames] = useState<Array<{ name: string; count: number }>>([]);
  const [popularNamesLoading, setPopularNamesLoading] = useState(false);

  // Mode: determined by URL params
  const [categoryName, setCategoryName] = useState<string>("");

  const pageSize = 20;

  // Determine mode from URL
  const urlSearch = searchParams.get("search") || "";
  const urlCpv = searchParams.get("cpv_code") || "";
  const urlYear = searchParams.get("year") || "";
  const urlMinPrice = searchParams.get("min_price") || "";
  const urlMaxPrice = searchParams.get("max_price") || "";
  const urlEntity = searchParams.get("entity") || "";
  const urlSort = searchParams.get("sort_by") || "";
  const urlPage = searchParams.get("page") || "";
  const urlCategoryName = searchParams.get("category_name") || "";

  const isResultsMode = !!(urlSearch || urlCpv);

  // Hydration
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Load divisions on mount (always, for browse mode)
  useEffect(() => {
    if (!isHydrated) return;
    loadDivisions();
  }, [isHydrated]);

  // Initialize from URL params
  useEffect(() => {
    if (!isHydrated) return;

    const initialFilters: ProductFilterState = {};
    if (urlCpv) initialFilters.cpvCode = urlCpv;
    if (urlYear) initialFilters.year = parseInt(urlYear);
    if (urlMinPrice) initialFilters.minPrice = parseFloat(urlMinPrice);
    if (urlMaxPrice) initialFilters.maxPrice = parseFloat(urlMaxPrice);
    if (urlEntity) initialFilters.procuringEntity = urlEntity;
    if (urlCategoryName) {
      initialFilters.cpvName = urlCategoryName;
      setCategoryName(urlCategoryName);
    }

    setFilters(initialFilters);
    if (urlSearch) setSearchInput(urlSearch);
    if (urlSort && SORT_LABELS[urlSort as SortOption]) setSortBy(urlSort as SortOption);
    if (urlPage) setPage(parseInt(urlPage) || 1);

    if (isResultsMode) {
      fetchProducts(
        urlSearch || undefined,
        initialFilters,
        urlSort as SortOption || "date_desc",
        parseInt(urlPage) || 1
      );
      // Load popular product names for category browsing
      if (urlCpv && !urlSearch) {
        loadPopularNames(urlCpv);
      }
    }
  }, [isHydrated]); // eslint-disable-line react-hooks/exhaustive-deps

  async function loadDivisions() {
    try {
      setDivisionsLoading(true);
      const res = await api.getCPVDivisionsWithStats();
      setDivisions(res.divisions || []);
    } catch (error) {
      console.error("Failed to load divisions:", error);
    } finally {
      setDivisionsLoading(false);
    }
  }

  async function loadPopularNames(cpvCode?: string) {
    try {
      setPopularNamesLoading(true);
      const res = await api.getTopProductNames(cpvCode, 12);
      setPopularNames(res.names || []);
    } catch {
      setPopularNames([]);
    } finally {
      setPopularNamesLoading(false);
    }
  }

  const syncToURL = useCallback(
    (search: string | undefined, f: ProductFilterState, sort: SortOption, p: number) => {
      const params = new URLSearchParams();
      if (search) params.set("search", search);
      if (f.cpvCode) params.set("cpv_code", f.cpvCode);
      if (f.year) params.set("year", f.year.toString());
      if (f.minPrice) params.set("min_price", f.minPrice.toString());
      if (f.maxPrice) params.set("max_price", f.maxPrice.toString());
      if (f.procuringEntity) params.set("entity", f.procuringEntity);
      if (f.cpvName) params.set("category_name", f.cpvName);
      if (sort !== "date_desc") params.set("sort_by", sort);
      if (p > 1) params.set("page", p.toString());
      const qs = params.toString();
      router.replace(qs ? `/products?${qs}` : "/products", { scroll: false });
    },
    [router]
  );

  const fetchProducts = useCallback(
    async (
      search: string | undefined,
      f: ProductFilterState,
      sort: SortOption,
      p: number
    ) => {
      try {
        setLoading(true);

        const searchParams: Record<string, any> = {
          page: p,
          page_size: pageSize,
          sort_by: sort,
        };
        if (search) searchParams.q = search;
        if (f.cpvCode) searchParams.cpv_code = f.cpvCode;
        if (f.year) searchParams.year = f.year;
        if (f.minPrice) searchParams.min_price = f.minPrice;
        if (f.maxPrice) searchParams.max_price = f.maxPrice;
        if (f.procuringEntity) searchParams.procuring_entity = f.procuringEntity;

        // Fetch results and aggregations in parallel (aggregations only on first page with search)
        const [searchResult, aggResult] = await Promise.all([
          api.searchProducts(searchParams),
          search && p === 1
            ? api.getProductAggregations(search).catch(() => null)
            : Promise.resolve(null),
        ]);

        setProducts(searchResult.items);
        setTotal(searchResult.total);
        setPriceGated(searchResult.price_gated ?? false);
        setPriceViewsRemaining(searchResult.price_views_remaining ?? null);
        setPriceViewsLimit(searchResult.price_views_limit ?? null);
        setPage(p);

        if (aggResult) {
          setAggregations(aggResult.aggregations);
        } else if (p === 1) {
          setAggregations([]);
        }
      } catch (error) {
        console.error("Product search failed:", error);
        toast.error("Пребарувањето не успеа. Обидете се повторно.");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  // Suggestions
  useEffect(() => {
    if (suggestionsTimerRef.current) clearTimeout(suggestionsTimerRef.current);
    if (searchInput.length < 2) {
      setSuggestions([]);
      setShowSuggestions(false);
      return;
    }
    suggestionsTimerRef.current = setTimeout(async () => {
      try {
        const result = await api.getProductSuggestions(searchInput, 8);
        setSuggestions(result.suggestions);
        setShowSuggestions(result.suggestions.length > 0);
      } catch {
        setSuggestions([]);
      }
    }, 300);
    return () => {
      if (suggestionsTimerRef.current) clearTimeout(suggestionsTimerRef.current);
    };
  }, [searchInput]);

  // --- Actions ---

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchInput.trim()) return;
    setShowSuggestions(false);
    const newFilters = { ...filters };
    syncToURL(searchInput, newFilters, sortBy, 1);
    fetchProducts(searchInput, newFilters, sortBy, 1);
  };

  const handleSuggestionClick = (suggestion: string) => {
    setSearchInput(suggestion);
    setShowSuggestions(false);
    syncToURL(suggestion, filters, sortBy, 1);
    fetchProducts(suggestion, filters, sortBy, 1);
  };

  const handleExampleClick = (example: string) => {
    setSearchInput(example);
    syncToURL(example, filters, sortBy, 1);
    fetchProducts(example, filters, sortBy, 1);
  };

  const handleCategorySelect = (cpvCode: string, nameMk: string) => {
    const newFilters: ProductFilterState = { cpvCode, cpvName: nameMk };
    setFilters(newFilters);
    setCategoryName(nameMk);
    setSearchInput("");
    syncToURL(undefined, newFilters, "date_desc", 1);
    fetchProducts(undefined, newFilters, "date_desc", 1);
    loadPopularNames(cpvCode);
  };

  const handleBackToBrowse = () => {
    setProducts([]);
    setAggregations([]);
    setTotal(0);
    setSearchInput("");
    setFilters({});
    setCategoryName("");
    setSortBy("date_desc");
    setPage(1);
    setPopularNames([]);
    router.replace("/products", { scroll: false });
  };

  const handlePopularNameClick = (name: string) => {
    setSearchInput(name);
    syncToURL(name, filters, sortBy, 1);
    fetchProducts(name, filters, sortBy, 1);
  };

  const handleFiltersApply = (newFilters: ProductFilterState) => {
    setFilters(newFilters);
    const search = searchInput.trim() || undefined;
    syncToURL(search, newFilters, sortBy, 1);
    fetchProducts(search, newFilters, sortBy, 1);
  };

  const handleFiltersReset = () => {
    const emptyFilters: ProductFilterState = {};
    setFilters(emptyFilters);
    const search = searchInput.trim() || undefined;
    if (search) {
      syncToURL(search, emptyFilters, sortBy, 1);
      fetchProducts(search, emptyFilters, sortBy, 1);
    } else {
      handleBackToBrowse();
    }
  };

  const handleSortChange = (newSort: SortOption) => {
    setSortBy(newSort);
    const search = searchInput.trim() || undefined;
    syncToURL(search, filters, newSort, 1);
    fetchProducts(search, filters, newSort, 1);
  };

  const handlePageChange = (newPage: number) => {
    const search = searchInput.trim() || undefined;
    syncToURL(search, filters, sortBy, newPage);
    fetchProducts(search, filters, sortBy, newPage);
    window.scrollTo({ top: 0, behavior: "smooth" });
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

  const totalPages = Math.ceil(total / pageSize);

  // Price stats from aggregations
  const priceStats =
    aggregations.length > 0
      ? {
          min: Math.min(
            ...aggregations
              .map((a) => a.min_unit_price || Infinity)
              .filter((p) => p !== Infinity)
          ),
          max: Math.max(...aggregations.map((a) => a.max_unit_price || 0)),
          avg:
            aggregations.reduce((sum, a) => sum + (a.avg_unit_price || 0), 0) /
            aggregations.length,
        }
      : null;

  // Wait for hydration
  if (!isHydrated) {
    return <ProductsLoadingFallback />;
  }

  // Current label for results header
  const resultsLabel = searchInput.trim()
    ? `"${searchInput.trim()}"`
    : categoryName
    ? categoryName
    : "";

  // ========== BROWSE MODE ==========
  if (!isResultsMode) {
    return (
      <div className="p-3 md:p-6 lg:p-8 space-y-6">
        {/* Header */}
        <div className="text-center max-w-2xl mx-auto">
          <h1 className="text-2xl md:text-3xl font-bold flex items-center justify-center gap-2">
            <Package className="h-7 w-7 md:h-8 md:w-8" />
            Каталог на Производи
          </h1>
          <p className="text-sm md:text-base text-muted-foreground mt-2">
            Пребарувајте и споредувајте производи, опрема и услуги низ сите јавни набавки
          </p>
        </div>

        {/* Search Bar - Prominent */}
        <div className="max-w-2xl mx-auto">
          <form onSubmit={handleSearch} className="relative">
            <div className="flex gap-2">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
                <Input
                  placeholder="Пребарувајте производи, опрема, услуги..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
                  className="pl-10 h-12 text-base"
                  autoComplete="off"
                />
                {/* Suggestions dropdown */}
                {showSuggestions && suggestions.length > 0 && (
                  <div className="absolute z-50 w-full mt-1 bg-background border rounded-md shadow-lg max-h-60 overflow-auto">
                    {suggestions.map((suggestion, index) => (
                      <button
                        key={index}
                        type="button"
                        onClick={() => handleSuggestionClick(suggestion)}
                        className={`w-full px-4 py-2.5 text-left hover:bg-accent transition-colors text-sm ${
                          index === selectedSuggestionIndex ? "bg-accent" : ""
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Search className="h-4 w-4 text-muted-foreground shrink-0" />
                          <span>{suggestion}</span>
                        </div>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <Button type="submit" size="lg" disabled={!searchInput.trim()}>
                <Search className="h-4 w-4 sm:mr-2" />
                <span className="hidden sm:inline">Пребарај</span>
              </Button>
            </div>
          </form>

          {/* Example searches */}
          <div className="flex flex-wrap gap-2 mt-3 justify-center">
            {EXAMPLE_SEARCHES.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => handleExampleClick(example)}
                className="text-xs px-3 py-1.5 rounded-full border hover:bg-accent hover:border-primary/30 transition-colors text-muted-foreground hover:text-foreground"
              >
                {example}
              </button>
            ))}
          </div>
        </div>

        {/* Cross-link to e-Pazar for price check */}
        <div className="flex items-center gap-3 p-3 rounded-lg border border-primary/20 bg-primary/5">
          <DollarSign className="h-5 w-5 text-primary flex-shrink-0" />
          <p className="text-sm text-muted-foreground flex-1">
            Сакате да ја проверите <strong>пазарната цена</strong> за одреден производ?
          </p>
          <Link href="/epazar">
            <Button variant="outline" size="sm" className="whitespace-nowrap">
              Провери на е-Пазар
            </Button>
          </Link>
        </div>

        {/* Category Grid */}
        <div>
          <h2 className="text-lg font-semibold mb-3">
            Пребарувајте по категорија
          </h2>
          <CategoryGrid
            divisions={divisions}
            loading={divisionsLoading}
            onSelect={handleCategorySelect}
          />
        </div>
      </div>
    );
  }

  // ========== RESULTS MODE ==========
  return (
    <div className="p-3 md:p-6 lg:p-8 space-y-4 md:space-y-6">
      {/* Results Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBackToBrowse}
            className="shrink-0"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            <span className="hidden sm:inline">Категории</span>
          </Button>
          <div>
            <h1 className="text-lg md:text-xl font-bold flex items-center gap-2">
              <Package className="h-5 w-5" />
              {categoryName || "Резултати"}
            </h1>
          </div>
        </div>

        {/* Compact search in results mode */}
        <form onSubmit={handleSearch} className="flex gap-2 w-full sm:w-auto sm:max-w-md">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={categoryName ? `Пребарај во ${categoryName}...` : "Пребарај..."}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
              className="pl-9 h-9"
              autoComplete="off"
            />
            {showSuggestions && suggestions.length > 0 && (
              <div className="absolute z-50 w-full mt-1 bg-background border rounded-md shadow-lg max-h-48 overflow-auto">
                {suggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => handleSuggestionClick(suggestion)}
                    className={`w-full px-3 py-2 text-left hover:bg-accent transition-colors text-sm ${
                      index === selectedSuggestionIndex ? "bg-accent" : ""
                    }`}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
          </div>
          <Button type="submit" size="sm" disabled={!searchInput.trim()}>
            <Search className="h-4 w-4" />
          </Button>
        </form>
      </div>

      {/* Mobile filter toggle */}
      <div className="lg:hidden">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowMobileFilters(!showMobileFilters)}
          className="w-full"
        >
          <SlidersHorizontal className="h-4 w-4 mr-2" />
          Филтри
          {Object.values(filters).filter((v) => v !== undefined).length > 0 && (
            <Badge variant="default" className="ml-2 h-5 px-1.5 text-xs">
              {Object.values(filters).filter((v) => v !== undefined).length}
            </Badge>
          )}
        </Button>
      </div>

      {/* Popular product quick-filters (when browsing a category without search) */}
      {popularNames.length > 0 && !searchInput.trim() && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">Популарни производи во категоријата:</p>
          <div className="flex flex-wrap gap-1.5">
            {popularNames.map((item) => (
              <button
                key={item.name}
                type="button"
                onClick={() => handlePopularNameClick(item.name)}
                className="inline-flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-full border hover:bg-accent hover:border-primary/30 transition-colors text-muted-foreground hover:text-foreground"
              >
                <span className="max-w-[200px] truncate">{item.name}</span>
                <Badge variant="secondary" className="h-4 px-1 text-[10px] shrink-0">
                  {item.count}
                </Badge>
              </button>
            ))}
          </div>
        </div>
      )}
      {popularNamesLoading && !searchInput.trim() && (
        <div className="flex flex-wrap gap-1.5">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-7 w-28 rounded-full" />
          ))}
        </div>
      )}

      {/* Grid: Sidebar + Main */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 md:gap-6">
        {/* Sidebar - Filters */}
        <div
          className={`lg:col-span-1 space-y-4 ${
            showMobileFilters ? "block" : "hidden lg:block"
          }`}
        >
          <ProductFilters
            filters={filters}
            onApply={handleFiltersApply}
            onReset={handleFiltersReset}
          />
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3 space-y-4">
          {/* Price quota indicator */}
          {!loading && priceViewsLimit !== null && priceViewsLimit !== undefined && (
            priceGated ? (
              <div className="flex items-center gap-3 p-3 rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800">
                <Lock className="h-4 w-4 text-amber-600 shrink-0" />
                <p className="text-sm text-amber-800 dark:text-amber-300 flex-1">
                  Ги искористивте <strong>{priceViewsLimit}/{priceViewsLimit}</strong> ценовни прегледи денес.
                  {" "}
                  <Link href="/billing/plans" className="underline font-medium hover:text-amber-900 dark:hover:text-amber-200">
                    Надградете за повеќе
                  </Link>
                </p>
              </div>
            ) : priceViewsRemaining !== null && (
              <div className="flex items-center gap-3 p-2.5 rounded-lg border bg-muted/30">
                <DollarSign className="h-4 w-4 text-muted-foreground shrink-0" />
                <p className="text-xs text-muted-foreground">
                  Преостануваат <strong className="text-foreground">{priceViewsRemaining}</strong> од {priceViewsLimit} ценовни прегледи денес
                </p>
                <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden max-w-[120px] ml-auto">
                  <div
                    className={`h-full rounded-full transition-all ${
                      priceViewsRemaining <= Math.ceil(priceViewsLimit * 0.2) ? "bg-amber-500" : "bg-green-500"
                    }`}
                    style={{ width: `${Math.round((priceViewsRemaining / priceViewsLimit) * 100)}%` }}
                  />
                </div>
              </div>
            )
          )}

          {/* Price Statistics or Upgrade Prompt */}
          {!loading && aggregations.length > 0 && (
            priceGated ? (
              <UpgradePrompt
                feature="price_intelligence"
                currentTier="free"
                tierRequired="starter"
                message="Надградете за да видите цени, ценовна статистика и споредба на цени по производи."
                variant="inline"
              />
            ) : priceStats ? (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Card>
                  <CardContent className="p-3 md:p-4">
                    <div className="text-base md:text-lg font-bold text-green-600 dark:text-green-400">
                      {formatPrice(priceStats.min)}
                    </div>
                    <p className="text-xs text-muted-foreground">Најниска цена</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3 md:p-4">
                    <div className="text-base md:text-lg font-bold">
                      {formatPrice(priceStats.avg)}
                    </div>
                    <p className="text-xs text-muted-foreground">Просечна цена</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3 md:p-4">
                    <div className="text-base md:text-lg font-bold text-red-600 dark:text-red-400">
                      {formatPrice(priceStats.max)}
                    </div>
                    <p className="text-xs text-muted-foreground">Највисока цена</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3 md:p-4">
                    <div className="text-base md:text-lg font-bold">
                      {aggregations.length}
                    </div>
                    <p className="text-xs text-muted-foreground">Варијанти</p>
                  </CardContent>
                </Card>
              </div>
            ) : null
          )}

          {/* Aggregations Table (collapsible, only for paid users) */}
          {aggregations.length > 0 && !loading && !priceGated && (
            <details className="group">
              <summary className="cursor-pointer list-none">
                <Card className="hover:border-primary/30 transition-colors">
                  <CardContent className="p-3 md:p-4 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <TrendingUp className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">
                        Анализа на цени по производ
                      </span>
                      <Badge variant="secondary" className="text-xs">
                        {aggregations.length}
                      </Badge>
                    </div>
                    <ChevronRight className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-90" />
                  </CardContent>
                </Card>
              </summary>
              <Card className="mt-2">
                <CardContent className="p-0">
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/30">
                          <th className="text-left p-3">Производ</th>
                          <th className="text-right p-3">Просечна</th>
                          <th className="text-right p-3 hidden sm:table-cell">Мин</th>
                          <th className="text-right p-3 hidden sm:table-cell">Макс</th>
                          <th className="text-right p-3">Тендери</th>
                        </tr>
                      </thead>
                      <tbody>
                        {aggregations.slice(0, 10).map((agg, i) => (
                          <tr
                            key={i}
                            className="border-b last:border-0 hover:bg-muted/50"
                          >
                            <td className="p-3 font-medium max-w-[200px] truncate">
                              {agg.product_name}
                            </td>
                            <td className="text-right p-3">
                              {formatPrice(agg.avg_unit_price)}
                            </td>
                            <td className="text-right p-3 text-green-600 dark:text-green-400 hidden sm:table-cell">
                              {formatPrice(agg.min_unit_price)}
                            </td>
                            <td className="text-right p-3 text-red-600 dark:text-red-400 hidden sm:table-cell">
                              {formatPrice(agg.max_unit_price)}
                            </td>
                            <td className="text-right p-3">{agg.tender_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </details>
          )}

          {/* Results header bar */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <p className="text-sm text-muted-foreground">
              {loading ? (
                "Пребарување..."
              ) : (
                <>
                  <span className="font-medium text-foreground">
                    {total.toLocaleString()}
                  </span>{" "}
                  резултати{resultsLabel ? ` за ${resultsLabel}` : ""}
                </>
              )}
            </p>
            <div className="flex items-center gap-2">
              <Select
                value={sortBy}
                onValueChange={(v) => handleSortChange(v as SortOption)}
              >
                <SelectTrigger className="w-[180px] h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(SORT_LABELS)
                    .filter(([value]) => !priceGated || !value.startsWith("price_"))
                    .map(([value, label]) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {products.length > 0 && (
                <ExportButton
                  data={products}
                  filename={`производи-${(searchInput || categoryName || "сите").replace(/\s+/g, "-")}-${new Date().toISOString().split("T")[0]}`}
                  columns={[
                    { key: "name", label: "Име на Производ" },
                    { key: "quantity", label: "Количина" },
                    { key: "unit", label: "Единица" },
                    { key: "unit_price", label: "Единечна Цена (МКД)" },
                    { key: "total_price", label: "Вкупна Цена (МКД)" },
                    { key: "cpv_code", label: "CPV Код" },
                    { key: "tender_title", label: "Тендер" },
                    { key: "procuring_entity", label: "Орган" },
                    { key: "opening_date", label: "Датум" },
                  ]}
                />
              )}
            </div>
          </div>

          {/* Product Cards */}
          {loading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <Card key={i}>
                  <CardContent className="p-4 sm:p-6">
                    <Skeleton className="h-5 w-3/4 mb-3" />
                    <div className="flex gap-2 mb-3">
                      <Skeleton className="h-6 w-20 rounded-full" />
                      <Skeleton className="h-6 w-24 rounded-full" />
                      <Skeleton className="h-6 w-20 rounded-full" />
                    </div>
                    <Skeleton className="h-4 w-1/2 mb-2" />
                    <Skeleton className="h-4 w-1/3" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : products.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Package className="h-12 w-12 text-muted-foreground mb-4 opacity-50" />
              <h3 className="font-medium mb-1">Нема пронајдени производи</h3>
              <p className="text-sm text-muted-foreground max-w-md">
                {searchInput
                  ? `Не се пронајдени резултати за "${searchInput}". Обидете се со различни термини или проширете ги филтрите.`
                  : "Нема извлечени производи за оваа категорија. Податоците се извлекуваат од тендерската документација."}
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={handleBackToBrowse}
              >
                <ArrowLeft className="h-4 w-4 mr-1" />
                Назад кон категории
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {products.map((product) => (
                <ProductCard key={product.id} product={product} priceGated={priceGated} />
              ))}
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && !loading && (
            <div className="flex items-center justify-center gap-4 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                <span className="hidden sm:inline">Претходна</span>
              </Button>
              <span className="text-sm text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(page + 1)}
                disabled={page === totalPages}
              >
                <span className="hidden sm:inline">Следна</span>
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
