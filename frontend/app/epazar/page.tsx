'use client';

import { useState, useEffect } from 'react';
import { Search, Calendar, Building2, TrendingUp, Clock, Award } from 'lucide-react';
import { api, EPazarTender, EPazarStats, EPazarItemAggregation } from '@/lib/api';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';
import { formatCurrency, formatDate } from '@/lib/utils';

function getDaysRemaining(closingDate: string): string {
  const now = new Date();
  const closing = new Date(closingDate);
  const diffTime = closing.getTime() - now.getTime();
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return 'Затворен';
  if (diffDays === 0) return 'Затвора денес';
  if (diffDays === 1) return 'уште 1 ден';
  return `уште ${diffDays} дена`;
}

function StatsCard({ title, value, icon: Icon }: { title: string; value: string | number; icon: any }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500">{title}</p>
            <p className="text-2xl font-bold mt-1">{value}</p>
          </div>
          <Icon className="h-8 w-8 text-blue-500 opacity-80" />
        </div>
      </CardContent>
    </Card>
  );
}

export default function EPazarPage() {
  const [isHydrated, setIsHydrated] = useState(false);
  const [stats, setStats] = useState<EPazarStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Active tenders
  const [activeTenders, setActiveTenders] = useState<EPazarTender[]>([]);
  const [activeLoading, setActiveLoading] = useState(true);

  // Awarded tenders
  const [awardedTenders, setAwardedTenders] = useState<EPazarTender[]>([]);
  const [awardedLoading, setAwardedLoading] = useState(true);

  // Search state
  const [searchTerm, setSearchTerm] = useState('');

  // Price check state
  const [priceSearchTerm, setPriceSearchTerm] = useState('');
  const [priceResults, setPriceResults] = useState<EPazarItemAggregation[]>([]);
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceSearched, setPriceSearched] = useState(false);

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    if (!isHydrated) return;
    loadStats();
    loadActiveTenders();
    loadAwardedTenders();
  }, [isHydrated]);

  async function loadStats() {
    setStatsLoading(true);
    try {
      const data = await api.getEPazarStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    } finally {
      setStatsLoading(false);
    }
  }

  async function loadActiveTenders() {
    setActiveLoading(true);
    try {
      const data = await api.getEPazarTenders({
        status: 'active',
        sort_by: 'closing_date',
        sort_order: 'asc',
        page_size: 6,
      });
      setActiveTenders(data.items);
    } catch (err) {
      console.error('Failed to load active tenders:', err);
    } finally {
      setActiveLoading(false);
    }
  }

  async function loadAwardedTenders() {
    setAwardedLoading(true);
    try {
      const data = await api.getEPazarTenders({
        status: 'awarded,signed',
        sort_by: 'award_date',
        sort_order: 'desc',
        page_size: 4,
      });
      setAwardedTenders(data.items);
    } catch (err) {
      console.error('Failed to load awarded tenders:', err);
    } finally {
      setAwardedLoading(false);
    }
  }

  async function handlePriceSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!priceSearchTerm.trim()) return;

    setPriceLoading(true);
    setPriceSearched(true);
    try {
      const data = await api.getEPazarItemsAggregations(priceSearchTerm);
      setPriceResults(data.aggregations || []);
    } catch (err) {
      console.error('Failed to search prices:', err);
      setPriceResults([]);
    } finally {
      setPriceLoading(false);
    }
  }

  function handleMainSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchTerm.trim()) return;
    // Navigate to tenders page with search term
    window.location.href = `/epazar?search=${encodeURIComponent(searchTerm)}`;
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

  const activeCount = stats?.status_breakdown?.active?.count || 0;
  const totalValue = stats?.total_value_mkd || 0;

  return (
    <DashboardLayout>
      <div className="space-y-8 p-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-2">е-Пазар - Електронски Пазар</h1>
          <p className="text-gray-500 text-lg">Најдете можности и проверете пазарни цени</p>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <StatsCard
            title="Активни тендери"
            value={statsLoading ? '-' : activeCount.toLocaleString()}
            icon={TrendingUp}
          />
          <StatsCard
            title="Вкупна доделена вредност"
            value={statsLoading ? '-' : formatCurrency(totalValue)}
            icon={Award}
          />
        </div>

        {/* Search Bar */}
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleMainSearch} className="flex gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Пребарај тендери..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Button type="submit">Барај</Button>
            </form>
          </CardContent>
        </Card>

        {/* Active Opportunities Section */}
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold">АКТИВНИ МОЖНОСТИ</h2>
            <Link href="/epazar?status=active">
              <Button variant="outline" size="sm">Види сите</Button>
            </Link>
          </div>

          {activeLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <CardHeader>
                    <div className="h-6 bg-gray-200 rounded w-3/4" />
                    <div className="h-4 bg-gray-200 rounded w-1/2 mt-2" />
                  </CardHeader>
                  <CardContent>
                    <div className="h-4 bg-gray-200 rounded w-full mt-2" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : activeTenders.length === 0 ? (
            <Card>
              <CardContent className="pt-6 text-center text-gray-500">
                Нема активни можности во моментов
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {activeTenders.map((tender) => (
                <Link key={tender.tender_id} href={`/epazar/${encodeURIComponent(tender.tender_id)}`}>
                  <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-lg line-clamp-2">{tender.title}</CardTitle>
                      {tender.contracting_authority && (
                        <CardDescription className="flex items-center gap-1 mt-2">
                          <Building2 className="h-3 w-3" />
                          {tender.contracting_authority}
                        </CardDescription>
                      )}
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2 text-sm">
                        {tender.closing_date && (
                          <div className="flex items-center gap-2">
                            <Clock className="h-4 w-4 text-orange-500" />
                            <Badge variant="outline" className="text-orange-600">
                              {getDaysRemaining(tender.closing_date)}
                            </Badge>
                          </div>
                        )}
                        {tender.estimated_value_mkd && (
                          <div className="flex justify-between items-center">
                            <span className="text-gray-500">Проценета вредност:</span>
                            <span className="font-semibold">{formatCurrency(tender.estimated_value_mkd)}</span>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Price Check Section */}
        <div>
          <Card className="border-2 border-blue-100 bg-blue-50/30">
            <CardHeader>
              <CardTitle className="text-2xl flex items-center gap-2">
                <TrendingUp className="h-6 w-6 text-blue-600" />
                ПРОВЕРИ ЦЕНА
              </CardTitle>
              <CardDescription className="text-base">
                Внесете производ за да видите пазарни цени
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <form onSubmit={handlePriceSearch} className="flex gap-4">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    type="text"
                    placeholder="Пр. хартија А4, тонер, канцелариски материјал..."
                    value={priceSearchTerm}
                    onChange={(e) => setPriceSearchTerm(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <Button type="submit" disabled={priceLoading}>
                  {priceLoading ? 'Се пребарува...' : 'Пребарај'}
                </Button>
              </form>

              {priceSearched && !priceLoading && (
                <div>
                  {priceResults.length === 0 ? (
                    <p className="text-center text-gray-500 py-4">
                      Не се пронајдени резултати за "{priceSearchTerm}"
                    </p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b bg-white">
                            <th className="text-left p-3 font-semibold">Производ</th>
                            <th className="text-right p-3 font-semibold">Мин. цена</th>
                            <th className="text-right p-3 font-semibold">Просечна</th>
                            <th className="text-right p-3 font-semibold">Макс. цена</th>
                            <th className="text-right p-3 font-semibold">Тендери</th>
                          </tr>
                        </thead>
                        <tbody>
                          {priceResults.slice(0, 10).map((item, idx) => (
                            <tr key={idx} className="border-b hover:bg-white/50">
                              <td className="p-3 font-medium">
                                {item.item_name}
                                {item.unit && <span className="text-xs text-gray-500 ml-1">({item.unit})</span>}
                              </td>
                              <td className="text-right p-3 text-green-600 font-semibold">
                                {formatCurrency(item.min_unit_price || 0)}
                              </td>
                              <td className="text-right p-3">{formatCurrency(item.avg_unit_price || 0)}</td>
                              <td className="text-right p-3 text-red-600 font-semibold">
                                {formatCurrency(item.max_unit_price || 0)}
                              </td>
                              <td className="text-right p-3">
                                <Badge variant="outline">{item.tender_count}</Badge>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Recently Awarded Section */}
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold">НЕОДАМНА ДОДЕЛЕНИ</h2>
            <Link href="/epazar?status=awarded">
              <Button variant="outline" size="sm">Види сите</Button>
            </Link>
          </div>

          {awardedLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <CardHeader>
                    <div className="h-6 bg-gray-200 rounded w-3/4" />
                  </CardHeader>
                  <CardContent>
                    <div className="h-4 bg-gray-200 rounded w-full mt-2" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : awardedTenders.length === 0 ? (
            <Card>
              <CardContent className="pt-6 text-center text-gray-500">
                Нема доделени тендери
              </CardContent>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {awardedTenders.map((tender) => {
                // Find winner from offers if available
                const winner = tender.awarded_value_mkd ? 'Доделен' : 'Доделен';

                return (
                  <Link key={tender.tender_id} href={`/epazar/${encodeURIComponent(tender.tender_id)}`}>
                    <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
                      <CardHeader className="pb-3">
                        <div className="flex items-start justify-between gap-2 mb-2">
                          <Badge variant="secondary">Доделен</Badge>
                          {tender.award_date && (
                            <span className="text-xs text-gray-500 flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {formatDate(tender.award_date)}
                            </span>
                          )}
                        </div>
                        <CardTitle className="text-lg line-clamp-2">{tender.title}</CardTitle>
                        {tender.contracting_authority && (
                          <CardDescription className="flex items-center gap-1 mt-2">
                            <Building2 className="h-3 w-3" />
                            {tender.contracting_authority}
                          </CardDescription>
                        )}
                      </CardHeader>
                      <CardContent>
                        <div className="space-y-2 text-sm">
                          {tender.awarded_value_mkd && (
                            <div className="flex justify-between items-center">
                              <span className="text-gray-500">Доделена вредност:</span>
                              <span className="font-bold text-green-600">
                                {formatCurrency(tender.awarded_value_mkd)}
                              </span>
                            </div>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
