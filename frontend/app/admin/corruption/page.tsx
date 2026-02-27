'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { tenderUrl } from '@/lib/utils';
import {
  AlertTriangle,
  Shield,
  Building2,
  TrendingUp,
  RefreshCw,
  Eye,
  AlertCircle,
  CheckCircle2,
  Plus,
  FileText,
  Users,
  Clock,
  MessageSquare,
  Link2,
  ChevronDown,
  ChevronUp,
  Briefcase,
  Megaphone,
  X,
  Search,
  FolderOpen,
  StickyNote,
  Scale,
  Activity,
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

// ---------------------------------------------------------------------------
// API URL
// ---------------------------------------------------------------------------
const API_URL =
  typeof window !== 'undefined'
    ? window.location.hostname === 'localhost'
      ? 'http://localhost:8000'
      : 'https://api.nabavkidata.com'
    : 'https://api.nabavkidata.com';

// ---------------------------------------------------------------------------
// Helper: auth headers
// ---------------------------------------------------------------------------
function authHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options?.headers || {}) },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Types — Overview
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// Types — Investigations
// ---------------------------------------------------------------------------
interface InvestigationDashboard {
  total_cases: number;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  open_cases: number;
  recent_activity: Array<{ id: number; action: string; created_at: string; details?: string }>;
}

interface InvestigationCase {
  id: number;
  title: string;
  description: string;
  status: string;
  priority: string;
  assigned_to: string | null;
  tenders_count?: number;
  entities_count?: number;
  evidence_count?: number;
  notes_count?: number;
  created_at: string;
  updated_at: string;
  tenders?: Array<{ tender_id: string; role: string; title?: string }>;
  entities?: Array<{ entity_id: string; entity_type: string; entity_name: string; role: string }>;
  evidence?: Array<{ id: number; evidence_type: string; source_module: string; title: string; description: string; severity: string; metadata?: Record<string, unknown>; created_at: string }>;
  notes?: Array<{ id: number; content: string; author: string; created_at: string }>;
}

