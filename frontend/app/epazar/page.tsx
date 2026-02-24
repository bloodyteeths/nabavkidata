'use client';

import { useState, useEffect } from 'react';
import { Search, Building2, TrendingUp, Award, Package, ChevronLeft, ChevronRight, Sparkles, Tag } from 'lucide-react';
import { api, EPazarTender, EPazarStats } from '@/lib/api';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';
import { formatCurrency, formatDate } from '@/lib/utils';
import { AlertBellButton } from '@/components/alerts/AlertBellButton';

function getStatusLabel(status: string): string {
  switch (status?.toLowerCase()) {
    case 'active': return 'Активен';
    case 'awarded': return 'Доделен';
    case 'signed': return 'Потпишан';
    case 'cancelled': return 'Откажан';
    case 'completed': return 'Завршен';
    default: return status || 'Непознат';
  }
}

function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status?.toLowerCase()) {
    case 'active': return 'default';
    case 'awarded':
    case 'signed': return 'secondary';
    case 'cancelled': return 'destructive';
    default: return 'outline';
  }
}

export default function EPazarPage() {
  const [isHydrated, setIsHydrated] = useState(false);
  const [stats, setStats] = useState<EPazarStats | null>(null);

  // Tenders state
  const [tenders, setTenders] = useState<EPazarTender[]>([]);
  const [tendersLoading, setTendersLoading] = useState(true);
  const [tendersTotal, setTendersTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const pageSize = 12;

  // Price check state
  const [priceSearch, setPriceSearch] = useState('');
  const [productSuggestions, setProductSuggestions] = useState<Array<{
    name: string;
    count: number;
    min_price?: number;
    max_price?: number;
    avg_price?: number;
  }>>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [priceIntelligence, setPriceIntelligence] = useState<{
    product_name: string;
    recommended_bid_min_mkd?: number;
    recommended_bid_max_mkd?: number;
    market_min_mkd?: number;
    market_max_mkd?: number;
    market_avg_mkd?: number;
    sample_size: number;
    actual_prices?: {
      has_data: boolean;
      sample_size: number;
      min?: number;
      max?: number;
      avg?: number;
      p25?: number;
      p75?: number;
    };
    winning_brands?: Array<{
      brand: string;
      wins: number;
      avg_price?: number;
    }>;
    ai_recommendation?: string;
  } | null>(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceSearched, setPriceSearched] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    loadStats();
  }, [isHydrated]);

  useEffect(() => {
    if (!isHydrated) return;
    loadTenders();
  }, [isHydrated, page, search]);

  async function loadStats() {
    try {
      const data = await api.getEPazarStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }

  async function loadTenders() {
    setTendersLoading(true);
    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
        sort_by: 'publication_date',
        sort_order: 'desc',
      };
      if (search) params.search = search;

      const data = await api.getEPazarTenders(params);
      setTenders(data.items);
      setTendersTotal(data.total);
    } catch (err) {
      console.error('Failed to load tenders:', err);
    } finally {
      setTendersLoading(false);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setSearch(searchInput);
    setPage(1);
  }

  async function handlePriceSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!priceSearch.trim()) return;

    setPriceLoading(true);
    setPriceSearched(true);
    setPriceIntelligence(null);
    setShowSuggestions(false);

    try {
      // First search for matching products
      const searchResult = await api.searchEPazarProducts(priceSearch);

      if (searchResult.products.length === 0) {
        // No products found
        setProductSuggestions([]);
        setPriceIntelligence(null);
      } else if (searchResult.products.length === 1) {
        // Only one product - show prices directly
        setProductSuggestions([]);
        const data = await api.getEPazarPriceIntelligence({ search: searchResult.products[0].name });
        setPriceIntelligence(data);
      } else {
        // Multiple products - show suggestions
        setProductSuggestions(searchResult.products);
        setShowSuggestions(true);
      }
    } catch (err) {
      console.error('Failed to search prices:', err);
      setPriceIntelligence(null);
      setProductSuggestions([]);
    } finally {
      setPriceLoading(false);
    }
  }

  async function selectProduct(productName: string) {
    setPriceLoading(true);
    setShowSuggestions(false);
    setPriceSearch(productName);

    try {
      const data = await api.getEPazarPriceIntelligence({ search: productName });
      setPriceIntelligence(data);
    } catch (err) {
      console.error('Failed to get prices:', err);
      setPriceIntelligence(null);
    } finally {
      setPriceLoading(false);
    }
  }

  if (!isHydrated) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-full p-8">
          <p className="text-muted-foreground">Се вчитува...</p>
        </div>
      </DashboardLayout>
    );
  }

  const totalPages = Math.ceil(tendersTotal / pageSize);

  return (
    <DashboardLayout>
      <div className="space-y-6 p-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold">е-Пазар - Електронски Пазар</h1>
          <p className="text-gray-500">Тендери и цени од e-pazar.gov.mk</p>
        </div>

        {/* Explainer - what is e-Pazar */}
        <Card className="border-blue-500/20 bg-blue-500/5">
          <CardContent className="p-4 flex items-start gap-3">
            <div className="h-8 w-8 rounded-full bg-blue-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
              <Sparkles className="h-4 w-4 text-blue-400" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-foreground">Што е е-Пазар?</p>
              <p className="text-xs text-muted-foreground mt-1">
                е-Пазар е систем за <strong>мали набавки</strong> (обично под 500,000 ден) каде институциите директно бараат понуди за производи и услуги.
                За разлика од формалните тендери на <Link href="/tenders" className="text-primary hover:underline">Тендери</Link>, тука процесот е побрз и поедноставен -
                идеално за фирми кои продаваат стандардни производи.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Тендери</p>
                  <p className="text-2xl font-bold">{stats?.total_tenders?.toLocaleString() || '-'}</p>
                </div>
                <TrendingUp className="h-8 w-8 text-blue-500 opacity-80" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Ставки</p>
                  <p className="text-2xl font-bold">{stats?.total_items?.toLocaleString() || '-'}</p>
                </div>
                <Package className="h-8 w-8 text-green-500 opacity-80" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Добавувачи</p>
                  <p className="text-2xl font-bold">{stats?.total_suppliers?.toLocaleString() || '-'}</p>
                </div>
                <Building2 className="h-8 w-8 text-purple-500 opacity-80" />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-500">Вкупна вредност</p>
                  <p className="text-2xl font-bold">{formatCurrency(stats?.total_value_mkd || 0)}</p>
                </div>
                <Award className="h-8 w-8 text-yellow-500 opacity-80" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Price Check Tool */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              Провери пазарна цена
            </CardTitle>
            <CardDescription>
              Внесете производ за да видите мин/просек/макс цени (работи кирилица и латиница)
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <form onSubmit={handlePriceSearch} className="flex gap-2">
              <Input
                type="text"
                placeholder="пр. хартија А4, тонер, гориво, канцелариски..."
                value={priceSearch}
                onChange={(e) => setPriceSearch(e.target.value)}
                className="flex-1"
              />
              <Button type="submit" disabled={priceLoading}>
                {priceLoading ? 'Барам...' : 'Провери'}
              </Button>
            </form>

            {/* Product Suggestions - like Google search */}
            {priceSearched && !priceLoading && showSuggestions && productSuggestions.length > 0 && (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">Пронајдени {productSuggestions.length} производи - изберете:</p>
                <div className="grid gap-2">
                  {productSuggestions.map((product, idx) => (
                    <button
                      key={idx}
                      onClick={() => selectProduct(product.name)}
                      className="flex items-center justify-between p-3 rounded-lg border bg-muted/30 hover:bg-muted/50 transition-colors text-left"
                    >
                      <div>
                        <span className="font-medium">{product.name}</span>
                        <span className="text-xs text-muted-foreground ml-2">({product.count} понуди)</span>
                      </div>
                      {product.avg_price && (
                        <span className="text-sm font-semibold text-primary">
                          ~{formatCurrency(product.avg_price)}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* No results - with fallback links */}
            {priceSearched && !priceLoading && !showSuggestions && productSuggestions.length === 0 && !priceIntelligence && (
              <div className="text-center py-4 space-y-2">
                <p className="text-muted-foreground">Нема резултати за &ldquo;{priceSearch}&rdquo; во е-Пазар</p>
                <p className="text-xs text-muted-foreground">Обидете се со пократок збор (пр. &ldquo;хартија&rdquo; наместо &ldquo;хартија А4&rdquo;)</p>
                <div className="flex justify-center gap-2 mt-3">
                  <Link href={`/products?search=${encodeURIComponent(priceSearch)}`}>
                    <Button variant="outline" size="sm">
                      <Package className="h-3 w-3 mr-1" />
                      Барај во Каталог на Производи
                    </Button>
                  </Link>
                  <Link href={`/tenders?search=${encodeURIComponent(priceSearch)}`}>
                    <Button variant="outline" size="sm">
                      <Search className="h-3 w-3 mr-1" />
                      Барај во Тендери
                    </Button>
                  </Link>
                </div>
              </div>
            )}

            {/* Price Intelligence Results */}
            {priceSearched && !priceLoading && priceIntelligence && priceIntelligence.sample_size > 0 && (
              <div className="space-y-4">
                {/* Main Price Stats - using P25/P75 for typical range */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="bg-muted/50 rounded-lg p-4 text-center border">
                    <p className="text-xs text-muted-foreground uppercase font-medium">Ниска цена</p>
                    <p className="text-xl font-bold text-foreground">
                      {formatCurrency(priceIntelligence.actual_prices?.p25 || priceIntelligence.recommended_bid_min_mkd || 0)}
                    </p>
                  </div>
                  <div className="bg-primary/10 rounded-lg p-4 text-center border border-primary/20">
                    <p className="text-xs text-primary uppercase font-medium">Просек</p>
                    <p className="text-xl font-bold text-primary">
                      {formatCurrency(priceIntelligence.actual_prices?.avg || priceIntelligence.market_avg_mkd || 0)}
                    </p>
                  </div>
                  <div className="bg-muted/50 rounded-lg p-4 text-center border">
                    <p className="text-xs text-muted-foreground uppercase font-medium">Висока цена</p>
                    <p className="text-xl font-bold text-foreground">
                      {formatCurrency(priceIntelligence.actual_prices?.p75 || priceIntelligence.recommended_bid_max_mkd || 0)}
                    </p>
                  </div>
                </div>

                {/* Product name that was matched */}
                {priceIntelligence.product_name && (
                  <p className="text-sm text-muted-foreground">
                    Производ: <span className="font-medium text-foreground">{priceIntelligence.product_name}</span>
                  </p>
                )}

                  {/* Winning Brands from Evaluation Data */}
                  {priceIntelligence.winning_brands && priceIntelligence.winning_brands.length > 0 && (
                    <div className="bg-muted/30 rounded-lg p-3 border">
                      <div className="flex items-center gap-2 mb-2">
                        <Sparkles className="h-4 w-4 text-primary" />
                        <span className="text-sm font-medium">Победнички брендови</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {priceIntelligence.winning_brands.slice(0, 5).map((brand, idx) => (
                          <Badge key={idx} variant="secondary">
                            <Tag className="h-3 w-3 mr-1" />
                            {brand.brand}
                            <span className="text-xs text-muted-foreground ml-1">({brand.wins}x)</span>
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* AI Recommendation */}
                  {priceIntelligence.ai_recommendation && (
                    <div className="text-sm text-muted-foreground border-t pt-3">
                      {priceIntelligence.ai_recommendation}
                    </div>
                  )}

                <p className="text-xs text-muted-foreground text-right">
                  Базирано на {priceIntelligence.actual_prices?.sample_size || priceIntelligence.sample_size} тендери
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Tender Search */}
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleSearch} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Пребарај тендери (кирилица или латиница)..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Button type="submit">Барај</Button>
            </form>
          </CardContent>
        </Card>

        {/* Tenders List */}
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">
              {search ? `Резултати за "${search}"` : 'Последни тендери'}
              <span className="text-sm font-normal text-gray-500 ml-2">({tendersTotal} вкупно)</span>
            </h2>
          </div>

          {tendersLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <CardHeader>
                    <div className="h-5 bg-gray-200 rounded w-1/4 mb-2" />
                    <div className="h-6 bg-gray-200 rounded w-3/4" />
                  </CardHeader>
                  <CardContent>
                    <div className="h-4 bg-gray-200 rounded w-full" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : tenders.length === 0 ? (
            <Card>
              <CardContent className="pt-6 text-center text-gray-500">
                {search ? `Нема резултати за "${search}"` : 'Нема тендери'}
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {tenders.map((tender) => (
                  <Link key={tender.tender_id} href={`/epazar/${encodeURIComponent(tender.tender_id)}`}>
                    <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                      <CardHeader className="pb-2">
                        <div className="flex justify-between items-start gap-2">
                          <Badge variant={getStatusVariant(tender.status)}>
                            {getStatusLabel(tender.status)}
                          </Badge>
                          <span className="text-xs text-gray-500">
                            {tender.publication_date ? formatDate(tender.publication_date) : ''}
                          </span>
                        </div>
                        <CardTitle className="text-base line-clamp-2 mt-2">{tender.title}</CardTitle>
                        {tender.contracting_authority && (
                          <CardDescription className="flex items-center gap-1 text-xs">
                            <Building2 className="h-3 w-3" />
                            <span className="line-clamp-1">{tender.contracting_authority}</span>
                          </CardDescription>
                        )}
                      </CardHeader>
                      <CardContent>
                        <div className="text-sm">
                          {tender.estimated_value_mkd ? (
                            <div className="flex justify-between">
                              <span className="text-gray-500">Вредност:</span>
                              <span className="font-semibold">{formatCurrency(tender.estimated_value_mkd)}</span>
                            </div>
                          ) : tender.awarded_value_mkd ? (
                            <div className="flex justify-between">
                              <span className="text-gray-500">Доделено:</span>
                              <span className="font-semibold text-green-600">{formatCurrency(tender.awarded_value_mkd)}</span>
                            </div>
                          ) : null}
                        </div>
                        <div className="flex justify-between items-center mt-3">
                          <span className="text-xs text-muted-foreground">{tender.cpv_code || ''}</span>
                          <AlertBellButton
                            tenderId={tender.tender_id}
                            cpvCode={tender.cpv_code}
                            procuringEntity={tender.contracting_authority}
                            title={tender.title}
                            size="sm"
                          />
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex justify-center items-center gap-4 mt-6">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                    Претходна
                  </Button>
                  <span className="text-sm text-gray-500">
                    Страна {page} од {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                  >
                    Следна
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
