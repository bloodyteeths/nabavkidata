'use client';

import { useState, useEffect, useMemo } from 'react';
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
  ShoppingCart
} from 'lucide-react';
import { api, EPazarTender, EPazarStats } from '@/lib/api';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import Link from 'next/link';

function formatCurrency(value: number | undefined | null, currency: string = 'MKD'): string {
  if (!value) return 'N/A';
  return new Intl.NumberFormat('mk-MK', {
    style: 'currency',
    currency: currency === 'EUR' ? 'EUR' : 'MKD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(dateStr: string | undefined | null): string {
  if (!dateStr) return 'N/A';
  return new Date(dateStr).toLocaleDateString('mk-MK');
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
              <span className="text-gray-500">Estimated Value:</span>
              <span className="font-medium">{formatCurrency(tender.estimated_value_mkd)}</span>
            </div>
            {tender.closing_date && (
              <div className="flex justify-between">
                <span className="text-gray-500">Closing Date:</span>
                <span className="font-medium">{formatDate(tender.closing_date)}</span>
              </div>
            )}
            {tender.procedure_type && (
              <div className="flex justify-between">
                <span className="text-gray-500">Procedure:</span>
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
  description
}: {
  title: string;
  value: string | number;
  icon: any;
  description?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500">{title}</p>
            <p className="text-2xl font-bold">{value}</p>
            {description && <p className="text-xs text-gray-400 mt-1">{description}</p>}
          </div>
          <Icon className="h-8 w-8 text-blue-500 opacity-80" />
        </div>
      </CardContent>
    </Card>
  );
}

export default function EPazarPage() {
  const [tenders, setTenders] = useState<EPazarTender[]>([]);
  const [stats, setStats] = useState<EPazarStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<string>('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const pageSize = 12;

  // Status filter tabs
  const statusTabs = [
    { key: '', label: 'Сите' },
    { key: 'active', label: 'Активни' },
    { key: 'signed', label: 'Потпишани' },
    { key: 'awarded', label: 'Доделени' },
    { key: 'cancelled', label: 'Откажани' },
  ];

  useEffect(() => {
    loadStats();
  }, []);

  useEffect(() => {
    loadTenders();
  }, [page, status, search]);

  async function loadStats() {
    try {
      const data = await api.getEPazarStats();
      setStats(data);
    } catch (err) {
      console.error('Failed to load stats:', err);
    }
  }

  async function loadTenders() {
    setLoading(true);
    setError(null);

    try {
      const params: Record<string, any> = {
        page,
        page_size: pageSize,
      };

      if (status) params.status = status;
      if (search) params.search = search;

      const data = await api.getEPazarTenders(params);
      setTenders(data.items);
      setTotal(data.total);
      setTotalPages(Math.ceil(data.total / pageSize));
    } catch (err) {
      console.error('Failed to load tenders:', err);
      setError('Failed to load tenders');
    } finally {
      setLoading(false);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    loadTenders();
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
            <p className="text-gray-500">Прегледајте тендери од e-pazar.gov.mk</p>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatsCard
            title="Вкупно тендери"
            value={stats ? stats.total_tenders.toLocaleString() : '-'}
            icon={FileText}
          />
          <StatsCard
            title="Вкупно ставки"
            value={stats ? stats.total_items.toLocaleString() : '-'}
            icon={Package}
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

        {/* Search and Filters */}
        <Card>
          <CardContent className="pt-6">
            <form onSubmit={handleSearch} className="flex gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Пребарај тендери..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-10"
                />
              </div>
              <Button type="submit">
                <Filter className="h-4 w-4 mr-2" />
                Барај
              </Button>
            </form>

            {/* Status Tabs */}
            <div className="flex gap-2 mt-4">
              {statusTabs.map((tab) => (
                <Button
                  key={tab.key}
                  variant={status === tab.key ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setStatus(tab.key);
                    setPage(1);
                  }}
                >
                  {tab.label}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Results */}
        {loading ? (
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
        ) : error ? (
          <Card>
            <CardContent className="pt-6 text-center text-red-500">
              {error}
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
              Прикажани {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, total)} од {total} тендери
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {tenders.map((tender) => (
                <div key={tender.tender_id}>
                  <EPazarCard tender={tender} />
                </div>
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
    </DashboardLayout>
  );
}
