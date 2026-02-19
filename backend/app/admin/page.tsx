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
import { formatDateTime } from '@/lib/utils';

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

// Backend response format (snake_case)
interface BackendStats {
  total_users: number;
  active_users: number;
  verified_users: number;
  total_tenders: number;
  open_tenders: number;
  total_subscriptions: number;
  active_subscriptions: number;
  monthly_revenue_mkd: string;
  monthly_revenue_eur: string;
  total_queries_today: number;
  total_queries_month: number;
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

interface ActivityItem {
  id: string;
  type: string;
  user: string;
  action: string;
  timestamp: string;
}

interface ChartDataPoint {
  month: string;
  users?: number;
  revenue?: number;
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
  const [userGrowthData, setUserGrowthData] = useState<ChartDataPoint[]>([]);
  const [revenueData, setRevenueData] = useState<ChartDataPoint[]>([]);
  const [subscriptionDistribution, setSubscriptionDistribution] = useState<Array<{ name: string; value: number; color: string }>>([]);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);

      const authToken = localStorage.getItem('auth_token');
      const headers = { Authorization: `Bearer ${authToken}` };

      // Fetch dashboard stats
      const statsResponse = await fetch('/api/admin/dashboard', { headers });

      if (statsResponse.ok) {
        const backendStats: BackendStats = await statsResponse.json();

        // Calculate growth from analytics data (will fetch next)
        setStats({
          totalUsers: backendStats.total_users || 0,
          activeSubscriptions: backendStats.active_subscriptions || 0,
          totalRevenue: parseFloat(backendStats.monthly_revenue_eur) || 0,
          totalTenders: backendStats.total_tenders || 0,
          userGrowth: 0, // Will be calculated from analytics
          revenueGrowth: 0,
          subscriptionGrowth: 0,
          tenderGrowth: 0,
        });
      } else {
        toast.error('Failed to fetch dashboard stats');
      }

      // Fetch analytics for charts and trends
      const analyticsResponse = await fetch('/api/admin/analytics', { headers });

      if (analyticsResponse.ok) {
        const analytics: BackendAnalytics = await analyticsResponse.json();

        // Process user growth data for chart (last 6 months)
        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'Maj', 'Jun', 'Jul', 'Avg', 'Sep', 'Okt', 'Nov', 'Dec'];
        const userGrowthEntries = Object.entries(analytics.users_growth || {}).slice(-6);
        const userChartData = userGrowthEntries.map(([date, count]) => {
          const monthIndex = new Date(date).getMonth();
          return { month: monthNames[monthIndex], users: count };
        });
        setUserGrowthData(userChartData);

        // Calculate user growth percentage
        if (userGrowthEntries.length >= 2) {
          const prev = userGrowthEntries[userGrowthEntries.length - 2][1];
          const curr = userGrowthEntries[userGrowthEntries.length - 1][1];
          const growth = prev > 0 ? ((curr - prev) / prev * 100) : 0;
          setStats(s => ({ ...s, userGrowth: Math.round(growth) }));
        }

        // Process revenue data for chart (last 6 months)
        const revenueEntries = Object.entries(analytics.revenue_trend || {}).slice(-6);
        const revenueChartData = revenueEntries.map(([month, revenue]) => {
          const monthIndex = parseInt(month.split('-')[1]) - 1;
          return { month: monthNames[monthIndex], revenue: revenue };
        });
        setRevenueData(revenueChartData);

        // Calculate revenue growth percentage
        if (revenueEntries.length >= 2) {
          const prev = revenueEntries[revenueEntries.length - 2][1];
          const curr = revenueEntries[revenueEntries.length - 1][1];
          const growth = prev > 0 ? ((curr - prev) / prev * 100) : 0;
          setStats(s => ({ ...s, revenueGrowth: Math.round(growth) }));
        }

