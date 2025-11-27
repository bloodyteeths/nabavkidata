'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api, SupplierDetail } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import {
  Building2,
  Trophy,
  FileText,
  TrendingUp,
  ArrowLeft,
  Mail,
  Phone,
  Globe,
  MapPin,
  User,
  ExternalLink,
} from 'lucide-react';
import Link from 'next/link';
import { formatDate } from '@/lib/utils';

export default function SupplierDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [supplier, setSupplier] = useState<SupplierDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const supplierId = params.id as string;

  useEffect(() => {
    if (supplierId) {
      fetchSupplier();
    }
  }, [supplierId]);

  const fetchSupplier = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.getSupplier(supplierId);
      setSupplier(response);
    } catch (err: any) {
      setError(err.message || 'Failed to load supplier');
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (value?: number) => {
    if (!value) return '-';
    return new Intl.NumberFormat('mk-MK', {
      style: 'currency',
      currency: 'MKD',
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatPercent = (value?: number) => {
    if (value === null || value === undefined) return '-';
    return `${(value * 100).toFixed(1)}%`;
  };

  if (loading) {
    return (
      <div className="container mx-auto py-8 px-4">
        <div className="flex items-center justify-center h-64">
          <div className="flex items-center gap-2">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
            <span>Се вчитува...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !supplier) {
    return (
      <div className="container mx-auto py-8 px-4">
        <Card className="border-destructive">
          <CardContent className="pt-6">
            <div className="text-center">
              <p className="text-destructive mb-4">{error || 'Добавувачот не е пронајден'}</p>
              <Button onClick={() => router.push('/suppliers')}>
                <ArrowLeft className="h-4 w-4 mr-2" />
                Назад кон добавувачи
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4">
      {/* Back Button */}
      <Button variant="ghost" onClick={() => router.push('/suppliers')} className="mb-4">
        <ArrowLeft className="h-4 w-4 mr-2" />
        Назад кон добавувачи
      </Button>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold">{supplier.company_name}</h1>
          {supplier.tax_id && (
            <p className="text-muted-foreground mt-1">ЕДБ: {supplier.tax_id}</p>
          )}
        </div>
        <Badge variant={supplier.total_wins > 0 ? 'default' : 'secondary'} className="text-lg px-4 py-2">
          {supplier.total_wins} победи
        </Badge>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <FileText className="h-8 w-8 text-blue-500" />
              <div>
                <p className="text-sm text-muted-foreground">Вкупно понуди</p>
                <p className="text-2xl font-bold">{supplier.total_bids}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Trophy className="h-8 w-8 text-yellow-500" />
              <div>
                <p className="text-sm text-muted-foreground">Победи</p>
                <p className="text-2xl font-bold">{supplier.total_wins}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <TrendingUp className="h-8 w-8 text-green-500" />
              <div>
                <p className="text-sm text-muted-foreground">Стапка на победи</p>
                <p className="text-2xl font-bold">{formatPercent(supplier.win_rate)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <Building2 className="h-8 w-8 text-purple-500" />
              <div>
                <p className="text-sm text-muted-foreground">Вкупна вредност</p>
                <p className="text-xl font-bold">{formatCurrency(supplier.total_value_won_mkd)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Contact Information */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              Контакт информации
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {supplier.address && (
              <div className="flex items-start gap-2">
                <MapPin className="h-4 w-4 mt-1 text-muted-foreground" />
                <span>{supplier.address}</span>
              </div>
            )}
            {supplier.city && (
              <div className="flex items-center gap-2">
                <Building2 className="h-4 w-4 text-muted-foreground" />
                <span>{supplier.city}, {supplier.country || 'Северна Македонија'}</span>
              </div>
            )}
            {supplier.contact_person && (
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" />
                <span>{supplier.contact_person}</span>
              </div>
            )}
            {supplier.contact_email && (
              <div className="flex items-center gap-2">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <a href={`mailto:${supplier.contact_email}`} className="hover:text-primary">
                  {supplier.contact_email}
                </a>
              </div>
            )}
            {supplier.contact_phone && (
              <div className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-muted-foreground" />
                <a href={`tel:${supplier.contact_phone}`} className="hover:text-primary">
                  {supplier.contact_phone}
                </a>
              </div>
            )}
            {supplier.website && (
              <div className="flex items-center gap-2">
                <Globe className="h-4 w-4 text-muted-foreground" />
                <a href={supplier.website} target="_blank" rel="noopener noreferrer" className="hover:text-primary flex items-center gap-1">
                  {supplier.website}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
            {!supplier.address && !supplier.city && !supplier.contact_person && !supplier.contact_email && !supplier.contact_phone && !supplier.website && (
              <p className="text-muted-foreground text-sm">Нема достапни контакт информации</p>
            )}
          </CardContent>
        </Card>

        {/* Wins by Category */}
        <Card>
          <CardHeader>
            <CardTitle>Победи по категорија</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(supplier.wins_by_category).length > 0 ? (
              <div className="space-y-2">
                {Object.entries(supplier.wins_by_category)
                  .sort(([, a], [, b]) => b - a)
                  .map(([category, count]) => (
                    <div key={category} className="flex items-center justify-between">
                      <span className="text-sm truncate flex-1">{category}</span>
                      <Badge variant="outline">{count}</Badge>
                    </div>
                  ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">Нема евидентирани победи</p>
            )}
          </CardContent>
        </Card>

        {/* Wins by Entity */}
        <Card>
          <CardHeader>
            <CardTitle>Победи по институција</CardTitle>
          </CardHeader>
          <CardContent>
            {Object.keys(supplier.wins_by_entity).length > 0 ? (
              <div className="space-y-2">
                {Object.entries(supplier.wins_by_entity)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 10)
                  .map(([entity, count]) => (
                    <div key={entity} className="flex items-center justify-between">
                      <span className="text-sm truncate flex-1" title={entity}>{entity}</span>
                      <Badge variant="outline">{count}</Badge>
                    </div>
                  ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">Нема евидентирани победи</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Recent Participations */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Последни учества во тендери</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Тендер</TableHead>
                <TableHead>Договорен орган</TableHead>
                <TableHead className="text-right">Понуда</TableHead>
                <TableHead className="text-center">Ранг</TableHead>
                <TableHead className="text-center">Статус</TableHead>
                <TableHead className="text-right">Датум</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {supplier.recent_participations.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                    Нема евидентирани учества
                  </TableCell>
                </TableRow>
              ) : (
                supplier.recent_participations.map((participation) => (
                  <TableRow key={participation.tender_id} className="hover:bg-muted/50">
                    <TableCell>
                      <Link
                        href={`/tenders/${encodeURIComponent(participation.tender_id)}`}
                        className="font-medium hover:text-primary line-clamp-2"
                      >
                        {participation.title}
                      </Link>
                    </TableCell>
                    <TableCell className="max-w-[200px] truncate" title={participation.procuring_entity}>
                      {participation.procuring_entity}
                    </TableCell>
                    <TableCell className="text-right font-mono">
                      {formatCurrency(participation.bid_amount_mkd)}
                    </TableCell>
                    <TableCell className="text-center">
                      {participation.rank ? (
                        <Badge variant={participation.rank === 1 ? 'default' : 'outline'}>
                          #{participation.rank}
                        </Badge>
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell className="text-center">
                      {participation.is_winner ? (
                        <Badge className="bg-green-500">Победник</Badge>
                      ) : (
                        <Badge variant="secondary">{participation.status}</Badge>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      {formatDate(participation.closing_date)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
