'use client';

import { useState, useEffect } from 'react';
import { Search, Building2, TrendingUp, Award, Package, ChevronLeft, ChevronRight, ChevronDown, ChevronUp, Sparkles, Tag, Lock } from 'lucide-react';
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
  const [priceCheckOpen, setPriceCheckOpen] = useState(false);
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
  const [priceAuthRequired, setPriceAuthRequired] = useState(false);

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
    setPriceAuthRequired(false);

    try {
      const searchResult = await api.searchEPazarProducts(priceSearch);

      if (searchResult.products.length === 0) {
        setProductSuggestions([]);
        setPriceIntelligence(null);
      } else if (searchResult.products.length === 1) {
        setProductSuggestions([]);
        const data = await api.getEPazarPriceIntelligence({ search: searchResult.products[0].name });
        setPriceIntelligence(data);
      } else {
        setProductSuggestions(searchResult.products);
        setShowSuggestions(true);
      }
    } catch (err: any) {
      console.error('Failed to search prices:', err);
      const isAuthError = err?.message?.includes('401') || err?.message?.includes('Unauthorized') || err?.message?.includes('403') || err?.status === 401 || err?.status === 403;
      if (isAuthError) {
        setPriceAuthRequired(true);
      }
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
    } catch (err: any) {
      console.error('Failed to get prices:', err);
      const isAuthError = err?.message?.includes('401') || err?.message?.includes('Unauthorized') || err?.message?.includes('403') || err?.status === 401 || err?.status === 403;
      if (isAuthError) {
        setPriceAuthRequired(true);
      }
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
      <div className="space-y-4 p-6">
        {/* Header + Search */}
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">е-Пазар</h1>
            <p className="text-sm text-muted-foreground">Мали набавки од e-pazar.gov.mk</p>
          </div>
          <form onSubmit={handleSearch} className="flex gap-2 w-full md:w-auto md:min-w-[320px]">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Пребарај тендери..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="pl-10"
              />
            </div>
            <Button type="submit">Барај</Button>
          </form>
        </div>

        {/* Compact Stats Strip */}
        <div className="flex flex-wrap gap-4 p-3 rounded-lg border bg-card">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-blue-500" />
            <div>
              <p className="text-xs text-muted-foreground">Тендери</p>
              <p className="text-sm font-bold">{stats?.total_tenders?.toLocaleString() || '-'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-green-500" />
            <div>
              <p className="text-xs text-muted-foreground">Ставки</p>
              <p className="text-sm font-bold">{stats?.total_items?.toLocaleString() || '-'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Building2 className="h-4 w-4 text-purple-500" />
            <div>
              <p className="text-xs text-muted-foreground">Добавувачи</p>
              <p className="text-sm font-bold">{stats?.total_suppliers?.toLocaleString() || '-'}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Award className="h-4 w-4 text-yellow-500" />
            <div>
              <p className="text-xs text-muted-foreground">Вкупна вредност</p>
              <p className="text-sm font-bold">{stats?.total_value_mkd ? formatCurrency(stats.total_value_mkd) : '-'}</p>
            </div>
          </div>
        </div>

        {/* Tender List */}
        <div>
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-lg font-semibold">
              {search ? `Резултати за "${search}"` : 'Последни тендери'}
              <span className="text-sm font-normal text-muted-foreground ml-2">({tendersTotal})</span>
            </h2>
          </div>

          {tendersLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <CardHeader>
                    <div className="h-5 bg-muted rounded w-1/4 mb-2" />
                    <div className="h-6 bg-muted rounded w-3/4" />
                  </CardHeader>
                  <CardContent>
                    <div className="h-4 bg-muted rounded w-full" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : tenders.length === 0 ? (
            <Card>
              <CardContent className="pt-6 text-center text-muted-foreground">
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
                          <span className="text-xs text-muted-foreground">
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
                              <span className="text-muted-foreground">Вредност:</span>
                              <span className="font-semibold">{formatCurrency(tender.estimated_value_mkd)}</span>
                            </div>
                          ) : tender.awarded_value_mkd ? (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Доделено:</span>
                              <span className="font-semibold text-green-600">{formatCurrency(tender.awarded_value_mkd)}</span>
                            </div>
                          ) : (
                            <div className="text-xs text-muted-foreground italic">Вредноста не е наведена</div>
                          )}
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
                  <span className="text-sm text-muted-foreground">
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

        {/* Price Check Tool - Collapsible, below tenders */}
        <Card>
          <button
            onClick={() => setPriceCheckOpen(!priceCheckOpen)}
            className="w-full flex items-center justify-between p-4 hover:bg-muted/50 transition-colors rounded-lg"
          >
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              <span className="font-semibold">Провери пазарна цена</span>
              <span className="text-xs text-muted-foreground">— мин/просек/макс за производ</span>
            </div>
            {priceCheckOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
          {priceCheckOpen && (
            <CardContent className="pt-0 space-y-4">
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

              {/* Product Suggestions */}
              {priceSearched && !priceLoading && showSuggestions && productSuggestions.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm text-muted-foreground">Пронајдени {productSuggestions.length} производи — изберете:</p>
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

              {/* Auth required — upgrade prompt */}
              {priceAuthRequired && !priceLoading && (
                <div className="text-center py-6 space-y-3">
                  <Lock className="h-8 w-8 text-muted-foreground mx-auto" />
                  <p className="font-medium">Ценовната анализа е достапна за претплатници</p>
                  <p className="text-sm text-muted-foreground">Надградете го вашиот план за пристап до пазарни цени, препорачани понуди и победнички брендови.</p>
                  <Link href="/billing/plans">
                    <Button size="sm" className="mt-2">Прегледај планови</Button>
                  </Link>
                </div>
              )}

              {/* No results */}
              {priceSearched && !priceLoading && !showSuggestions && productSuggestions.length === 0 && !priceIntelligence && !priceAuthRequired && (
                <div className="text-center py-4 space-y-2">
                  <p className="text-muted-foreground">Нема резултати за &ldquo;{priceSearch}&rdquo; во е-Пазар</p>
                  <p className="text-xs text-muted-foreground">Обидете се со пократок збор (пр. &ldquo;хартија&rdquo; наместо &ldquo;хартија А4&rdquo;)</p>
                  <div className="flex justify-center gap-2 mt-3">
                    <Link href={`/products?search=${encodeURIComponent(priceSearch)}`}>
                      <Button variant="outline" size="sm">
                        <Package className="h-3 w-3 mr-1" />
                        Барај во Каталог
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

                  {priceIntelligence.product_name && (
                    <p className="text-sm text-muted-foreground">
                      Производ: <span className="font-medium text-foreground">{priceIntelligence.product_name}</span>
                    </p>
                  )}

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
          )}
        </Card>
      </div>
    </DashboardLayout>
  );
}
