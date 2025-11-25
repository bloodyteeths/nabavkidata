'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
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
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import { Download, TrendingUp, Users, DollarSign, Activity } from 'lucide-react';
import { toast } from "sonner";

interface AnalyticsData {
  userGrowth: Array<{ date: string; users: number; newUsers: number }>;
  revenue: Array<{ month: string; revenue: number; subscriptions: number }>;
  categoryStats: Array<{ category: string; count: number; color: string }>;
  systemStats: {
    totalQueriesToday: number;
    totalQueriesMonth: number;
    activeUsersToday: number;
    activeUsersWeek: number;
    activeUsersMonth: number;
  };
}

// Backend analytics response
interface BackendAnalytics {
  users_growth: Record<string, number>;
  revenue_trend: Record<string, number>;
  queries_trend: Record<string, number>;
  subscription_distribution: Record<string, number>;
  top_categories: Array<{ category: string; count: number }>;
  active_users_today: number;
  active_users_week: number;
  active_users_month: number;
}

// Backend stats from /api/analytics/tenders/stats
interface TenderStats {
  total_tenders: number;
  tenders_by_status: Record<string, number>;
  tenders_by_category: Record<string, number>;
  tenders_by_procedure_type: Record<string, number>;
  total_estimated_value_mkd: number | null;
  avg_estimated_value_mkd: number | null;
  tenders_last_7_days: number;
  tenders_last_30_days: number;
}