interface TimelineEntry {
  id: number;
  action: string;
  actor?: string;
  details?: string;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Types — Whistleblower Tips
// ---------------------------------------------------------------------------
interface WhistleblowerStats {
  total_tips: number;
  by_status: Record<string, number>;
  avg_triage_score: number | null;
  tips_this_week: number;
}

interface WhistleblowerTip {
  id: number;
  category: string;
  triage_score: number | null;
  urgency: string;
  status: string;
  description: string;
  extracted_entities?: Array<{ name: string; type: string }>;
  matched_tenders?: Array<{ tender_id: string; title?: string }>;
  triage_details?: Record<string, unknown>;
  analyst_note?: string | null;
  linked_case_id?: number | null;
  submitted_at: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
};

const FLAG_TYPE_LABELS: Record<string, string> = {
  single_bidder: '1 понудувач',
  repeat_winner: 'Повторен победник',
  price_anomaly: 'Ценовна аномалија',
  bid_clustering: 'Кластер понуди',
  short_deadline: 'Краток рок',
  procedure_type: 'Ризична постапка',
  identical_bids: 'Идентични понуди',
  professional_loser: 'Покривач понудувач',
  contract_splitting: 'Делење договори',
  short_decision: 'Брза одлука',
  strategic_disqualification: 'Стратешка дисквалификација',
  contract_value_growth: 'Раст на вредност',
  bid_rotation: 'Ротација понуди',
  threshold_manipulation: 'Манипулација на праг',
  late_amendment: 'Доцен амандман',
};

const FLAG_TYPE_COLORS: Record<string, string> = {
  single_bidder: '#f59e0b',
  repeat_winner: '#ef4444',
  price_anomaly: '#a855f7',
  bid_clustering: '#6366f1',
  short_deadline: '#ca8a04',
  procedure_type: '#64748b',
  identical_bids: '#e11d48',
  professional_loser: '#71717a',
  contract_splitting: '#059669',
  short_decision: '#06b6d4',
  strategic_disqualification: '#dc2626',
  contract_value_growth: '#ea580c',
  bid_rotation: '#8b5cf6',
  threshold_manipulation: '#14b8a6',
  late_amendment: '#d97706',
};

const TOTAL_INDICATORS = Object.keys(FLAG_TYPE_LABELS).length;

const CASE_STATUS_LABELS: Record<string, string> = {
  open: 'Отворена',
  in_progress: 'Во тек',
  review: 'Преглед',
  closed: 'Затворена',
  archived: 'Архивирана',
};

const CASE_STATUS_VARIANTS: Record<string, 'destructive' | 'default' | 'secondary' | 'outline'> = {
  open: 'default',
  in_progress: 'destructive',
  review: 'secondary',
  closed: 'outline',
  archived: 'outline',
};

const PRIORITY_LABELS: Record<string, string> = {
  low: 'Низок',
  medium: 'Среден',
  high: 'Висок',
  critical: 'Критичен',
};

const PRIORITY_COLORS: Record<string, string> = {
  low: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  high: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
};

const TIP_CATEGORY_LABELS: Record<string, string> = {
  bid_rigging: 'Намештени понуди',
  bribery: 'Поткуп',
  conflict_of_interest: 'Конфликт на интереси',
  fraud: 'Измама',
  other: 'Друго',
};

const TIP_STATUS_LABELS: Record<string, string> = {
  submitted: 'Поднесена',
  under_review: 'Во преглед',
  investigating: 'Се истражува',
  resolved: 'Решена',
  dismissed: 'Одбиена',
  linked: 'Поврзана',
};

const TIP_STATUS_VARIANTS: Record<string, 'destructive' | 'default' | 'secondary' | 'outline'> = {
  submitted: 'default',
  under_review: 'secondary',
  investigating: 'destructive',
  resolved: 'outline',
  dismissed: 'outline',
  linked: 'secondary',
};

const URGENCY_LABELS: Record<string, string> = {
  low: 'Низок',
  medium: 'Среден',
  high: 'Висок',
  critical: 'Критичен',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatMKD(value: number | null) {
  if (!value) return 'Н/Д';
  return new Intl.NumberFormat('mk-MK', {
    style: 'currency',
    currency: 'MKD',
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(d: string | null | undefined) {
  if (!d) return 'Н/Д';
  return new Date(d).toLocaleDateString('mk-MK', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function formatDateTime(d: string | null | undefined) {
  if (!d) return 'Н/Д';
  return new Date(d).toLocaleString('mk-MK', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function severityBadge(severity: string) {
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
  return <Badge variant={variants[severity] || 'outline'}>{labels[severity] || severity}</Badge>;
}

function priorityBadge(priority: string) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${PRIORITY_COLORS[priority] || 'bg-gray-100 text-gray-800'}`}>
      {PRIORITY_LABELS[priority] || priority}
    </span>
  );
}

// ============================================================================================
// MAIN COMPONENT
// ============================================================================================
export default function CorruptionDashboard() {
  const [activeTab, setActiveTab] = useState('overview');

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <Shield className="w-8 h-8 text-red-500" />
          Детекција на Корупција
        </h1>
        <p className="text-muted-foreground mt-1">
          AI анализа на ризични тендери, истраги и пријави од укажувачи
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3 max-w-lg">
          <TabsTrigger value="overview" className="gap-1.5">
            <Activity className="w-4 h-4" />
            Преглед
          </TabsTrigger>
          <TabsTrigger value="investigations" className="gap-1.5">
            <Briefcase className="w-4 h-4" />
            Истраги
          </TabsTrigger>
          <TabsTrigger value="tips" className="gap-1.5">
            <Megaphone className="w-4 h-4" />
            Пријави
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab />
        </TabsContent>
        <TabsContent value="investigations">
          <InvestigationsTab />
        </TabsContent>
        <TabsContent value="tips">
          <TipsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ============================================================================================
// TAB 1: OVERVIEW
// ============================================================================================
function OverviewTab() {
  const [stats, setStats] = useState<CorruptionStats | null>(null);
  const [flaggedTenders, setFlaggedTenders] = useState<FlaggedTender[]>([]);
  const [institutions, setInstitutions] = useState<InstitutionRisk[]>([]);
  const [invDashboard, setInvDashboard] = useState<InvestigationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [statsData, tendersData, institutionsData, dashboardData] = await Promise.allSettled([
        apiFetch<CorruptionStats>('/api/corruption/stats'),
        apiFetch<{ tenders: FlaggedTender[] }>('/api/corruption/flagged-tenders?limit=20'),
        apiFetch<{ institutions: InstitutionRisk[] }>('/api/corruption/institutions/risk?limit=10'),
        apiFetch<InvestigationDashboard>('/api/corruption/investigations/dashboard'),
      ]);
      if (statsData.status === 'fulfilled') setStats(statsData.value);
      if (tendersData.status === 'fulfilled') setFlaggedTenders(tendersData.value.tenders || []);
      if (institutionsData.status === 'fulfilled') setInstitutions(institutionsData.value.institutions || []);
      if (dashboardData.status === 'fulfilled') setInvDashboard(dashboardData.value);
    } catch (error) {
      console.error('Error fetching corruption data:', error);
      toast.error('Грешка при вчитување на податоци');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const triggerAnalysis = async () => {
    try {
      setAnalyzing(true);
      await apiFetch('/api/corruption/analyze', { method: 'POST' });
      toast.success('Анализата е започната');
      setTimeout(fetchData, 5000);
    } catch {
      toast.error('Грешка при стартување на анализа');
    } finally {
      setAnalyzing(false);
    }
  };

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
        .slice(0, TOTAL_INDICATORS)
        .map(([type, count]) => ({
          name: FLAG_TYPE_LABELS[type] || type,
          count,
          type,
          color: FLAG_TYPE_COLORS[type] || '#f97316',
        }))
    : [];

  if (loading) {
    return (
      <div className="space-y-6 mt-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {[...Array(4)].map((_, i) => (
            <Card key={i}>
              <CardHeader className="pb-2"><Skeleton className="h-4 w-24" /></CardHeader>
              <CardContent><Skeleton className="h-8 w-16" /><Skeleton className="h-3 w-32 mt-2" /></CardContent>
            </Card>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card><CardContent className="pt-6"><Skeleton className="h-[250px]" /></CardContent></Card>
          <Card><CardContent className="pt-6"><Skeleton className="h-[250px]" /></CardContent></Card>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 mt-4">
      {/* Action Bar */}
      <div className="flex items-center justify-end gap-2">
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="w-4 h-4 mr-2" />
          Освежи
        </Button>
        <Button size="sm" onClick={triggerAnalysis} disabled={analyzing}>
          {analyzing ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <AlertTriangle className="w-4 h-4 mr-2" />}
          {analyzing ? 'Анализира...' : 'Нова Анализа'}
        </Button>
      </div>

      {/* Corruption Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Вкупно Знамиња</CardTitle>
            <AlertTriangle className="w-4 h-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_flags || 0}</div>
            <p className="text-xs text-muted-foreground">Детектирани индикатори</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Означени Тендери</CardTitle>
            <AlertCircle className="w-4 h-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_tenders_flagged || 0}</div>
            <p className="text-xs text-muted-foreground">Тендери со ризик</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Критични</CardTitle>
            <AlertTriangle className="w-4 h-4 text-red-600" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats?.by_severity?.critical || 0}</div>
            <p className="text-xs text-muted-foreground">Итни случаи</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Вредност во Ризик</CardTitle>
            <TrendingUp className="w-4 h-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {stats?.total_value_at_risk_mkd ? `${(stats.total_value_at_risk_mkd / 1000000).toFixed(1)}M` : 'Н/Д'}
            </div>
            <p className="text-xs text-muted-foreground">МКД вкупно</p>
          </CardContent>
        </Card>
      </div>

      {/* Investigation Dashboard Stats */}
      {invDashboard && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="border-blue-200">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Вкупно Истраги</CardTitle>
              <Briefcase className="w-4 h-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{invDashboard.total_cases}</div>
              <p className="text-xs text-muted-foreground">Сите случаи</p>
            </CardContent>
          </Card>
          <Card className="border-orange-200">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Отворени Истраги</CardTitle>
              <FolderOpen className="w-4 h-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-600">{invDashboard.open_cases}</div>
              <p className="text-xs text-muted-foreground">Чекаат акција</p>
            </CardContent>
          </Card>
          <Card className="border-purple-200">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Во тек</CardTitle>
              <Activity className="w-4 h-4 text-purple-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-purple-600">{invDashboard.by_status?.in_progress || 0}</div>
              <p className="text-xs text-muted-foreground">Активни истраги</p>
            </CardContent>
          </Card>
          <Card className="border-green-200">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Затворени</CardTitle>
              <CheckCircle2 className="w-4 h-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{invDashboard.by_status?.closed || 0}</div>
              <p className="text-xs text-muted-foreground">Завршени истраги</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle>Распределба по Сериозност</CardTitle></CardHeader>
          <CardContent>
            {severityChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={severityChartData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} paddingAngle={2} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                    {severityChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">Нема податоци</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Типови на Знамиња ({TOTAL_INDICATORS} индикатори)</CardTitle></CardHeader>
          <CardContent>
            {typeChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={Math.max(250, typeChartData.length * 28)}>
                <BarChart data={typeChartData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" />
                  <YAxis dataKey="name" type="category" width={160} tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {typeChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex items-center justify-center h-[250px] text-muted-foreground">Нема податоци</div>
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
          <CardDescription>Тендери со највисок ризик скор</CardDescription>
        </CardHeader>
        <CardContent>
          {flaggedTenders.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Тендер</TableHead>
                  <TableHead>Институција</TableHead>
                  <TableHead className="text-right">Вредност</TableHead>
                  <TableHead className="text-center">CRI</TableHead>
                  <TableHead className="text-center">Знамиња</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {flaggedTenders.map((tender) => (
                  <TableRow key={tender.tender_id}>
                    <TableCell>
                      <div className="max-w-[300px]">
                        <p className="font-medium truncate" title={tender.title || 'Без наслов'}>{tender.title || 'Без наслов'}</p>
                        <p className="text-xs text-muted-foreground">{tender.tender_id}</p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <p className="truncate max-w-[200px]" title={tender.procuring_entity || ''}>{tender.procuring_entity || 'Н/Д'}</p>
                    </TableCell>
                    <TableCell className="text-right">{formatMKD(tender.estimated_value_mkd)}</TableCell>
                    <TableCell className="text-center">
                      <div className="flex flex-col items-center gap-1">
                        <span className="font-bold">{tender.risk_score}</span>
                        {severityBadge(tender.risk_level)}
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <div className="flex flex-wrap gap-1 justify-center">
                        <Badge variant="outline">{tender.total_flags}/{TOTAL_INDICATORS}</Badge>
                        {tender.flag_types?.slice(0, 3).map((ft: string) => (
                          <Badge key={ft} variant="secondary" className="text-[9px]">{FLAG_TYPE_LABELS[ft] || ft}</Badge>
                        ))}
                        {tender.flag_types && tender.flag_types.length > 3 && (
                          <Badge variant="outline" className="text-[9px]">+{tender.flag_types.length - 3}</Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm" onClick={() => window.open(tenderUrl(tender.tender_id), '_blank')}>
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
          <CardDescription>Институции рангирани по број на означени тендери</CardDescription>
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
                      <p className="truncate max-w-[300px]" title={inst.institution_name}>{inst.institution_name}</p>
                    </TableCell>
                    <TableCell className="text-center">{inst.total_tenders}</TableCell>
                    <TableCell className="text-center">{inst.flagged_tenders}</TableCell>
                    <TableCell className="text-center">
                      <span className={inst.flag_percentage > 50 ? 'text-red-500 font-bold' : ''}>{inst.flag_percentage.toFixed(1)}%</span>
                    </TableCell>
                    <TableCell className="text-center">{severityBadge(inst.risk_level)}</TableCell>
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

// ============================================================================================
// TAB 2: INVESTIGATIONS
// ============================================================================================
function InvestigationsTab() {
  const [cases, setCases] = useState<InvestigationCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showNewCaseForm, setShowNewCaseForm] = useState(false);
  const [expandedCaseId, setExpandedCaseId] = useState<number | null>(null);

  // New case form
  const [newTitle, setNewTitle] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newPriority, setNewPriority] = useState('medium');
  const [creating, setCreating] = useState(false);

  const fetchCases = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ limit: '50', offset: '0' });
      if (statusFilter && statusFilter !== 'all') params.set('status', statusFilter);
      const data = await apiFetch<{ cases: InvestigationCase[] } | InvestigationCase[]>(
        `/api/corruption/investigations/cases?${params}`
      );
      setCases(Array.isArray(data) ? data : data.cases || []);
    } catch (error) {
      console.error('Error fetching cases:', error);
      toast.error('Грешка при вчитување на истраги');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchCases();
  }, [fetchCases]);

  const createCase = async () => {
    if (!newTitle.trim()) {
      toast.error('Внесете наслов');
      return;
    }
    try {
      setCreating(true);
      await apiFetch('/api/corruption/investigations/cases', {
        method: 'POST',
        body: JSON.stringify({ title: newTitle.trim(), description: newDescription.trim(), priority: newPriority }),
      });
      toast.success('Истрагата е креирана');
      setNewTitle('');
      setNewDescription('');
      setNewPriority('medium');
      setShowNewCaseForm(false);
      fetchCases();
    } catch {
      toast.error('Грешка при креирање на истрага');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-4 mt-4">
      {/* Top bar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Филтер статус" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Сите статуси</SelectItem>
              {Object.entries(CASE_STATUS_LABELS).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={fetchCases}>
            <RefreshCw className="w-4 h-4 mr-1" /> Освежи
          </Button>
        </div>
        <Button size="sm" onClick={() => setShowNewCaseForm(!showNewCaseForm)}>
          {showNewCaseForm ? <X className="w-4 h-4 mr-1" /> : <Plus className="w-4 h-4 mr-1" />}
          {showNewCaseForm ? 'Откажи' : 'Нов Случај'}
        </Button>
      </div>

      {/* New case form */}
      {showNewCaseForm && (
        <Card className="border-blue-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Креирај нов случај за истрага</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Input placeholder="Наслов на случајот" value={newTitle} onChange={(e) => setNewTitle(e.target.value)} />
            <Textarea placeholder="Опис (опционално)" value={newDescription} onChange={(e) => setNewDescription(e.target.value)} rows={3} />
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium">Приоритет:</label>
              <Select value={newPriority} onValueChange={setNewPriority}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(PRIORITY_LABELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex justify-end">
              <Button onClick={createCase} disabled={creating}>
                {creating ? <RefreshCw className="w-4 h-4 mr-1 animate-spin" /> : <Plus className="w-4 h-4 mr-1" />}
                {creating ? 'Креира...' : 'Креирај'}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Cases list */}
      {loading ? (
        <Card>
          <CardContent className="pt-6 space-y-3">
            {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </CardContent>
        </Card>
      ) : cases.length === 0 ? (
        <Card>
          <CardContent className="py-16">
            <div className="flex flex-col items-center text-muted-foreground">
              <FolderOpen className="w-12 h-12 mb-3" />
              <p className="font-medium">Нема истраги</p>
              <p className="text-sm">Креирајте нов случај за да започнете</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">ID</TableHead>
                <TableHead>Наслов</TableHead>
                <TableHead className="w-28">Статус</TableHead>
                <TableHead className="w-28">Приоритет</TableHead>
                <TableHead className="text-center w-20">Тендери</TableHead>
                <TableHead className="text-center w-20">Ентитети</TableHead>
                <TableHead className="w-28">Креирана</TableHead>
                <TableHead className="w-32">Доделена на</TableHead>
                <TableHead className="w-10"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {cases.map((c) => (
                <CaseRow
                  key={c.id}
                  caseItem={c}
                  isExpanded={expandedCaseId === c.id}
                  onToggle={() => setExpandedCaseId(expandedCaseId === c.id ? null : c.id)}
                  onRefresh={fetchCases}
                />
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Case Row + Expandable Detail
// ---------------------------------------------------------------------------
function CaseRow({
  caseItem,
  isExpanded,
  onToggle,
  onRefresh,
}: {
  caseItem: InvestigationCase;
  isExpanded: boolean;
  onToggle: () => void;
  onRefresh: () => void;
}) {
  return (
    <>
      <TableRow className="cursor-pointer hover:bg-muted/50" onClick={onToggle}>
        <TableCell className="font-mono text-xs">#{caseItem.id}</TableCell>
        <TableCell>
          <p className="font-medium truncate max-w-[300px]" title={caseItem.title}>{caseItem.title}</p>
        </TableCell>
        <TableCell>
          <Badge variant={CASE_STATUS_VARIANTS[caseItem.status] || 'outline'}>
            {CASE_STATUS_LABELS[caseItem.status] || caseItem.status}
          </Badge>
        </TableCell>
        <TableCell>{priorityBadge(caseItem.priority)}</TableCell>
        <TableCell className="text-center">{caseItem.tenders_count ?? 0}</TableCell>
        <TableCell className="text-center">{caseItem.entities_count ?? 0}</TableCell>
        <TableCell className="text-xs">{formatDate(caseItem.created_at)}</TableCell>
        <TableCell className="text-xs truncate max-w-[120px]">{caseItem.assigned_to || '-'}</TableCell>
        <TableCell>
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </TableCell>
      </TableRow>
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={9} className="p-0 bg-muted/30">
            <CaseDetail caseId={caseItem.id} onRefresh={onRefresh} />
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Case Detail Panel
// ---------------------------------------------------------------------------
function CaseDetail({ caseId, onRefresh }: { caseId: number; onRefresh: () => void }) {
  const [detail, setDetail] = useState<InvestigationCase | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [updatingPriority, setUpdatingPriority] = useState(false);

  // Add tender
  const [addTenderInput, setAddTenderInput] = useState('');
  const [addingTender, setAddingTender] = useState(false);

  // Add entity
  const [showAddEntity, setShowAddEntity] = useState(false);
  const [entityName, setEntityName] = useState('');
  const [entityType, setEntityType] = useState('company');
  const [addingEntity, setAddingEntity] = useState(false);

  // Add evidence
  const [showAddEvidence, setShowAddEvidence] = useState(false);
  const [evidenceTitle, setEvidenceTitle] = useState('');
  const [evidenceDesc, setEvidenceDesc] = useState('');
  const [evidenceType, setEvidenceType] = useState('document');
  const [evidenceSeverity, setEvidenceSeverity] = useState('medium');
  const [addingEvidence, setAddingEvidence] = useState(false);

  // Add note
  const [noteContent, setNoteContent] = useState('');
  const [noteAuthor, setNoteAuthor] = useState('');
  const [addingNote, setAddingNote] = useState(false);

  // Assigned to
  const [assignedInput, setAssignedInput] = useState('');
  const [updatingAssigned, setUpdatingAssigned] = useState(false);

  const fetchDetail = useCallback(async () => {
    try {
      setLoading(true);
      const [caseData, timelineData] = await Promise.allSettled([
        apiFetch<InvestigationCase>(`/api/corruption/investigations/cases/${caseId}`),
        apiFetch<{ timeline: TimelineEntry[] } | TimelineEntry[]>(`/api/corruption/investigations/cases/${caseId}/timeline`),
      ]);
      if (caseData.status === 'fulfilled') {
        setDetail(caseData.value);
        setAssignedInput(caseData.value.assigned_to || '');
      }
      if (timelineData.status === 'fulfilled') {
        const tl = timelineData.value;
        setTimeline(Array.isArray(tl) ? tl : tl.timeline || []);
      }
    } catch {
      toast.error('Грешка при вчитување на детали');
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  const patchCase = async (body: Record<string, string>) => {
    await apiFetch(`/api/corruption/investigations/cases/${caseId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
    fetchDetail();
    onRefresh();
  };

  const handleStatusChange = async (status: string) => {
    try {
      setUpdatingStatus(true);
      await patchCase({ status });
      toast.success(`Статус променет: ${CASE_STATUS_LABELS[status]}`);
    } catch {
      toast.error('Грешка при промена на статус');
    } finally {
      setUpdatingStatus(false);
    }
  };

  const handlePriorityChange = async (priority: string) => {
    try {
      setUpdatingPriority(true);
      await patchCase({ priority });
      toast.success(`Приоритет променет: ${PRIORITY_LABELS[priority]}`);
    } catch {
      toast.error('Грешка при промена на приоритет');
    } finally {
      setUpdatingPriority(false);
    }
  };

  const handleAssignedChange = async () => {
    try {
      setUpdatingAssigned(true);
      await patchCase({ assigned_to: assignedInput.trim() });
      toast.success('Доделено');
    } catch {
      toast.error('Грешка');
    } finally {
      setUpdatingAssigned(false);
    }
  };

  const addTender = async () => {
    if (!addTenderInput.trim()) return;
    try {
      setAddingTender(true);
      await apiFetch(`/api/corruption/investigations/cases/${caseId}/tenders`, {
        method: 'POST',
        body: JSON.stringify({ tender_id: addTenderInput.trim(), role: 'suspect' }),
      });
      toast.success('Тендерот е додаден');
      setAddTenderInput('');
      fetchDetail();
      onRefresh();
    } catch {
      toast.error('Грешка при додавање на тендер');
    } finally {
      setAddingTender(false);
    }
  };

  const addEntity = async () => {
    if (!entityName.trim()) return;
    try {
      setAddingEntity(true);
      await apiFetch(`/api/corruption/investigations/cases/${caseId}/entities`, {
        method: 'POST',
        body: JSON.stringify({
          entity_id: entityName.trim().toLowerCase().replace(/\s+/g, '-'),
          entity_type: entityType,
          entity_name: entityName.trim(),
          role: 'suspect',
        }),
      });
      toast.success('Ентитетот е додаден');
      setEntityName('');
      setShowAddEntity(false);
      fetchDetail();
      onRefresh();
    } catch {
      toast.error('Грешка при додавање на ентитет');
    } finally {
      setAddingEntity(false);
    }
  };

  const addEvidence = async () => {
    if (!evidenceTitle.trim()) return;
    try {
      setAddingEvidence(true);
      await apiFetch(`/api/corruption/investigations/cases/${caseId}/evidence`, {
        method: 'POST',
        body: JSON.stringify({
          evidence_type: evidenceType,
          source_module: 'admin',
          title: evidenceTitle.trim(),
          description: evidenceDesc.trim(),
          severity: evidenceSeverity,
          metadata: {},
        }),
      });
      toast.success('Доказот е додаден');
      setEvidenceTitle('');
      setEvidenceDesc('');
      setShowAddEvidence(false);
      fetchDetail();
    } catch {
      toast.error('Грешка при додавање на доказ');
    } finally {
      setAddingEvidence(false);
    }
  };

  const addNote = async () => {
    if (!noteContent.trim()) return;
    try {
      setAddingNote(true);
      await apiFetch(`/api/corruption/investigations/cases/${caseId}/notes`, {
        method: 'POST',
        body: JSON.stringify({ content: noteContent.trim(), author: noteAuthor.trim() || 'Admin' }),
      });
      toast.success('Белешката е додадена');
      setNoteContent('');
      setNoteAuthor('');
      fetchDetail();
    } catch {
      toast.error('Грешка при додавање на белешка');
    } finally {
      setAddingNote(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="p-6 text-center text-muted-foreground">Грешка при вчитување</div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Case Header */}
      <div className="flex flex-col gap-3">
        <h3 className="text-lg font-semibold">#{detail.id} — {detail.title}</h3>
        {detail.description && <p className="text-sm text-muted-foreground">{detail.description}</p>}
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Статус:</span>
          <Select value={detail.status} onValueChange={handleStatusChange} disabled={updatingStatus}>
            <SelectTrigger className="w-[150px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(CASE_STATUS_LABELS).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Приоритет:</span>
          <Select value={detail.priority} onValueChange={handlePriorityChange} disabled={updatingPriority}>
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(PRIORITY_LABELS).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">Доделена на:</span>
          <Input
            className="w-[160px] h-8 text-xs"
            placeholder="Аналитичар"
            value={assignedInput}
            onChange={(e) => setAssignedInput(e.target.value)}
          />
          <Button variant="outline" size="sm" className="h-8" onClick={handleAssignedChange} disabled={updatingAssigned}>
            Зачувај
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* LEFT COLUMN */}
        <div className="space-y-4">
          {/* Attached Tenders */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <FileText className="w-4 h-4" />
                Прикачени Тендери ({detail.tenders?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {detail.tenders && detail.tenders.length > 0 ? (
                <div className="space-y-1">
                  {detail.tenders.map((t, i) => (
                    <div key={i} className="flex items-center justify-between text-sm py-1 border-b last:border-b-0">
                      <div>
                        <span className="font-mono text-xs">{t.tender_id}</span>
                        {t.title && <span className="ml-2 text-muted-foreground truncate">{t.title}</span>}
                      </div>
                      <Badge variant="outline" className="text-[10px]">{t.role}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">Нема прикачени тендери</p>
              )}
              <div className="flex items-center gap-2 pt-2">
                <Input
                  className="h-8 text-xs flex-1"
                  placeholder="Внеси tender_id (пр. 12345/2024)"
                  value={addTenderInput}
                  onChange={(e) => setAddTenderInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addTender()}
                />
                <Button variant="outline" size="sm" className="h-8" onClick={addTender} disabled={addingTender}>
                  <Plus className="w-3 h-3 mr-1" /> Додади
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Attached Entities */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Users className="w-4 h-4" />
                Ентитети ({detail.entities?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {detail.entities && detail.entities.length > 0 ? (
                <div className="space-y-1">
                  {detail.entities.map((e, i) => (
                    <div key={i} className="flex items-center justify-between text-sm py-1 border-b last:border-b-0">
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="text-[10px]">{e.entity_type}</Badge>
                        <span>{e.entity_name}</span>
                      </div>
                      <Badge variant="outline" className="text-[10px]">{e.role}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">Нема прикачени ентитети</p>
              )}
              {!showAddEntity ? (
                <Button variant="outline" size="sm" className="h-8 w-full" onClick={() => setShowAddEntity(true)}>
                  <Plus className="w-3 h-3 mr-1" /> Додади ентитет
                </Button>
              ) : (
                <div className="space-y-2 pt-2 border-t">
                  <Input
                    className="h-8 text-xs"
                    placeholder="Име на ентитетот"
                    value={entityName}
                    onChange={(e) => setEntityName(e.target.value)}
                  />
                  <Select value={entityType} onValueChange={setEntityType}>
                    <SelectTrigger className="h-8 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="company">Компанија</SelectItem>
                      <SelectItem value="person">Лице</SelectItem>
                      <SelectItem value="institution">Институција</SelectItem>
                    </SelectContent>
                  </Select>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="h-8 flex-1" onClick={() => setShowAddEntity(false)}>Откажи</Button>
                    <Button size="sm" className="h-8 flex-1" onClick={addEntity} disabled={addingEntity}>
                      {addingEntity ? 'Додава...' : 'Додади'}
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Evidence */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Scale className="w-4 h-4" />
                Докази ({detail.evidence?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {detail.evidence && detail.evidence.length > 0 ? (
                <div className="space-y-2">
                  {detail.evidence.map((ev) => (
                    <div key={ev.id} className="text-sm p-2 rounded border bg-background">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{ev.title}</span>
                        {severityBadge(ev.severity)}
                      </div>
                      {ev.description && <p className="text-xs text-muted-foreground mt-1">{ev.description}</p>}
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-[10px]">{ev.evidence_type}</Badge>
                        <Badge variant="outline" className="text-[10px]">{ev.source_module}</Badge>
                        <span className="text-[10px] text-muted-foreground ml-auto">{formatDateTime(ev.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">Нема додадени докази</p>
              )}
              {!showAddEvidence ? (
                <Button variant="outline" size="sm" className="h-8 w-full" onClick={() => setShowAddEvidence(true)}>
                  <Plus className="w-3 h-3 mr-1" /> Додади доказ
                </Button>
              ) : (
                <div className="space-y-2 pt-2 border-t">
                  <Input className="h-8 text-xs" placeholder="Наслов на доказот" value={evidenceTitle} onChange={(e) => setEvidenceTitle(e.target.value)} />
                  <Textarea className="text-xs" placeholder="Опис" value={evidenceDesc} onChange={(e) => setEvidenceDesc(e.target.value)} rows={2} />
                  <div className="grid grid-cols-2 gap-2">
                    <Select value={evidenceType} onValueChange={setEvidenceType}>
                      <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Тип" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="document">Документ</SelectItem>
                        <SelectItem value="financial">Финансиски</SelectItem>
                        <SelectItem value="behavioral">Бихевиорален</SelectItem>
                        <SelectItem value="statistical">Статистички</SelectItem>
                        <SelectItem value="testimony">Сведочење</SelectItem>
                        <SelectItem value="other">Друго</SelectItem>
                      </SelectContent>
                    </Select>
                    <Select value={evidenceSeverity} onValueChange={setEvidenceSeverity}>
                      <SelectTrigger className="h-8 text-xs"><SelectValue placeholder="Сериозност" /></SelectTrigger>
                      <SelectContent>
                        {Object.entries(PRIORITY_LABELS).map(([k, v]) => (
                          <SelectItem key={k} value={k}>{v}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" className="h-8 flex-1" onClick={() => setShowAddEvidence(false)}>Откажи</Button>
                    <Button size="sm" className="h-8 flex-1" onClick={addEvidence} disabled={addingEvidence}>
                      {addingEvidence ? 'Додава...' : 'Додади'}
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* RIGHT COLUMN */}
        <div className="space-y-4">
          {/* Notes */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <StickyNote className="w-4 h-4" />
                Белешки ({detail.notes?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {detail.notes && detail.notes.length > 0 ? (
                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                  {detail.notes.map((n) => (
                    <div key={n.id} className="text-sm p-2 rounded border bg-background">
                      <p className="whitespace-pre-wrap">{n.content}</p>
                      <div className="flex items-center justify-between mt-1 text-[10px] text-muted-foreground">
                        <span className="font-medium">{n.author}</span>
                        <span>{formatDateTime(n.created_at)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">Нема белешки</p>
              )}
              <div className="space-y-2 pt-2 border-t">
                <Textarea className="text-xs" placeholder="Нова белешка..." value={noteContent} onChange={(e) => setNoteContent(e.target.value)} rows={2} />
                <div className="flex items-center gap-2">
                  <Input className="h-8 text-xs flex-1" placeholder="Автор (опционално)" value={noteAuthor} onChange={(e) => setNoteAuthor(e.target.value)} />
                  <Button size="sm" className="h-8" onClick={addNote} disabled={addingNote || !noteContent.trim()}>
                    <MessageSquare className="w-3 h-3 mr-1" />
                    {addingNote ? 'Додава...' : 'Додади'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Activity Timeline */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Активност
              </CardTitle>
            </CardHeader>
            <CardContent>
              {timeline.length > 0 ? (
                <div className="space-y-2 max-h-[350px] overflow-y-auto">
                  {timeline.map((entry) => (
                    <div key={entry.id} className="flex items-start gap-2 text-xs py-1.5 border-b last:border-b-0">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                      <div className="flex-1">
                        <p>{entry.action}</p>
                        {entry.details && <p className="text-muted-foreground">{entry.details}</p>}
                      </div>
                      <span className="text-muted-foreground whitespace-nowrap">{formatDateTime(entry.created_at)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">Нема активност</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ============================================================================================
// TAB 3: WHISTLEBLOWER TIPS
// ============================================================================================
function TipsTab() {
  const [tips, setTips] = useState<WhistleblowerTip[]>([]);
  const [tipStats, setTipStats] = useState<WhistleblowerStats | null>(null);
  const [openCases, setOpenCases] = useState<InvestigationCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [expandedTipId, setExpandedTipId] = useState<number | null>(null);

  const fetchTips = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams({ limit: '50', offset: '0' });
      if (statusFilter && statusFilter !== 'all') params.set('status', statusFilter);

      const [tipsData, statsData, casesData] = await Promise.allSettled([
        apiFetch<{ tips: WhistleblowerTip[] } | WhistleblowerTip[]>(`/api/whistleblower/admin/tips?${params}`),
        apiFetch<WhistleblowerStats>('/api/whistleblower/admin/stats'),
        apiFetch<{ cases: InvestigationCase[] } | InvestigationCase[]>(
          '/api/corruption/investigations/cases?limit=100&status=open'
        ),
      ]);

      if (tipsData.status === 'fulfilled') {
        const d = tipsData.value;
        setTips(Array.isArray(d) ? d : d.tips || []);
      }
      if (statsData.status === 'fulfilled') setTipStats(statsData.value);
      if (casesData.status === 'fulfilled') {
        const c = casesData.value;
        setOpenCases(Array.isArray(c) ? c : c.cases || []);
      }
    } catch {
      toast.error('Грешка при вчитување на пријави');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchTips();
  }, [fetchTips]);

  return (
    <div className="space-y-4 mt-4">
      {/* Stats Row */}
      {tipStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Вкупно Пријави</CardTitle>
              <Megaphone className="w-4 h-4 text-blue-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{tipStats.total_tips}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Оваа Недела</CardTitle>
              <Clock className="w-4 h-4 text-green-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{tipStats.tips_this_week}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Просечен Скор</CardTitle>
              <TrendingUp className="w-4 h-4 text-purple-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {tipStats.avg_triage_score != null ? tipStats.avg_triage_score.toFixed(1) : 'Н/Д'}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Во Преглед</CardTitle>
              <Search className="w-4 h-4 text-orange-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-600">{tipStats.by_status?.under_review || 0}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="Филтер статус" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Сите статуси</SelectItem>
            {Object.entries(TIP_STATUS_LABELS).map(([k, v]) => (
              <SelectItem key={k} value={k}>{v}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button variant="outline" size="sm" onClick={fetchTips}>
          <RefreshCw className="w-4 h-4 mr-1" /> Освежи
        </Button>
      </div>

      {/* Tips Table */}
      {loading ? (
        <Card>
          <CardContent className="pt-6 space-y-3">
            {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
          </CardContent>
        </Card>
      ) : tips.length === 0 ? (
        <Card>
          <CardContent className="py-16">
            <div className="flex flex-col items-center text-muted-foreground">
              <Megaphone className="w-12 h-12 mb-3" />
              <p className="font-medium">Нема пријави</p>
              <p className="text-sm">Моментално нема пријави од укажувачи</p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-12">ID</TableHead>
                <TableHead>Категорија</TableHead>
                <TableHead className="text-center w-24">Скор</TableHead>
                <TableHead className="text-center w-24">Итност</TableHead>
                <TableHead className="w-28">Статус</TableHead>
                <TableHead className="w-28">Поднесена</TableHead>
                <TableHead className="w-10"></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tips.map((tip) => (
                <TipRow
                  key={tip.id}
                  tip={tip}
                  isExpanded={expandedTipId === tip.id}
                  onToggle={() => setExpandedTipId(expandedTipId === tip.id ? null : tip.id)}
                  openCases={openCases}
                  onRefresh={fetchTips}
                />
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tip Row + Expandable Detail
// ---------------------------------------------------------------------------
function TipRow({
  tip,
  isExpanded,
  onToggle,
  openCases,
  onRefresh,
}: {
  tip: WhistleblowerTip;
  isExpanded: boolean;
  onToggle: () => void;
  openCases: InvestigationCase[];
  onRefresh: () => void;
}) {
  return (
    <>
      <TableRow className="cursor-pointer hover:bg-muted/50" onClick={onToggle}>
        <TableCell className="font-mono text-xs">#{tip.id}</TableCell>
        <TableCell>
          <Badge variant="secondary">{TIP_CATEGORY_LABELS[tip.category] || tip.category}</Badge>
        </TableCell>
        <TableCell className="text-center">
          {tip.triage_score != null ? (
            <span className={`font-bold ${tip.triage_score >= 7 ? 'text-red-600' : tip.triage_score >= 4 ? 'text-orange-600' : 'text-green-600'}`}>
              {tip.triage_score.toFixed(1)}
            </span>
          ) : (
            <span className="text-muted-foreground">-</span>
          )}
        </TableCell>
        <TableCell className="text-center">{priorityBadge(tip.urgency)}</TableCell>
        <TableCell>
          <Badge variant={TIP_STATUS_VARIANTS[tip.status] || 'outline'}>
            {TIP_STATUS_LABELS[tip.status] || tip.status}
          </Badge>
        </TableCell>
        <TableCell className="text-xs">{formatDate(tip.submitted_at)}</TableCell>
        <TableCell>
          {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </TableCell>
      </TableRow>
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={7} className="p-0 bg-muted/30">
            <TipDetail tip={tip} openCases={openCases} onRefresh={onRefresh} />
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Tip Detail Panel
// ---------------------------------------------------------------------------
function TipDetail({
  tip,
  openCases,
  onRefresh,
}: {
  tip: WhistleblowerTip;
  openCases: InvestigationCase[];
  onRefresh: () => void;
}) {
  const [analystNote, setAnalystNote] = useState(tip.analyst_note || '');
  const [updatingNote, setUpdatingNote] = useState(false);
  const [updatingStatus, setUpdatingStatus] = useState(false);
  const [linkingCase, setLinkingCase] = useState(false);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');

  const updateTip = async (body: Record<string, string | null>) => {
    await apiFetch(`/api/whistleblower/admin/tips/${tip.id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    });
    onRefresh();
  };

  const handleStatusChange = async (status: string) => {
    try {
      setUpdatingStatus(true);
      await updateTip({ status });
      toast.success(`Статус променет: ${TIP_STATUS_LABELS[status]}`);
    } catch {
      toast.error('Грешка при промена на статус');
    } finally {
      setUpdatingStatus(false);
    }
  };

  const saveAnalystNote = async () => {
    try {
      setUpdatingNote(true);
      await updateTip({ analyst_note: analystNote.trim() || null });
      toast.success('Белешката е зачувана');
    } catch {
      toast.error('Грешка при зачувување на белешка');
    } finally {
      setUpdatingNote(false);
    }
  };

  const linkToCase = async () => {
    if (!selectedCaseId) return;
    try {
      setLinkingCase(true);
      await apiFetch(`/api/whistleblower/admin/tips/${tip.id}/link-case`, {
        method: 'POST',
        body: JSON.stringify({ case_id: parseInt(selectedCaseId, 10) }),
      });
      toast.success('Пријавата е поврзана со истрагата');
      setSelectedCaseId('');
      onRefresh();
    } catch {
      toast.error('Грешка при поврзување');
    } finally {
      setLinkingCase(false);
    }
  };

  return (
    <div className="p-6 space-y-4">
      {/* Description */}
      <div>
        <h4 className="text-sm font-medium mb-1">Опис на пријавата</h4>
        <p className="text-sm bg-background rounded border p-3 whitespace-pre-wrap">{tip.description || 'Нема опис'}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Extracted Entities */}
        {tip.extracted_entities && tip.extracted_entities.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-1">Извлечени Ентитети</h4>
            <div className="flex flex-wrap gap-1">
              {tip.extracted_entities.map((e, i) => (
                <Badge key={i} variant="secondary" className="text-xs">
                  {e.type}: {e.name}
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Matched Tenders */}
        {tip.matched_tenders && tip.matched_tenders.length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-1">Совпаднати Тендери</h4>
            <div className="space-y-1">
              {tip.matched_tenders.map((t, i) => (
                <div key={i} className="text-xs font-mono">
                  <a href={tenderUrl(t.tender_id)} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    {t.tender_id}
                  </a>
                  {t.title && <span className="ml-1 text-muted-foreground">{t.title}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Triage Details */}
        {tip.triage_details && Object.keys(tip.triage_details).length > 0 && (
          <div>
            <h4 className="text-sm font-medium mb-1">Детали за Тријажа</h4>
            <pre className="text-[10px] bg-background border rounded p-2 overflow-auto max-h-[120px]">
              {JSON.stringify(tip.triage_details, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-end gap-4 pt-2 border-t">
        {/* Change Status */}
        <div className="space-y-1">
          <label className="text-xs font-medium">Промени статус</label>
          <Select value={tip.status} onValueChange={handleStatusChange} disabled={updatingStatus}>
            <SelectTrigger className="w-[160px] h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(TIP_STATUS_LABELS).map(([k, v]) => (
                <SelectItem key={k} value={k}>{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Link to Case */}
        <div className="space-y-1">
          <label className="text-xs font-medium">Поврзи со истрага</label>
          <div className="flex items-center gap-2">
            <Select value={selectedCaseId} onValueChange={setSelectedCaseId}>
              <SelectTrigger className="w-[220px] h-8 text-xs">
                <SelectValue placeholder="Избери случај..." />
              </SelectTrigger>
              <SelectContent>
                {openCases.map((c) => (
                  <SelectItem key={c.id} value={String(c.id)}>
                    #{c.id} — {c.title}
                  </SelectItem>
                ))}
                {openCases.length === 0 && (
                  <SelectItem value="_none" disabled>Нема отворени случаи</SelectItem>
                )}
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" className="h-8" onClick={linkToCase} disabled={linkingCase || !selectedCaseId}>
              <Link2 className="w-3 h-3 mr-1" />
              {linkingCase ? 'Поврзува...' : 'Поврзи'}
            </Button>
          </div>
        </div>

        {tip.linked_case_id && (
          <div className="text-xs text-muted-foreground flex items-center gap-1">
            <Link2 className="w-3 h-3" />
            Поврзана со случај #{tip.linked_case_id}
          </div>
        )}
      </div>

      {/* Analyst Note */}
      <div className="space-y-2 pt-2 border-t">
        <label className="text-xs font-medium">Белешка на аналитичар</label>
        <Textarea
          className="text-xs"
          placeholder="Додади белешка за оваа пријава..."
          value={analystNote}
          onChange={(e) => setAnalystNote(e.target.value)}
          rows={2}
        />
        <div className="flex justify-end">
          <Button variant="outline" size="sm" className="h-8" onClick={saveAnalystNote} disabled={updatingNote}>
            <MessageSquare className="w-3 h-3 mr-1" />
            {updatingNote ? 'Зачувува...' : 'Зачувај белешка'}
          </Button>
        </div>
      </div>
    </div>
  );
}
