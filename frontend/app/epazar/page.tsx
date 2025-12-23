'use client';

import { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  Calendar,
  DollarSign,
  Building2,
  ChevronLeft,
  ChevronRight,
  Package,
  Users,
  FileText,
  TrendingUp,
  ShoppingCart,
  ExternalLink,
  ArrowUpDown,
  Lightbulb,
  BarChart3
} from 'lucide-react';
import { api, EPazarTender, EPazarStats, EPazarItemWithTender, EPazarItemAggregation } from '@/lib/api';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import Link from 'next/link';
import { formatCurrency, formatDate } from '@/lib/utils';
import { SupplierRankings } from '@/components/epazar/SupplierRankings';

function formatQuantity(qty: number | undefined | null, unit: string | undefined | null): string {
  if (!qty) return '-';
  return `${qty.toLocaleString('mk-MK')} ${unit || ''}`.trim();
}

function getStatusBadgeVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status?.toLowerCase()) {
    case 'active':
      return 'default';
    case 'awarded':
    case 'signed':
      return 'secondary';
    case 'cancelled':
      return 'destructive';
    default:
      return 'outline';
  }
}

function getStatusLabel(status: string): string {
  switch (status?.toLowerCase()) {
    case 'active':
      return 'Активен';
    case 'awarded':
      return 'Доделен';
    case 'signed':
      return 'Потпишан';
    case 'cancelled':
      return 'Откажан';
    default:
      return status || 'Непознат';
  }
}

