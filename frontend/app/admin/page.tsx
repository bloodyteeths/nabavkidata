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

// Backend response format (snake_case)
interface BackendStats {
  total_users: number;
  active_subscriptions: number;
  monthly_revenue_eur: string;
  total_tenders: number;
  verified_users: number;
  open_tenders: number;
}

interface ActivityItem {
  id: string;
  type: string;
  user: string;
  action: string;
  timestamp: string;
}

// Backend activity format
interface BackendActivity {
  type: string;
  description: string;
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
    { month: 'Jan', users: 120 },
    { month: 'Feb', users: 150 },
    { month: 'Mar', users: 180 },
    { month: 'Apr', users: 220 },
    { month: 'May', users: 280 },
    { month: 'Jun', users: 350 },
  ];

  const revenueData = [
    { month: 'Jan', revenue: 4500 },
    { month: 'Feb', revenue: 5200 },
    { month: 'Mar', revenue: 6100 },
    { month: 'Apr', revenue: 7300 },
    { month: 'May', revenue: 8900 },
    { month: 'Jun', revenue: 10500 },
  ];

  const subscriptionDistribution = [
    { name: 'Free', value: 400, color: '#94a3b8' },
    { name: 'Basic', value: 300, color: '#3b82f6' },
    { name: 'Premium', value: 200, color: '#a855f7' },
    { name: 'Enterprise', value: 100, color: '#eab308' },
  ];

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);

      // Fetch stats
      const statsResponse = await fetch('/api/admin/dashboard', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      if (statsResponse.ok) {
        const backendStats: BackendStats = await statsResponse.json();
        // Map snake_case backend response to camelCase frontend format
        setStats({
          totalUsers: backendStats.total_users || 0,
          activeSubscriptions: backendStats.active_subscriptions || 0,
          totalRevenue: parseFloat(backendStats.monthly_revenue_eur) || 0,
          totalTenders: backendStats.total_tenders || 0,
          userGrowth: 0,
          revenueGrowth: 0,
          subscriptionGrowth: 0,
          tenderGrowth: 0,
        });
      }

      // Fetch recent activity from audit logs
      const activityResponse = await fetch('/api/admin/logs?limit=10', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      if (activityResponse.ok) {
        const activityData = await activityResponse.json();
        // Map backend logs format to frontend activity format
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
                        {new Date(activity.timestamp).toLocaleString('en-US')}
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
