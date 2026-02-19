'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  AlertTriangle,
  Shield,
  Building2,
  TrendingUp,
  RefreshCw,
  Eye,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface CorruptionStats {
  total_flags: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  total_tenders_flagged: number;
  total_value_at_risk_mkd: number | null;
  last_analysis_run: string | null;
}

interface FlaggedTender {
  tender_id: string;
  title: string;
  procuring_entity: string;
  winner: string | null;
  estimated_value_mkd: number | null;
  status: string;
  total_flags: number;
  risk_score: number;
  risk_level: string;
  flag_types: string[];
  max_severity: string;
}

interface InstitutionRisk {
  institution_name: string;
  total_tenders: number;
  flagged_tenders: number;
  flag_percentage: number;
  total_flags: number;
  risk_level: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
};

const FLAG_TYPE_LABELS: Record<string, string> = {
  single_bidder: 'Еден понудувач',
  repeat_winner: 'Повторлив победник',
  price_anomaly: 'Ценовна аномалија',
  bid_clustering: 'Кластер понуди',
  short_deadline: 'Краток рок',
};

export default function CorruptionDashboard() {
  const [stats, setStats] = useState<CorruptionStats | null>(null);
  const [flaggedTenders, setFlaggedTenders] = useState<FlaggedTender[]>([]);
  const [institutions, setInstitutions] = useState<InstitutionRisk[]>([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const authToken = localStorage.getItem('auth_token');
      const headers: HeadersInit = authToken
        ? { Authorization: `Bearer ${authToken}` }
        : {};

      // Fetch stats
      const statsRes = await fetch('/api/corruption/stats', { headers });
      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      // Fetch flagged tenders
      const tendersRes = await fetch('/api/corruption/flagged-tenders?limit=20', { headers });
      if (tendersRes.ok) {
        const tendersData = await tendersRes.json();
        setFlaggedTenders(tendersData.tenders || []);
      }

      // Fetch institution risk
      const institutionsRes = await fetch('/api/corruption/institutions/risk?limit=10', { headers });
      if (institutionsRes.ok) {
        const institutionsData = await institutionsRes.json();
        setInstitutions(institutionsData.institutions || []);
      }
    } catch (error) {
      console.error('Error fetching corruption data:', error);
      toast.error('Грешка при вчитување на податоци');
    } finally {
      setLoading(false);
    }
  };

  const triggerAnalysis = async () => {
    try {
      setAnalyzing(true);
      const authToken = localStorage.getItem('auth_token');
      const response = await fetch('/api/corruption/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${authToken}`,
        },
      });

      if (response.ok) {
        toast.success('Анализата е започната');
        // Refresh data after a delay
        setTimeout(fetchData, 5000);
      } else {
        toast.error('Грешка при стартување на анализа');
      }
    } catch (error) {
      console.error('Error triggering analysis:', error);
      toast.error('Грешка при стартување на анализа');
    } finally {
      setAnalyzing(false);
    }
  };

  const getSeverityBadge = (severity: string) => {
    const variants: Record<string, 'destructive' | 'default' | 'secondary' | 'outline'> = {
      critical: 'destructive',
      high: 'destructive',
      medium: 'default',
      low: 'secondary',
    };
    const labels: Record<string, string> = {
      critical: 'Критично',
      high: 'Високо',
      medium: 'Средно',
      low: 'Ниско',
    };
    return (
      <Badge variant={variants[severity] || 'outline'}>
        {labels[severity] || severity}
      </Badge>
    );
  };

  const formatValue = (value: number | null) => {
    if (!value) return 'N/A';
    return new Intl.NumberFormat('mk-MK', {
      style: 'currency',
      currency: 'MKD',
      maximumFractionDigits: 0,
    }).format(value);
  };

  // Prepare chart data
  const severityChartData = stats
    ? Object.entries(stats.by_severity).map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value,
        color: SEVERITY_COLORS[name] || '#94a3b8',
      }))
    : [];

  const typeChartData = stats
    ? Object.entries(stats.by_type)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([type, count]) => ({
          name: FLAG_TYPE_LABELS[type] || type,
          count,
        }))
    : [];

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Вчитување...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Shield className="w-8 h-8 text-red-500" />
            Детекција на Корупција
          </h1>
          <p className="text-muted-foreground mt-1">
            AI анализа на ризични тендери и сомнителни шеми
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchData}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Освежи
          </Button>
          <Button onClick={triggerAnalysis} disabled={analyzing}>
            {analyzing ? (
              <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <AlertTriangle className="w-4 h-4 mr-2" />
            )}
            {analyzing ? 'Анализира...' : 'Нова Анализа'}
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Вкупно Знамиња</CardTitle>
            <AlertTriangle className="w-4 h-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_flags || 0}</div>
            <p className="text-xs text-muted-foreground">
              Детектирани индикатори
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Означени Тендери</CardTitle>
            <AlertCircle className="w-4 h-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_tenders_flagged || 0}</div>
            <p className="text-xs text-muted-foreground">
              Тендери со ризик
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Критични</CardTitle>
            <AlertTriangle className="w-4 h-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {stats?.by_severity?.critical || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Итни случаи
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Вредност во Ризик</CardTitle>
            <TrendingUp className="w-4 h-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.total_value_at_risk_mkd
                ? `${(stats.total_value_at_risk_mkd / 1000000).toFixed(1)}M`
                : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">
              МКД вкупно
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Severity Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Распределба по Сериозност</CardTitle>
          </CardHeader>
          <CardContent>
            {severityChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie
                    data={severityChartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {severityChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">
                Нема податоци
              </div>
            )}
          </CardContent>
        </Card>

        {/* Flag Types */}
        <Card>
          <CardHeader>
            <CardTitle>Типови на Знамиња</CardTitle>
          </CardHeader>
          <CardContent>
            {typeChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={typeChartData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="count" fill="#f97316" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">
                Нема податоци
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Flagged Tenders Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-orange-500" />
            Означени Тендери
          </CardTitle>
          <CardDescription>
            Тендери со највисок ризик скор
          </CardDescription>
        </CardHeader>
        <CardContent>
          {flaggedTenders.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Тендер</TableHead>
                  <TableHead>Институција</TableHead>
                  <TableHead className="text-right">Вредност</TableHead>
                  <TableHead className="text-center">Ризик</TableHead>
                  <TableHead className="text-center">Знамиња</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {flaggedTenders.map((tender) => (
                  <TableRow key={tender.tender_id}>
                    <TableCell>
                      <div className="max-w-[300px]">
                        <p className="font-medium truncate" title={tender.title || 'N/A'}>
                          {tender.title || 'Без наслов'}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {tender.tender_id}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <p className="truncate max-w-[200px]" title={tender.procuring_entity || ''}>
                        {tender.procuring_entity || 'N/A'}
                      </p>
                    </TableCell>
                    <TableCell className="text-right">
                      {formatValue(tender.estimated_value_mkd)}
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="flex flex-col items-center gap-1">
                        <span className="font-bold">{tender.risk_score}</span>
                        {getSeverityBadge(tender.risk_level)}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline">{tender.total_flags}</Badge>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => window.open(`/tenders/${tender.tender_id}`, '_blank')}
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <CheckCircle2 className="w-12 h-12 mb-4 text-green-500" />
              <p>Нема означени тендери</p>
              <p className="text-sm">Сите тендери се во нормални параметри</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Institution Risk */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-blue-500" />
            Институции со Највисок Ризик
          </CardTitle>
          <CardDescription>
            Институции рангирани по број на означени тендери
          </CardDescription>
        </CardHeader>
        <CardContent>
          {institutions.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Институција</TableHead>
                  <TableHead className="text-center">Тендери</TableHead>
                  <TableHead className="text-center">Означени</TableHead>
                  <TableHead className="text-center">%</TableHead>
                  <TableHead className="text-center">Ризик</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {institutions.map((inst, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <p className="truncate max-w-[300px]" title={inst.institution_name}>
                        {inst.institution_name}
                      </p>
                    </TableCell>
                    <TableCell className="text-center">{inst.total_tenders}</TableCell>
                    <TableCell className="text-center">{inst.flagged_tenders}</TableCell>
                    <TableCell className="text-center">
                      <span className={inst.flag_percentage > 50 ? 'text-red-500 font-bold' : ''}>
                        {inst.flag_percentage.toFixed(1)}%
                      </span>
                    </TableCell>
                    <TableCell className="text-center">
                      {getSeverityBadge(inst.risk_level)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
              <CheckCircle2 className="w-12 h-12 mb-4 text-green-500" />
              <p>Нема ризични институции</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Last Analysis Info */}
      {stats?.last_analysis_run && (
        <Card>
          <CardContent className="py-4">
            <p className="text-sm text-muted-foreground text-center">
              Последна анализа: {new Date(stats.last_analysis_run).toLocaleString('mk-MK')}
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
