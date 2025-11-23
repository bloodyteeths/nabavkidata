'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import StatCard from '@/components/admin/StatCard';
import {
  Users,
  CreditCard,
  DollarSign,
  FileText,
  Activity,
  Settings,
  Database,
  PlayCircle,
} from 'lucide-react';
import { toast } from "sonner";
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
} from 'recharts';

interface DashboardStats {
  totalUsers: number;
  activeSubscriptions: number;
  totalRevenue: number;
  totalTenders: number;
  userGrowth: number;
  revenueGrowth: number;
  subscriptionGrowth: number;
  tenderGrowth: number;
}

interface ActivityItem {
  id: string;
  type: string;
  user: string;
  action: string;
  timestamp: string;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    totalUsers: 0,
    activeSubscriptions: 0,
    totalRevenue: 0,
    totalTenders: 0,
    userGrowth: 0,
    revenueGrowth: 0,
    subscriptionGrowth: 0,
    tenderGrowth: 0,
  });
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Mock data for charts
  const userGrowthData = [
    { month: 'Јан', users: 120 },
    { month: 'Фев', users: 150 },
    { month: 'Мар', users: 180 },
    { month: 'Апр', users: 220 },
    { month: 'Мај', users: 280 },
    { month: 'Јун', users: 350 },
  ];

  const revenueData = [
    { month: 'Јан', revenue: 4500 },
    { month: 'Фев', revenue: 5200 },
    { month: 'Мар', revenue: 6100 },
    { month: 'Апр', revenue: 7300 },
    { month: 'Мај', revenue: 8900 },
    { month: 'Јун', revenue: 10500 },
  ];

  const subscriptionDistribution = [
    { name: 'Бесплатен', value: 400, color: '#94a3b8' },
    { name: 'Основен', value: 300, color: '#3b82f6' },
    { name: 'Премиум', value: 200, color: '#a855f7' },
    { name: 'Корпоративен', value: 100, color: '#eab308' },
  ];

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);

      // Fetch stats
      const statsResponse = await fetch('/api/admin/stats', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (statsResponse.ok) {
        const statsData = await statsResponse.json();
        setStats(statsData);
      }

      // Fetch recent activity
      const activityResponse = await fetch('/api/admin/activity?limit=10', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (activityResponse.ok) {
        const activityData = await activityResponse.json();
        setRecentActivity(activityData);
      }
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerScraper = async () => {
    try {
      const response = await fetch('/api/admin/scraper/trigger', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });

      if (response.ok) {
        toast.success('Scraper успешно активиран');
      } else {
        toast.error('Грешка при активирање на scraper');
      }
    } catch (error) {
      console.error('Error triggering scraper:', error);
      toast.error('Грешка при активирање на scraper');
    }
  };

  const activityConfig: Record<string, { icon: any; color: string }> = {
    user: { icon: Users, color: 'bg-blue-100 text-blue-600' },
    subscription: { icon: CreditCard, color: 'bg-green-100 text-green-600' },
    tender: { icon: FileText, color: 'bg-purple-100 text-purple-600' },
    default: { icon: Activity, color: 'bg-gray-100 text-gray-600' },
  };

  const getActivityIcon = (type: string) => {
    const Icon = (activityConfig[type] || activityConfig.default).icon;
    return <Icon className="w-4 h-4" />;
  };

  const getActivityColor = (type: string) => (activityConfig[type] || activityConfig.default).color;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Се вчитува...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Админ Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Преглед на системски метрики и активности
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => window.location.reload()}>
            <Activity className="w-4 h-4 mr-2" />
            Освежи
          </Button>
          <Button onClick={handleTriggerScraper}>
            <PlayCircle className="w-4 h-4 mr-2" />
            Активирај Scraper
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          label="Вкупно корисници"
          value={stats.totalUsers}
          icon={Users}
          trend={{
            value: stats.userGrowth,
            isPositive: stats.userGrowth > 0,
          }}
        />
        <StatCard
          label="Активни претплати"
          value={stats.activeSubscriptions}
          icon={CreditCard}
          trend={{
            value: stats.subscriptionGrowth,
            isPositive: stats.subscriptionGrowth > 0,
          }}
        />
        <StatCard
          label="Вкупен приход"
          value={`€${stats.totalRevenue.toLocaleString()}`}
          icon={DollarSign}
          trend={{
            value: stats.revenueGrowth,
            isPositive: stats.revenueGrowth > 0,
          }}
        />
        <StatCard
          label="Вкупно тендери"
          value={stats.totalTenders}
          icon={FileText}
          trend={{
            value: stats.tenderGrowth,
            isPositive: stats.tenderGrowth > 0,
          }}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* User Growth Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Раст на корисници</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={userGrowthData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="users"
                  stroke="#3b82f6"
                  name="Корисници"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Revenue Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Приход</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={revenueData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="revenue" fill="#10b981" name="Приход (€)" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Subscription Distribution and Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Subscription Distribution */}
        <Card>
          <CardHeader>
            <CardTitle>Дистрибуција на претплати</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={subscriptionDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => `${entry.name}: ${entry.value}`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {subscriptionDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card>
          <CardHeader>
            <CardTitle>Скорешни активности</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentActivity.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  Нема скорешни активности
                </p>
              ) : (
                recentActivity.map((activity) => (
                  <div
                    key={activity.id}
                    className="flex items-start gap-3 pb-3 border-b last:border-0"
                  >
                    <div
                      className={`w-8 h-8 rounded-full flex items-center justify-center ${getActivityColor(
                        activity.type
                      )}`}
                    >
                      {getActivityIcon(activity.type)}
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{activity.action}</p>
                      <p className="text-xs text-muted-foreground">
                        {activity.user}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(activity.timestamp).toLocaleString('mk-MK')}
                      </p>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Брзи акции</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button
              variant="outline"
              className="h-auto flex-col py-6"
              onClick={() => (window.location.href = '/admin/users')}
            >
              <Users className="w-8 h-8 mb-2" />
              <span className="font-semibold">Управувај со корисници</span>
              <span className="text-xs text-muted-foreground">
                Прегледај и измени корисници
              </span>
            </Button>
            <Button
              variant="outline"
              className="h-auto flex-col py-6"
              onClick={() => (window.location.href = '/admin/logs')}
            >
              <Database className="w-8 h-8 mb-2" />
              <span className="font-semibold">Прегледај логови</span>
              <span className="text-xs text-muted-foreground">
                Систем логови и активности
              </span>
            </Button>
            <Button
              variant="outline"
              className="h-auto flex-col py-6"
              onClick={() => (window.location.href = '/admin/analytics')}
            >
              <Settings className="w-8 h-8 mb-2" />
              <span className="font-semibold">Аналитика</span>
              <span className="text-xs text-muted-foreground">
                Детални статистики
              </span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
