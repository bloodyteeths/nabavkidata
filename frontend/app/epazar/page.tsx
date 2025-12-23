'use client';

import { useState, useEffect } from 'react';
import { Search, Building2, TrendingUp, Award, Package, ChevronLeft, ChevronRight } from 'lucide-react';
import { api, EPazarTender, EPazarStats, EPazarItemAggregation } from '@/lib/api';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';
import { formatCurrency, formatDate } from '@/lib/utils';

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
  const [priceResults, setPriceResults] = useState<EPazarItemAggregation[]>([]);
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
    try {
      const data = await api.getEPazarItemsAggregations(priceSearch);
      setPriceResults(data.aggregations || []);
    } catch (err) {
      console.error('Failed to search prices:', err);
      setPriceResults([]);
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
        <Card className="border-blue-200 bg-blue-50/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-blue-600" />
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

            {priceSearched && !priceLoading && (
              priceResults.length === 0 ? (
                <p className="text-gray-500 text-center py-2">Нема резултати за "{priceSearch}"</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">Производ</th>
                        <th className="text-right p-2">Мин</th>
                        <th className="text-right p-2">Просек</th>
                        <th className="text-right p-2">Макс</th>
                        <th className="text-right p-2">Тендери</th>
                      </tr>
                    </thead>
                    <tbody>
                      {priceResults.slice(0, 8).map((item, idx) => (
                        <tr key={idx} className="border-b">
                          <td className="p-2">
                            {item.item_name}
                            {item.unit && <span className="text-xs text-gray-400 ml-1">({item.unit})</span>}
                          </td>
                          <td className="text-right p-2 text-green-600 font-medium">
                            {formatCurrency(item.min_unit_price || 0)}
                          </td>
                          <td className="text-right p-2">{formatCurrency(item.avg_unit_price || 0)}</td>
                          <td className="text-right p-2 text-red-600 font-medium">
                            {formatCurrency(item.max_unit_price || 0)}
                          </td>
                          <td className="text-right p-2">{item.tender_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}
          </CardContent>
        </Card>

        {/* Tender Search */}
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleSearch} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
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
