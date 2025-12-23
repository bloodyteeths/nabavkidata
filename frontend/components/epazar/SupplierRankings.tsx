'use client';

import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Trophy, TrendingUp, ArrowUpDown, ArrowUp, ArrowDown } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';
import Link from 'next/link';

export interface SupplierRanking {
  supplier_id: string;
  company_name: string;
  tax_id?: string;
  total_wins: number;
  total_offers: number;
  win_rate: number;
  total_contract_value_mkd: number;
  avg_bid_amount_mkd?: number;
  city?: string;
}

interface SupplierRankingsProps {
  suppliers: SupplierRanking[];
  loading?: boolean;
  title?: string;
  description?: string;
  showCity?: boolean;
}

type SortField = 'company_name' | 'win_rate' | 'total_wins' | 'total_contract_value_mkd';
type SortOrder = 'asc' | 'desc';

export function SupplierRankings({
  suppliers,
  loading = false,
  title = "Топ Добавувачи",
  description = "Рангирање на добавувачи според успешност",
  showCity = false
}: SupplierRankingsProps) {
  const [sortField, setSortField] = useState<SortField>('win_rate');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-yellow-500" />
            {title}
          </CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>Добавувач</TableHead>
                  {showCity && <TableHead>Град</TableHead>}
                  <TableHead className="text-right">Победи</TableHead>
                  <TableHead className="text-center">% Победи</TableHead>
                  <TableHead className="text-right">Вкупна Вредност</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: 5 }).map((_, idx) => (
                  <TableRow key={idx}>
                    <TableCell>
                      <div className="animate-pulse h-4 bg-gray-200 rounded w-6" />
                    </TableCell>
                    <TableCell>
                      <div className="animate-pulse space-y-2">
                        <div className="h-4 bg-gray-200 rounded w-32" />
                        <div className="h-3 bg-gray-200 rounded w-20" />
                      </div>
                    </TableCell>
                    {showCity && (
                      <TableCell>
                        <div className="animate-pulse h-4 bg-gray-200 rounded w-16" />
                      </TableCell>
                    )}
                    <TableCell className="text-right">
                      <div className="animate-pulse space-y-1">
                        <div className="h-4 bg-gray-200 rounded w-12 ml-auto" />
                        <div className="h-3 bg-gray-200 rounded w-10 ml-auto" />
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="animate-pulse flex items-center justify-center gap-2">
                        <div className="h-4 bg-gray-200 rounded w-12" />
                        <div className="h-5 bg-gray-200 rounded w-16" />
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="animate-pulse space-y-1">
                        <div className="h-4 bg-gray-200 rounded w-24 ml-auto" />
                        <div className="h-3 bg-gray-200 rounded w-20 ml-auto" />
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    );
  }

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const sortedSuppliers = [...suppliers].sort((a, b) => {
    const aVal = a[sortField] || 0;
    const bVal = b[sortField] || 0;

    if (sortField === 'company_name') {
      return sortOrder === 'asc'
        ? String(aVal).localeCompare(String(bVal), 'mk')
        : String(bVal).localeCompare(String(aVal), 'mk');
    }

    return sortOrder === 'asc' ? Number(aVal) - Number(bVal) : Number(bVal) - Number(aVal);
  });

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) return <ArrowUpDown className="h-4 w-4 text-gray-400" />;
    return sortOrder === 'asc'
      ? <ArrowUp className="h-4 w-4 text-primary" />
      : <ArrowDown className="h-4 w-4 text-primary" />;
  };

  const getWinRateBadge = (winRate: number) => {
    if (winRate >= 50) {
      return <Badge className="bg-green-500">Висока</Badge>;
    } else if (winRate >= 25) {
      return <Badge className="bg-yellow-500">Средна</Badge>;
    } else {
      return <Badge variant="outline">Ниска</Badge>;
    }
  };

  if (suppliers.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Trophy className="h-5 w-5 text-yellow-500" />
            {title}
          </CardTitle>
          {description && <CardDescription>{description}</CardDescription>}
        </CardHeader>
        <CardContent>
          <p className="text-center text-gray-500 py-8">Нема податоци за добавувачи</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Trophy className="h-5 w-5 text-yellow-500" />
          {title}
        </CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">#</TableHead>
                <TableHead>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('company_name')}
                    className="h-auto p-0 hover:bg-transparent"
                  >
                    Добавувач
                    {getSortIcon('company_name')}
                  </Button>
                </TableHead>
                {showCity && <TableHead>Град</TableHead>}
                <TableHead className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('total_wins')}
                    className="h-auto p-0 hover:bg-transparent ml-auto flex items-center gap-1"
                  >
                    Победи
                    {getSortIcon('total_wins')}
                  </Button>
                </TableHead>
                <TableHead className="text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('win_rate')}
                    className="h-auto p-0 hover:bg-transparent"
                  >
                    % Победи
                    {getSortIcon('win_rate')}
                  </Button>
                </TableHead>
                <TableHead className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('total_contract_value_mkd')}
                    className="h-auto p-0 hover:bg-transparent ml-auto flex items-center gap-1"
                  >
                    Вкупна Вредност
                    {getSortIcon('total_contract_value_mkd')}
                  </Button>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedSuppliers.map((supplier, idx) => (
                <TableRow key={supplier.supplier_id} className="hover:bg-muted/50">
                  <TableCell className="font-medium text-gray-500">
                    {idx < 3 && (
                      <Trophy className={`h-4 w-4 inline ${idx === 0 ? 'text-yellow-500' : idx === 1 ? 'text-gray-400' : 'text-amber-600'}`} />
                    )}
                    {idx >= 3 && idx + 1}
                  </TableCell>
                  <TableCell>
                    <div>
                      <Link
                        href={`/epazar/suppliers/${encodeURIComponent(supplier.supplier_id)}`}
                        className="font-medium hover:text-primary hover:underline"
                      >
                        {supplier.company_name}
                      </Link>
                      {supplier.tax_id && (
                        <div className="text-xs text-gray-500">ДБ: {supplier.tax_id}</div>
                      )}
                    </div>
                  </TableCell>
                  {showCity && (
                    <TableCell className="text-sm text-gray-600">
                      {supplier.city || '-'}
                    </TableCell>
                  )}
                  <TableCell className="text-right">
                    <div>
                      <div className="font-semibold">{supplier.total_wins}</div>
                      <div className="text-xs text-gray-500">од {supplier.total_offers}</div>
                    </div>
                  </TableCell>
                  <TableCell className="text-center">
                    <div className="flex items-center justify-center gap-2">
                      <span className="font-semibold">{supplier.win_rate.toFixed(1)}%</span>
                      {getWinRateBadge(supplier.win_rate)}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="font-semibold text-green-600">
                      {formatCurrency(supplier.total_contract_value_mkd)}
                    </div>
                    {supplier.avg_bid_amount_mkd && (
                      <div className="text-xs text-gray-500">
                        Просек: {formatCurrency(supplier.avg_bid_amount_mkd)}
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
