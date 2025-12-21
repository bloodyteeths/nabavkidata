'use client';

import { useState, useEffect } from 'react';
import { api, Supplier } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Building2, Trophy, FileText, TrendingUp, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import Link from 'next/link';
import { formatCurrency } from '@/lib/utils';

export default function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sortBy, setSortBy] = useState('total_wins');
  const [sortOrder, setSortOrder] = useState('desc');
  const [stats, setStats] = useState<{
    total_suppliers: number;
    suppliers_with_wins: number;
    total_bids: number;
    average_win_rate: number | null;
  } | null>(null);

  useEffect(() => {
    fetchSuppliers();
  }, [page, search, sortBy, sortOrder]);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'https://api.nabavkidata.com'}/api/suppliers/stats`);
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (err) {
      console.error('Failed to fetch supplier stats:', err);
    }
  };

  const fetchSuppliers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getSuppliers({
        page,
        page_size: pageSize,
        search: search || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setSuppliers(response.items);
      setTotal(response.total);
    } catch (err: any) {
      setError(err.message || 'Failed to load suppliers');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    setSearch(searchInput);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const formatPercent = (value?: number | null) => {
    if (value === null || value === undefined) return '-';
    // win_rate is already stored as percentage (0-100), not decimal
    return `${value.toFixed(1)}%`;
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">Добавувачи</h1>
          <p className="text-muted-foreground mt-1">
            Преглед на сите добавувачи и нивната историја на учество
          </p>
        </div>
        <Badge variant="outline" className="text-lg px-4 py-2">
          {total} добавувачи
        </Badge>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Building2 className="h-8 w-8 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Вкупно добавувачи</p>
                <p className="text-2xl font-bold">{stats?.total_suppliers ?? total}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Trophy className="h-8 w-8 text-yellow-500" />
              <div>
                <p className="text-sm text-muted-foreground">Со победи</p>
                <p className="text-2xl font-bold">
                  {stats?.suppliers_with_wins ?? '-'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Вкупно понуди</p>
                <p className="text-2xl font-bold">
                  {stats?.total_bids?.toLocaleString() ?? '-'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <TrendingUp className="h-8 w-8 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Просек победи</p>
                <p className="text-2xl font-bold">
                  {stats?.average_win_rate != null ? `${stats.average_win_rate}%` : '-'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card className="mb-6">
        <CardContent className="pt-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 flex gap-2">
              <Input
                placeholder="Пребарувај по име на компанија..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyPress={handleKeyPress}
                className="flex-1"
              />
              <Button onClick={handleSearch}>
                <Search className="h-4 w-4 mr-2" />
                Пребарај
              </Button>
            </div>
            <div className="flex gap-2">
              <Select value={sortBy} onValueChange={setSortBy}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Подреди по" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="total_wins">Број на победи</SelectItem>
                  <SelectItem value="total_bids">Број на понуди</SelectItem>
                  <SelectItem value="win_rate">Стапка на победи</SelectItem>
                  <SelectItem value="company_name">Име</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sortOrder} onValueChange={setSortOrder}>
                <SelectTrigger className="w-[120px]">
                  <SelectValue placeholder="Редослед" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="desc">Опаѓачки</SelectItem>
                  <SelectItem value="asc">Растечки</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Error State */}
      {error && (
        <Card className="mb-6 border-destructive">
          <CardContent className="pt-6">
            <p className="text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* Suppliers Table */}
      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Компанија</TableHead>
                <TableHead>Град</TableHead>
                <TableHead className="text-center">Понуди</TableHead>
                <TableHead className="text-center">Победи</TableHead>
                <TableHead className="text-center">Стапка</TableHead>
                <TableHead className="text-right">Вкупна вредност</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8">
                    <div className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                      Се вчитува...
                    </div>
                  </TableCell>
                </TableRow>
              ) : suppliers.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    Нема пронајдени добавувачи
                  </TableCell>
                </TableRow>
              ) : (
                suppliers.map((supplier) => (
                  <TableRow key={supplier.supplier_id} className="hover:bg-muted/50">
                    <TableCell>
                      <Link
                        href={`/suppliers/${supplier.supplier_id}`}
                        className="font-medium hover:text-primary"
                      >
                        {supplier.company_name}
                      </Link>
                      {supplier.tax_id && (
                        <p className="text-xs text-muted-foreground mt-1">
                          ЕДБ: {supplier.tax_id}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>{supplier.city || '-'}</TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline">{supplier.total_bids}</Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant={supplier.total_wins > 0 ? 'default' : 'secondary'}>
                        {supplier.total_wins}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      {formatPercent(supplier.win_rate)}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(supplier.total_value_won_mkd)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-muted-foreground">
            Страница {page} од {totalPages} ({total} резултати)
          </p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="h-4 w-4" />
              Претходна
            </Button>
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
        </div>
      )}
    </div>
  );
}
