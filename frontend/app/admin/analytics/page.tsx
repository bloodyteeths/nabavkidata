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
  activeUsers: Array<{
    id: string;
    name: string;
    email: string;
    logins: number;
    lastActive: string;
  }>;
  categoryStats: Array<{ category: string; count: number; percentage: number }>;
  systemStats: {
    totalViews: number;
    avgSessionDuration: number;
    bounceRate: number;
    activeUsers24h: number;
  };
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

      const response = await fetch(
        `/api/admin/analytics?range=${timeRange}`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
          },
        }
      );

      if (response.ok) {
        const data = await response.json();
        setAnalytics(data);
      }
    } catch (error) {
      console.error('Error fetching analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleExportData = async (type: string) => {
    try {
      const response = await fetch(`/api/admin/analytics/export?type=${type}&range=${timeRange}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${type}-analytics-${new Date().toISOString()}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Error exporting data:', error);
      toast.error('Грешка при експорт на податоците');
    }
  };

  // Mock data for demonstration
  const userGrowthData = [
    { date: '01.01', users: 120, newUsers: 15 },
    { date: '08.01', users: 135, newUsers: 20 },
    { date: '15.01', users: 155, newUsers: 18 },
    { date: '22.01', users: 173, newUsers: 22 },
    { date: '29.01', users: 195, newUsers: 25 },
  ];

  const revenueData = [
    { month: 'Јан', revenue: 4500, subscriptions: 45 },
    { month: 'Фев', revenue: 5200, subscriptions: 52 },
    { month: 'Мар', revenue: 6100, subscriptions: 61 },
    { month: 'Апр', revenue: 7300, subscriptions: 73 },
    { month: 'Мај', revenue: 8900, subscriptions: 89 },
    { month: 'Јун', revenue: 10500, subscriptions: 105 },
  ];

  const categoryData = [
    { category: 'Градежништво', count: 450, color: '#3b82f6' },
    { category: 'ИТ', count: 320, color: '#10b981' },
    { category: 'Услуги', count: 280, color: '#f59e0b' },
    { category: 'Снабдување', count: 220, color: '#8b5cf6' },
    { category: 'Останато', count: 180, color: '#94a3b8' },
  ];

  const activeUsersData = [
    {
      id: '1',
      name: 'Марко Петровски',
      email: 'marko@example.com',
      logins: 145,
      lastActive: '2024-01-15T10:30:00',
    },
    {
      id: '2',
      name: 'Ана Стојановска',
      email: 'ana@example.com',
      logins: 128,
      lastActive: '2024-01-15T09:15:00',
    },
    {
      id: '3',
      name: 'Петар Николовски',
      email: 'petar@example.com',
      logins: 112,
      lastActive: '2024-01-14T16:45:00',
    },
    {
      id: '4',
      name: 'Елена Димитриевска',
      email: 'elena@example.com',
      logins: 98,
      lastActive: '2024-01-14T14:20:00',
    },
    {
      id: '5',
      name: 'Владимир Георгиевски',
      email: 'vladimir@example.com',
      logins: 87,
      lastActive: '2024-01-13T11:30:00',
    },
  ];

  const systemStats = {
    totalViews: 45678,
    avgSessionDuration: 342,
    bounceRate: 32.5,
    activeUsers24h: 156,
  };

  if (loading) return <div className="flex items-center justify-center min-h-screen"><div className="text-center"><div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div><p className="mt-4 text-muted-foreground">Се вчитува...</p></div></div>;

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
          { label: 'Вкупни прегледи', value: systemStats.totalViews.toLocaleString(), icon: Activity, color: 'text-blue-600' },
          { label: 'Просечна сесија', value: `${Math.floor(systemStats.avgSessionDuration / 60)}м ${systemStats.avgSessionDuration % 60}с`, icon: TrendingUp, color: 'text-green-600' },
          { label: 'Bounce Rate', value: `${systemStats.bounceRate}%`, icon: DollarSign, color: 'text-yellow-600' },
          { label: 'Активни корисници (24ч)', value: systemStats.activeUsers24h, icon: Users, color: 'text-purple-600' },
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
              <AreaChart data={userGrowthData}>
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
              <BarChart data={revenueData}>
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
                  data={categoryData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => `${entry.category}: ${entry.count}`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="count"
                >
                  {categoryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Most Active Users */}
        <Card>
          <CardHeader>
            <CardTitle>Најактивни корисници</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Корисник</TableHead>
                  <TableHead>Најави</TableHead>
                  <TableHead>Последна активност</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {activeUsersData.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{user.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {user.email}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">{user.logins}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(user.lastActive).toLocaleString('mk-MK')}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
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