export default function AdminAnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('30d');

  useEffect(() => {
    fetchAnalytics();
  }, [timeRange]);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);

      const authToken = localStorage.getItem('auth_token');
      const headers = { Authorization: `Bearer ${authToken}` };

      // Fetch admin analytics
      const analyticsResponse = await fetch('/api/admin/analytics', { headers });

      if (!analyticsResponse.ok) {
        toast.error('Грешка при вчитување на аналитика');
        return;
      }

      const backendAnalytics: BackendAnalytics = await analyticsResponse.json();

      // Fetch tender stats from public analytics API
      const tenderStatsResponse = await fetch('/api/analytics/tenders/stats', { headers });
      const tenderStats: TenderStats = tenderStatsResponse.ok
        ? await tenderStatsResponse.json()
        : null;

      // Process user growth data
      const daysToShow = timeRange === '7d' ? 7 : timeRange === '30d' ? 30 : timeRange === '90d' ? 90 : 30;
      const userGrowthEntries = Object.entries(backendAnalytics.users_growth || {}).slice(-daysToShow);
      const userGrowthData = userGrowthEntries.map(([date, count], index) => {
        const prevCount = index > 0 ? userGrowthEntries[index - 1][1] : count;
        const newUsers = count - prevCount;
        return {
          date: new Date(date).toLocaleDateString('mk-MK', { month: '2-digit', day: '2-digit' }),
          users: count,
          newUsers: Math.max(0, newUsers),
        };
      });

      // Process revenue data (last 6 months)
      const monthNames = ['Јан', 'Фев', 'Мар', 'Апр', 'Мај', 'Јун', 'Јул', 'Авг', 'Сеп', 'Окт', 'Нов', 'Дек'];
      const revenueEntries = Object.entries(backendAnalytics.revenue_trend || {}).slice(-6);
      const revenueData = revenueEntries.map(([month, revenue]) => {
        const monthIndex = parseInt(month.split('-')[1]) - 1;
        // Get subscription count from distribution (approximate)
        const totalSubs = Object.values(backendAnalytics.subscription_distribution || {}).reduce((a, b) => a + b, 0);
        return {
          month: monthNames[monthIndex] || month,
          revenue: revenue,
          subscriptions: Math.round(totalSubs / 6), // Rough estimate
        };
      });

      // Process category data from tender stats
      const categoryColors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#06b6d4', '#ec4899', '#94a3b8'];
      const categoryData = tenderStats?.tenders_by_category
        ? Object.entries(tenderStats.tenders_by_category).slice(0, 8).map(([category, count], index) => ({
            category,
            count,
            color: categoryColors[index] || '#94a3b8',
          }))
        : backendAnalytics.top_categories.slice(0, 8).map((cat, index) => ({
            ...cat,
            color: categoryColors[index] || '#94a3b8',
          }));

      // System stats
      const systemStats = {
        totalQueriesToday: 0,
        totalQueriesMonth: 0,
        activeUsersToday: backendAnalytics.active_users_today || 0,
        activeUsersWeek: backendAnalytics.active_users_week || 0,
        activeUsersMonth: backendAnalytics.active_users_month || 0,
      };

      setAnalytics({
        userGrowth: userGrowthData,
        revenue: revenueData,
        categoryStats: categoryData,
        systemStats,
      });
    } catch (error) {
      console.error('Error fetching analytics:', error);
      toast.error('Грешка при вчитување на податоците');
    } finally {
      setLoading(false);
    }
  };

  const handleExportData = async (type: string) => {
    try {
      toast.info('Експортот ќе биде достапен наскоро');
      // Future implementation: export functionality
      // const response = await fetch(`/api/admin/analytics/export?type=${type}&range=${timeRange}`, {
      //   headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      // });
    } catch (error) {
      console.error('Error exporting data:', error);
      toast.error('Грешка при експорт на податоците');
    }
  };

  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="text-center"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div><p className="mt-4 text-muted-foreground">Се вчитува...</p></div></div>;

  if (!analytics) return <div className="flex items-center justify-center min-h-screen"><p className="text-muted-foreground">Нема податоци</p></div>;

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Аналитика</h1>
          <p className="text-muted-foreground mt-1">Детални статистики и метрики</p>
        </div>
        <Select value={timeRange} onValueChange={setTimeRange}><SelectTrigger className="w-[180px]"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="7d">Последни 7 дена</SelectItem><SelectItem value="30d">Последни 30 дена</SelectItem><SelectItem value="90d">Последни 90 дена</SelectItem><SelectItem value="1y">Последна година</SelectItem></SelectContent></Select>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {[
          { label: 'Активни корисници (денес)', value: analytics.systemStats.activeUsersToday, icon: Activity, color: 'text-blue-600' },
          { label: 'Активни корисници (недела)', value: analytics.systemStats.activeUsersWeek, icon: TrendingUp, color: 'text-green-600' },
          { label: 'Активни корисници (месец)', value: analytics.systemStats.activeUsersMonth, icon: Users, color: 'text-purple-600' },
          { label: 'Вкупно тендери', value: analytics.categoryStats.reduce((sum, cat) => sum + cat.count, 0).toLocaleString(), icon: DollarSign, color: 'text-yellow-600' },
        ].map((stat, i) => {
          const Icon = stat.icon;
          return <Card key={i}><CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-sm font-medium text-muted-foreground">{stat.label}</p><h3 className="text-2xl font-bold mt-2">{stat.value}</h3></div><Icon className={`w-8 h-8 ${stat.color}`} /></div></CardContent></Card>;
        })}
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* User Growth Chart */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Раст на корисници</CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleExportData('user-growth')}
            >
              <Download className="w-4 h-4 mr-2" />
              Експорт
            </Button>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={analytics.userGrowth}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Area
                  type="monotone"
                  dataKey="users"
                  stackId="1"
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  name="Вкупно корисници"
                />
                <Area
                  type="monotone"
                  dataKey="newUsers"
                  stackId="2"
                  stroke="#10b981"
                  fill="#10b981"
                  name="Нови корисници"
                />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Revenue Chart */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Приход и претплати</CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleExportData('revenue')}
            >
              <Download className="w-4 h-4 mr-2" />
              Експорт
            </Button>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={analytics.revenue}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis yAxisId="left" />
                <YAxis yAxisId="right" orientation="right" />
                <Tooltip />
                <Legend />
                <Bar
                  yAxisId="left"
                  dataKey="revenue"
                  fill="#10b981"
                  name="Приход (€)"
                />
                <Bar
                  yAxisId="right"
                  dataKey="subscriptions"
                  fill="#3b82f6"
                  name="Претплати"
                />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Category Distribution */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Популарни категории</CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleExportData('categories')}
            >
              <Download className="w-4 h-4 mr-2" />
              Експорт
            </Button>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={analytics.categoryStats}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => `${entry.category}: ${entry.count}`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="count"
                >
                  {analytics.categoryStats.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Top Categories List */}
        <Card>
          <CardHeader>
            <CardTitle>Најпопуларни категории</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {analytics.categoryStats.map((cat, index) => (
                <div key={index} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: cat.color }}></div>
                    <span className="text-sm font-medium">{cat.category}</span>
                  </div>
                  <span className="text-sm text-muted-foreground">{cat.count} тендери</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Експорт на податоци</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {['full-analytics', 'user-data', 'financial', 'tender-stats'].map((type) => (
              <Button key={type} variant="outline" onClick={() => handleExportData(type)}>
                <Download className="w-4 h-4 mr-2" />
                {type === 'full-analytics' ? 'Комплетна аналитика' : type === 'user-data' ? 'Податоци за корисници' : type === 'financial' ? 'Финансиски извештај' : 'Статистика за тендери'}
              </Button>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