function EPazarCard({ tender }: { tender: EPazarTender }) {
  return (
    <Link href={`/epazar/${encodeURIComponent(tender.tender_id)}`}>
      <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
        <CardHeader className="pb-2">
          <div className="flex justify-between items-start gap-2">
            <Badge variant={getStatusBadgeVariant(tender.status)}>
              {getStatusLabel(tender.status)}
            </Badge>
            {tender.cpv_code && (
              <span className="text-xs text-gray-500">{tender.cpv_code}</span>
            )}
          </div>
          <CardTitle className="text-lg line-clamp-2">{tender.title}</CardTitle>
          {tender.contracting_authority && (
            <CardDescription className="flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              {tender.contracting_authority}
            </CardDescription>
          )}
        </CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Проценета вредност:</span>
              <span className="font-medium">{formatCurrency(tender.estimated_value_mkd)}</span>
            </div>
            {tender.closing_date && (
              <div className="flex justify-between">
                <span className="text-gray-500">Краен рок:</span>
                <span className="font-medium">{formatDate(tender.closing_date)}</span>
              </div>
            )}
            {tender.procedure_type && (
              <div className="flex justify-between">
                <span className="text-gray-500">Постапка:</span>
                <span className="font-medium text-xs">{tender.procedure_type}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function StatsCard({
  title,
  value,
  icon: Icon,
  description,
  onClick,
  active
}: {
  title: string;
  value: string | number;
  icon: any;
  description?: string;
  onClick?: () => void;
  active?: boolean;
}) {
  return (
    <Card
      className={`${onClick ? 'cursor-pointer hover:border-primary/50 transition-colors' : ''} ${active ? 'border-primary bg-primary/5' : ''}`}
      onClick={onClick}
    >
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500">{title}</p>
            <p className="text-2xl font-bold">{value}</p>
            {description && <p className="text-xs text-gray-400 mt-1">{description}</p>}
          </div>
          <Icon className={`h-8 w-8 ${active ? 'text-primary' : 'text-blue-500'} opacity-80`} />
        </div>
      </CardContent>
    </Card>
  );
}

type TabType = 'tenders' | 'products' | 'intelligence';

export default function EPazarPage() {
  const [isHydrated, setIsHydrated] = useState(false);
  const [activeTab, setActiveTab] = useState<TabType>('tenders');

  // Stats
  const [stats, setStats] = useState<EPazarStats | null>(null);

  // Tenders state
  const [tenders, setTenders] = useState<EPazarTender[]>([]);
  const [tendersLoading, setTendersLoading] = useState(true);
  const [tendersError, setTendersError] = useState<string | null>(null);
  const [tendersSearch, setTendersSearch] = useState('');
  const [tendersStatus, setTendersStatus] = useState<string>('');
  const [tendersPage, setTendersPage] = useState(1);
  const [tendersTotalPages, setTendersTotalPages] = useState(1);
  const [tendersTotal, setTendersTotal] = useState(0);

  // Products state
  const [products, setProducts] = useState<EPazarItemWithTender[]>([]);
  const [productsLoading, setProductsLoading] = useState(false);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [productsSearch, setProductsSearch] = useState('');
  const [productsPage, setProductsPage] = useState(1);
  const [productsTotalPages, setProductsTotalPages] = useState(1);
  const [productsTotal, setProductsTotal] = useState(0);
  const [productsSortBy, setProductsSortBy] = useState('item_name');
  const [productsSortOrder, setProductsSortOrder] = useState('asc');
  const [productsAggregations, setProductsAggregations] = useState<EPazarItemAggregation[]>([]);
  const [hasSearchedProducts, setHasSearchedProducts] = useState(false);

  // Intelligence tab state
  const [supplierRankings, setSupplierRankings] = useState<any[]>([]);
  const [supplierRankingsLoading, setSupplierRankingsLoading] = useState(false);
  const [buyerStats, setBuyerStats] = useState<any[]>([]);
  const [buyerStatsLoading, setBuyerStatsLoading] = useState(false);

  const pageSize = 12;

  // Hydration guard
  useEffect(() => {
    setIsHydrated(true);
  }, []);

  // Status filter tabs for tenders
  const statusTabs = [
    { key: '', label: 'Сите' },
    { key: 'active', label: 'Активни' },
    { key: 'signed', label: 'Потпишани' },
    { key: 'awarded', label: 'Доделени' },
    { key: 'cancelled', label: 'Откажани' },
  ];

  useEffect(() => {
    if (!isHydrated) return;
    loadStats();
  }, [isHydrated]);

  useEffect(() => {
    if (!isHydrated) return;
    if (activeTab === 'tenders') {
      loadTenders();
    }
  }, [isHydrated, tendersPage, tendersStatus, tendersSearch, activeTab]);

  useEffect(() => {
    if (!isHydrated) return;
    if (activeTab === 'products' && hasSearchedProducts) {
      loadProducts();
    }
  }, [isHydrated, productsPage, productsSortBy, productsSortOrder, activeTab]);

  useEffect(() => {
    if (!isHydrated) return;
    if (activeTab === 'intelligence') {
      loadIntelligenceData();
    }
  }, [isHydrated, activeTab]);

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
    setTendersError(null);

    try {
      const params: Record<string, any> = {
        page: tendersPage,
        page_size: pageSize,
      };

      if (tendersStatus) params.status = tendersStatus;
      if (tendersSearch) params.search = tendersSearch;

      const data = await api.getEPazarTenders(params);
      setTenders(data.items);
      setTendersTotal(data.total);
      setTendersTotalPages(Math.ceil(data.total / pageSize));
    } catch (err) {
      console.error('Failed to load tenders:', err);
      setTendersError('Не успеавме да ги вчитаме тендерите');
    } finally {
      setTendersLoading(false);
    }
  }

  async function loadProducts() {
    setProductsLoading(true);
    setProductsError(null);

    try {
      const params: Record<string, any> = {
        page: productsPage,
        page_size: pageSize,
        sort_by: productsSortBy,
        sort_order: productsSortOrder,
      };

      if (productsSearch) params.search = productsSearch;

      const [searchResult, aggResult] = await Promise.all([
        api.searchEPazarItems(params),
        productsPage === 1 && productsSearch ? api.getEPazarItemsAggregations(productsSearch) : Promise.resolve(null),
      ]);

      setProducts(searchResult.items);
      setProductsTotal(searchResult.total);
      setProductsTotalPages(Math.ceil(searchResult.total / pageSize));

      if (aggResult) {
        setProductsAggregations(aggResult.aggregations);
      }
    } catch (err) {
      console.error('Failed to load products:', err);
      setProductsError('Не успеавме да ги вчитаме производите');
    } finally {
      setProductsLoading(false);
    }
  }

  function handleTendersSearch(e: React.FormEvent) {
    e.preventDefault();
    setTendersPage(1);
    loadTenders();
  }

  function handleProductsSearch(e: React.FormEvent) {
    e.preventDefault();
    setProductsPage(1);
    setHasSearchedProducts(true);
    loadProducts();
  }

  async function loadIntelligenceData() {
    setSupplierRankingsLoading(true);
    setBuyerStatsLoading(true);

    try {
      const [rankingsData, buyersData] = await Promise.all([
        api.getEPazarSupplierRankings({ page: 1, page_size: 20 }),
        api.getEPazarBuyerStats({ page: 1, page_size: 20 })
      ]);

      setSupplierRankings(rankingsData.suppliers);
      setBuyerStats(buyersData.buyers);
    } catch (err) {
      console.error('Failed to load intelligence data:', err);
    } finally {
      setSupplierRankingsLoading(false);
      setBuyerStatsLoading(false);
    }
  }

  // Wait for hydration
  if (!isHydrated) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-full p-8">
          <p className="text-muted-foreground">Се вчитува...</p>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6 p-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <ShoppingCart className="h-6 w-6" />
              е-Пазар Електронски Пазар
            </h1>
            <p className="text-gray-500">Прегледајте тендери и производи од e-pazar.gov.mk</p>
          </div>
        </div>

        {/* Stats - Clickable to switch tabs */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatsCard
            title="Вкупно тендери"
            value={stats ? stats.total_tenders.toLocaleString() : '-'}
            icon={FileText}
            onClick={() => setActiveTab('tenders')}
            active={activeTab === 'tenders'}
          />
          <StatsCard
            title="Вкупно ставки"
            value={stats ? stats.total_items.toLocaleString() : '-'}
            icon={Package}
            description="Кликни за пребарување"
            onClick={() => setActiveTab('products')}
            active={activeTab === 'products'}
          />
          <StatsCard
            title="Вкупно добавувачи"
            value={stats ? stats.total_suppliers.toLocaleString() : '-'}
            icon={Users}
          />
          <StatsCard
            title="Вкупна вредност"
            value={stats ? formatCurrency(stats.total_value_mkd) : '-'}
            icon={TrendingUp}
          />
        </div>

        {/* Tab Buttons */}
        <div className="flex gap-2 border-b pb-2">
          <Button
            variant={activeTab === 'tenders' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('tenders')}
            className="gap-2"
          >
            <FileText className="h-4 w-4" />
            Тендери
          </Button>
          <Button
            variant={activeTab === 'products' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('products')}
            className="gap-2"
          >
            <Package className="h-4 w-4" />
            Производи / Ставки
          </Button>
          <Button
            variant={activeTab === 'intelligence' ? 'default' : 'ghost'}
            onClick={() => setActiveTab('intelligence')}
            className="gap-2"
          >
            <Lightbulb className="h-4 w-4" />
            Market Intelligence
          </Button>
        </div>

        {/* TENDERS TAB */}
        {activeTab === 'tenders' && (
          <>
            {/* Search and Filters */}
            <Card>
              <CardContent className="pt-6">
                <form onSubmit={handleTendersSearch} className="flex gap-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      type="text"
                      placeholder="Пребарај тендери..."
                      value={tendersSearch}
                      onChange={(e) => setTendersSearch(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                  <Button type="submit">
                    <Filter className="h-4 w-4 mr-2" />
                    Барај
                  </Button>
                </form>

                {/* Status Tabs */}
                <div className="flex gap-2 mt-4 flex-wrap">
                  {statusTabs.map((tab) => (
                    <Button
                      key={tab.key}
                      variant={tendersStatus === tab.key ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => {
                        setTendersStatus(tab.key);
                        setTendersPage(1);
                      }}
                    >
                      {tab.label}
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Results */}
            {tendersLoading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Array.from({ length: 6 }).map((_, i) => (
                  <Card key={`skeleton-${i}`} className="animate-pulse">
                    <CardHeader>
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/4" />
                      <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-3/4 mt-2" />
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mt-2" />
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded" />
                        <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded" />
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : tendersError ? (
              <Card>
                <CardContent className="pt-6 text-center text-red-500">
                  {tendersError}
                </CardContent>
              </Card>
            ) : tenders.length === 0 ? (
              <Card>
                <CardContent className="pt-6 text-center text-gray-500">
                  Не се пронајдени тендери. Обидете се со други критериуми за пребарување.
                </CardContent>
              </Card>
            ) : (
              <>
                <div className="text-sm text-gray-500 mb-2">
                  Прикажани {(tendersPage - 1) * pageSize + 1}-{Math.min(tendersPage * pageSize, tendersTotal)} од {tendersTotal} тендери
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {tenders.map((tender) => (
                    <div key={tender.tender_id}>
                      <EPazarCard tender={tender} />
                    </div>
                  ))}
                </div>

                {/* Pagination */}
                {tendersTotalPages > 1 && (
                  <div className="flex justify-center items-center gap-4 mt-6">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setTendersPage(p => Math.max(1, p - 1))}
                      disabled={tendersPage === 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Претходна
                    </Button>
                    <span className="text-sm text-gray-500">
                      Страна {tendersPage} од {tendersTotalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setTendersPage(p => Math.min(tendersTotalPages, p + 1))}
                      disabled={tendersPage === tendersTotalPages}
                    >
                      Следна
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* PRODUCTS TAB */}
        {activeTab === 'products' && (
          <>
            {/* Search and Filters */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Пребарување производи</CardTitle>
                <CardDescription>
                  Пребарувајте и споредувајте цени на производи од сите е-Пазар тендери
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <form onSubmit={handleProductsSearch} className="flex gap-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                    <Input
                      type="text"
                      placeholder="Пребарај производи (пр. хартија, тонер, канцелариски материјал...)"
                      value={productsSearch}
                      onChange={(e) => setProductsSearch(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                  <Button type="submit" disabled={productsLoading}>
                    <Search className="h-4 w-4 mr-2" />
                    Барај
                  </Button>
                </form>

                {/* Sort options */}
                {hasSearchedProducts && (
                  <div className="flex gap-4 items-center">
                    <span className="text-sm text-muted-foreground">Сортирај по:</span>
                    <Select
                      value={productsSortBy}
                      onValueChange={(value) => {
                        setProductsSortBy(value);
                        setProductsPage(1);
                      }}
                    >
                      <SelectTrigger className="w-48">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="item_name">Име</SelectItem>
                        <SelectItem value="estimated_unit_price_mkd">Единечна цена</SelectItem>
                        <SelectItem value="quantity">Количина</SelectItem>
                        <SelectItem value="estimated_total_price_mkd">Вкупна цена</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setProductsSortOrder(prev => prev === 'asc' ? 'desc' : 'asc');
                        setProductsPage(1);
                      }}
                    >
                      <ArrowUpDown className="h-4 w-4 mr-1" />
                      {productsSortOrder === 'asc' ? 'Растечки' : 'Опаѓачки'}
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Products Results */}
            {!hasSearchedProducts ? (
              <Card>
                <CardContent className="pt-6 text-center">
                  <Package className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                  <p className="text-muted-foreground">
                    Внесете термин за пребарување за да ги видите производите и нивните цени
                  </p>
                  <p className="text-xs text-muted-foreground mt-2">
                    Примери: хартија А4, тонер, канцелариски материјал, гориво
                  </p>
                </CardContent>
              </Card>
            ) : productsLoading ? (
              <div className="space-y-4">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Card key={`skeleton-${i}`} className="animate-pulse">
                    <CardContent className="pt-6">
                      <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/2 mb-2" />
                      <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4" />
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : productsError ? (
              <Card>
                <CardContent className="pt-6 text-center text-red-500">
                  {productsError}
                </CardContent>
              </Card>
            ) : products.length === 0 ? (
              <Card>
                <CardContent className="pt-6 text-center text-gray-500">
                  <Package className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <p>Не се пронајдени производи за "{productsSearch}"</p>
                  <p className="text-xs mt-2">Обидете се со други термини за пребарување</p>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Price Aggregations */}
                {productsAggregations.length > 0 && (
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-lg flex items-center gap-2">
                        <TrendingUp className="h-5 w-5" />
                        Анализа на цени
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b">
                              <th className="text-left p-2">Производ</th>
                              <th className="text-right p-2">Мин. цена</th>
                              <th className="text-right p-2">Просек</th>
                              <th className="text-right p-2">Макс. цена</th>
                              <th className="text-right p-2">Вкупна кол.</th>
                              <th className="text-right p-2">Тендери</th>
                            </tr>
                          </thead>
                          <tbody>
                            {productsAggregations.slice(0, 10).map((agg, i) => (
                              <tr key={i} className="border-b last:border-0 hover:bg-muted/50">
                                <td className="p-2 font-medium">
                                  {agg.item_name}
                                  {agg.unit && <span className="text-xs text-muted-foreground ml-1">({agg.unit})</span>}
                                </td>
                                <td className="text-right p-2 text-green-600">{formatCurrency(agg.min_unit_price)}</td>
                                <td className="text-right p-2">{formatCurrency(agg.avg_unit_price)}</td>
                                <td className="text-right p-2 text-red-600">{formatCurrency(agg.max_unit_price)}</td>
                                <td className="text-right p-2">{agg.total_quantity?.toLocaleString() || '-'}</td>
                                <td className="text-right p-2">{agg.tender_count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Results count */}
                <div className="text-sm text-gray-500">
                  Прикажани {(productsPage - 1) * pageSize + 1}-{Math.min(productsPage * pageSize, productsTotal)} од {productsTotal} производи
                </div>

                {/* Products List */}
                <div className="space-y-4">
                  {products.map((item, idx) => (
                    <Card key={`${item.item_id}-${idx}`} className="hover:border-primary/50 transition-colors">
                      <CardContent className="pt-6">
                        <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
                          {/* Product Info */}
                          <div className="flex-1 space-y-2">
                            <h3 className="font-semibold text-lg">{item.item_name}</h3>
                            {item.item_description && (
                              <p className="text-sm text-muted-foreground line-clamp-2">{item.item_description}</p>
                            )}

                            <div className="flex flex-wrap gap-2 text-sm">
                              {item.quantity && (
                                <Badge variant="secondary">
                                  Кол: {formatQuantity(item.quantity, item.unit)}
                                </Badge>
                              )}
                              {item.estimated_unit_price_mkd && (
                                <Badge variant="outline">
                                  Ед. цена: {formatCurrency(item.estimated_unit_price_mkd)}
                                </Badge>
                              )}
                              {item.estimated_total_price_mkd && (
                                <Badge className="bg-green-100 text-green-800 hover:bg-green-200">
                                  Вкупно: {formatCurrency(item.estimated_total_price_mkd)}
                                </Badge>
                              )}
                              {item.cpv_code && (
                                <Badge variant="outline" className="font-mono">
                                  CPV: {item.cpv_code}
                                </Badge>
                              )}
                            </div>

                            {/* Tender Context */}
                            {item.tender_title && (
                              <div className="pt-2 border-t mt-2">
                                <div className="flex items-start gap-2 text-sm text-muted-foreground">
                                  <Building2 className="h-4 w-4 mt-0.5 shrink-0" />
                                  <div>
                                    <p className="font-medium text-foreground line-clamp-1">
                                      {item.tender_title}
                                    </p>
                                    {item.contracting_authority && (
                                      <p>{item.contracting_authority}</p>
                                    )}
                                  </div>
                                </div>

                                <div className="flex flex-wrap gap-4 mt-2 text-xs text-muted-foreground">
                                  {item.tender_closing_date && (
                                    <span className="flex items-center gap-1">
                                      <Calendar className="h-3 w-3" />
                                      Рок: {formatDate(item.tender_closing_date)}
                                    </span>
                                  )}
                                  {item.tender_status && (
                                    <Badge variant="outline" className="text-xs">
                                      {getStatusLabel(item.tender_status)}
                                    </Badge>
                                  )}
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Actions */}
                          <div className="flex md:flex-col gap-2">
                            <Link href={`/epazar/${encodeURIComponent(item.tender_id)}`}>
                              <Button variant="outline" size="sm">
                                <ExternalLink className="h-4 w-4 mr-1" />
                                Тендер
                              </Button>
                            </Link>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                {/* Pagination */}
                {productsTotalPages > 1 && (
                  <div className="flex justify-center items-center gap-4 mt-6">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setProductsPage(p => Math.max(1, p - 1))}
                      disabled={productsPage === 1 || productsLoading}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Претходна
                    </Button>
                    <span className="text-sm text-gray-500">
                      Страна {productsPage} од {productsTotalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setProductsPage(p => Math.min(productsTotalPages, p + 1))}
                      disabled={productsPage === productsTotalPages || productsLoading}
                    >
                      Следна
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* MARKET INTELLIGENCE TAB */}
        {activeTab === 'intelligence' && (
          <>
            <Card className="border-primary/30 bg-gradient-to-br from-purple-50/50 to-blue-50/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-purple-600" />
                  Пазарна Интелигенција
                </CardTitle>
                <CardDescription>
                  Анализа на добавувачи, купувачи и пазарни трендови на е-Пазар
                </CardDescription>
              </CardHeader>
            </Card>

            {/* Supplier Rankings */}
            <div>
              {supplierRankingsLoading ? (
                <Card>
                  <CardContent className="pt-6">
                    <div className="animate-pulse space-y-4">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <div key={i} className="h-12 bg-gray-200 rounded" />
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <SupplierRankings
                  suppliers={supplierRankings}
                  title="Топ Добавувачи"
                  description="Рангирање според стапка на успех и вредност на договори"
                  showCity={true}
                />
              )}
            </div>

            {/* Buyer Stats */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5 text-blue-600" />
                  Статистика на Купувачи
                </CardTitle>
                <CardDescription>
                  Активност на институции што објавуваат тендери
                </CardDescription>
              </CardHeader>
              <CardContent>
                {buyerStatsLoading ? (
                  <div className="animate-pulse space-y-4">
                    {Array.from({ length: 5 }).map((_, i) => (
                      <div key={i} className="h-12 bg-gray-200 rounded" />
                    ))}
                  </div>
                ) : buyerStats.length === 0 ? (
                  <p className="text-center text-gray-500 py-8">Нема податоци за купувачи</p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left p-3">Институција</th>
                          <th className="text-right p-3">Тендери</th>
                          <th className="text-right p-3">Вкупна Вредност</th>
                          <th className="text-right p-3">Просечна Вредност</th>
                          <th className="text-right p-3">Активни</th>
                        </tr>
                      </thead>
                      <tbody>
                        {buyerStats.map((buyer: any, idx: number) => (
                          <tr key={buyer.buyer_id || idx} className="border-b hover:bg-muted/50">
                            <td className="p-3 font-medium">{buyer.buyer_name}</td>
                            <td className="text-right p-3">{buyer.total_tenders?.toLocaleString()}</td>
                            <td className="text-right p-3 text-green-600 font-semibold">
                              {formatCurrency(buyer.total_value_mkd)}
                            </td>
                            <td className="text-right p-3">{formatCurrency(buyer.avg_tender_value_mkd)}</td>
                            <td className="text-right p-3">
                              <Badge variant="outline">{buyer.active_tenders || 0}</Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
