'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import { Badge } from '@/components/ui/badge';
import {
  Search,
  Download,
  RefreshCw,
  AlertCircle,
  AlertTriangle,
  Info,
} from 'lucide-react';
import { toast } from "sonner";
import { formatDateTime } from '@/lib/utils';

interface LogEntry {
  id: string;
  level: 'error' | 'warning' | 'info';
  message: string;
  user: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

// Backend response format
interface BackendLogEntry {
  audit_id: string;
  user_id: string | null;
  user_email: string | null;
  action: string;
  details: Record<string, any>;
  ip_address: string | null;
  created_at: string;
}

export default function AdminLogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filteredLogs, setFilteredLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const [filters, setFilters] = useState({
    level: 'all',
    search: '',
    dateFrom: '',
    dateTo: '',
  });

  const [pagination, setPagination] = useState({
    page: 1,
    limit: 50,
    total: 0,
  });

  useEffect(() => {
    fetchLogs();
  }, [pagination.page, filters.dateFrom, filters.dateTo]);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchLogs();
      }, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh]);

  useEffect(() => {
    applyFilters();
  }, [logs, filters]);

  const fetchLogs = async () => {
    try {
      setLoading(true);

      // Convert page to skip for backend
      const skip = (pagination.page - 1) * pagination.limit;
      const params = new URLSearchParams({
        skip: skip.toString(),
        limit: pagination.limit.toString(),
      });

      // Add date range filters if provided
      if (filters.dateFrom) {
        const startDate = new Date(filters.dateFrom);
        startDate.setHours(0, 0, 0, 0);
        params.append('start_date', startDate.toISOString());
      }

      if (filters.dateTo) {
        const endDate = new Date(filters.dateTo);
        endDate.setHours(23, 59, 59, 999);
        params.append('end_date', endDate.toISOString());
      }

      const response = await fetch(`/api/admin/logs?${params}`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      if (response.ok) {
        const data = await response.json();
        // Map backend format to frontend format
        const mappedLogs: LogEntry[] = (data.logs || []).map((log: BackendLogEntry) => {
          // Improved level inference based on action
          let level: 'error' | 'warning' | 'info' = 'info';
          const action = log.action.toLowerCase();

          // Error level triggers
          if (action.includes('error') || action.includes('failed') || action.includes('delete') ||
              action.includes('reject') || action.includes('blocked')) {
            level = 'error';
          }
          // Warning level triggers
          else if (action.includes('warning') || action.includes('ban') || action.includes('suspend') ||
                   action.includes('alert') || action.includes('exceed')) {
            level = 'warning';
          }

          return {
            id: log.audit_id,
            level,
            message: log.action,
            user: log.user_email || 'System',
            timestamp: log.created_at,
            metadata: log.details,
          };
        });
        setLogs(mappedLogs);
        setPagination((prev) => ({ ...prev, total: data.total || 0 }));
      } else {
        toast.error('Failed to fetch logs');
      }
    } catch (error) {
      console.error('Error fetching logs:', error);
      toast.error('Error loading logs');
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = [...logs];

    // Apply level filter
    if (filters.level !== 'all') {
      filtered = filtered.filter((log) => log.level === filters.level);
    }

    // Apply search filter
    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter(
        (log) =>
          log.message.toLowerCase().includes(searchLower) ||
          log.user.toLowerCase().includes(searchLower)
      );
    }

    setFilteredLogs(filtered);
  };

  const handleExport = async () => {
    try {
      const response = await fetch('/api/admin/logs/export', {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token')}`,
        },
      });

      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `logs-${new Date().toISOString()}.csv`;
        a.click();
        window.URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error('Error exporting logs:', error);
      toast.error('Error exporting logs');
    }
  };

  const getLevelBadge = (level: string) => {
    const config = {
      error: { color: 'bg-red-600 text-white', icon: AlertCircle, label: 'Error' },
      warning: { color: 'bg-yellow-500 text-white', icon: AlertTriangle, label: 'Warning' },
      info: { color: 'bg-blue-600 text-white', icon: Info, label: 'Info' },
    };

    const { color, icon: Icon, label } = config[level as keyof typeof config] || config.info;

    return (
      <Badge className={`${color} flex items-center gap-1`}>
        <Icon className="w-3 h-3" />
        {label}
      </Badge>
    );
  };

  const totalPages = Math.ceil(pagination.total / pagination.limit);

  if (loading && logs.length === 0) {
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">System Logs</h1>
          <p className="text-muted-foreground mt-1">Total {pagination.total} entries</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={autoRefresh ? 'bg-green-50' : ''}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? 'Auto-refresh ON' : 'Auto-refresh'}
          </Button>
          <Button variant="outline" onClick={handleExport}>
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
          <Button onClick={fetchLogs}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle>Filters</CardTitle></CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search logs..."
                className="pl-10"
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              />
            </div>
            <Select value={filters.level} onValueChange={(value) => setFilters({ ...filters, level: value })}>
              <SelectTrigger><SelectValue placeholder="Level" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Levels</SelectItem>
                <SelectItem value="error">Error</SelectItem>
                <SelectItem value="warning">Warning</SelectItem>
                <SelectItem value="info">Info</SelectItem>
              </SelectContent>
            </Select>
            <Input
              type="date"
              placeholder="From date"
              value={filters.dateFrom}
              onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })}
            />
            <Input
              type="date"
              placeholder="To date"
              value={filters.dateTo}
              onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="rounded-md border bg-white">
            <Table>
              <TableHeader>
                <TableRow className="bg-gray-50">
                  <TableHead className="w-[150px] text-gray-900 font-semibold">Time</TableHead>
                  <TableHead className="w-[120px] text-gray-900 font-semibold">Level</TableHead>
                  <TableHead className="w-[200px] text-gray-900 font-semibold">User</TableHead>
                  <TableHead className="text-gray-900 font-semibold">Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLogs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-8 text-gray-500">No logs</TableCell>
                  </TableRow>
                ) : (
                  filteredLogs.map((log) => (
                    <TableRow key={log.id} className="hover:bg-gray-50">
                      <TableCell className="font-mono text-sm text-gray-700">
                        {formatDateTime(log.timestamp, { dateStyle: 'medium', timeStyle: 'short' }, 'en-US')}
                      </TableCell>
                      <TableCell>{getLevelBadge(log.level)}</TableCell>
                      <TableCell className="font-medium text-gray-900">{log.user}</TableCell>
                      <TableCell>
                        <div>
                          <p className="text-sm text-gray-800">{log.message}</p>
                          {log.metadata && (
                            <details className="mt-1">
                              <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">Show details</summary>
                              <pre className="mt-2 text-xs bg-gray-100 text-gray-800 p-2 rounded overflow-x-auto">{JSON.stringify(log.metadata, null, 2)}</pre>
                            </details>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Page {pagination.page} of {totalPages || 1}</p>
        <div className="flex gap-2">
          <Button variant="outline" disabled={pagination.page === 1} onClick={() => setPagination({ ...pagination, page: pagination.page - 1 })}>Previous</Button>
          <Button variant="outline" disabled={pagination.page >= totalPages} onClick={() => setPagination({ ...pagination, page: pagination.page + 1 })}>Next</Button>
        </div>
      </div>
    </div>
  );
}