        // Process subscription distribution
        const subColors: Record<string, string> = {
          free: '#94a3b8',
          basic: '#3b82f6',
          premium: '#a855f7',
          enterprise: '#eab308',
          admin: '#ef4444',
        };
        const subDist = Object.entries(analytics.subscription_distribution || {}).map(([name, value]) => ({
          name: name.charAt(0).toUpperCase() + name.slice(1),
          value,
          color: subColors[name.toLowerCase()] || '#94a3b8',
        }));
        setSubscriptionDistribution(subDist);
      } else {
        toast.error('Failed to fetch analytics');
      }

      // Fetch recent activity from audit logs
      const activityResponse = await fetch('/api/admin/logs?limit=10', { headers });

      if (activityResponse.ok) {
        const activityData = await activityResponse.json();
        const activities = (activityData.logs || []).map((log: any, index: number) => ({
          id: log.audit_id || `activity-${index}`,
          type: log.action?.includes('user') ? 'user' : log.action?.includes('subscription') ? 'subscription' : 'tender',
          user: log.user_email || 'System',
          action: log.action,
          timestamp: log.created_at,
        }));
        setRecentActivity(activities);
      }
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      toast.error('Error loading dashboard');
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerScraper = async () => {
    try {
      const response = await fetch('/api/admin/scraper/trigger', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      if (response.ok) {
        toast.success('Scraper triggered successfully');
      } else {
        toast.error('Failed to trigger scraper');
      }
    } catch (error) {
      console.error('Error triggering scraper:', error);
      toast.error('Failed to trigger scraper');
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
          <p className="mt-4 text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Admin Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Overview of system metrics and activity
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => window.location.reload()}>
            <Activity className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={handleTriggerScraper}>
            <PlayCircle className="w-4 h-4 mr-2" />
            Trigger Scraper
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          label="Total Users"
          value={stats.totalUsers}
          icon={Users}
          trend={{
            value: stats.userGrowth,
            isPositive: stats.userGrowth > 0,
          }}
        />
        <StatCard
          label="Active Subscriptions"
          value={stats.activeSubscriptions}
          icon={CreditCard}
          trend={{
            value: stats.subscriptionGrowth,
            isPositive: stats.subscriptionGrowth > 0,
          }}
        />
        <StatCard
          label="Total Revenue"
          value={`€${stats.totalRevenue.toLocaleString()}`}
          icon={DollarSign}
          trend={{
            value: stats.revenueGrowth,
            isPositive: stats.revenueGrowth > 0,
          }}
        />
        <StatCard
          label="Total Tenders"
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
            <CardTitle>User Growth</CardTitle>
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
                  name="Users"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Revenue Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Revenue</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={revenueData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="month" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="revenue" fill="#10b981" name="Revenue (€)" />
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
            <CardTitle>Subscription Distribution</CardTitle>
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
            <CardTitle>Recent Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {recentActivity.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">
                  No recent activity
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
                        {formatDateTime(activity.timestamp, { dateStyle: 'medium', timeStyle: 'short' })}
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
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Button
              variant="outline"
              className="h-auto flex-col py-6"
              onClick={() => (window.location.href = '/admin/users')}
            >
              <Users className="w-8 h-8 mb-2" />
              <span className="font-semibold">Manage Users</span>
              <span className="text-xs text-muted-foreground">
                View and edit users
              </span>
            </Button>
            <Button
              variant="outline"
              className="h-auto flex-col py-6"
              onClick={() => (window.location.href = '/admin/logs')}
            >
              <Database className="w-8 h-8 mb-2" />
              <span className="font-semibold">View Logs</span>
              <span className="text-xs text-muted-foreground">
                System logs and activity
              </span>
            </Button>
            <Button
              variant="outline"
              className="h-auto flex-col py-6"
              onClick={() => (window.location.href = '/admin/analytics')}
            >
              <Settings className="w-8 h-8 mb-2" />
              <span className="font-semibold">Analytics</span>
              <span className="text-xs text-muted-foreground">
                Detailed statistics
              </span>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
