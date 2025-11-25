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
  }, [pagination.page]);

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

      if (filters.level !== 'all') {
        params.append('action', filters.level);
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
          // Determine level based on action
          let level: 'error' | 'warning' | 'info' = 'info';
          if (log.action.includes('error') || log.action.includes('failed') || log.action.includes('delete')) {
            level = 'error';
          } else if (log.action.includes('warning') || log.action.includes('ban')) {
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
      }
    } catch (error) {
      console.error('Error fetching logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const applyFilters = () => {
    let filtered = [...logs];

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
      error: { color: 'bg-red-100 text-red-800', icon: AlertCircle, label: 'Error' },
      warning: { color: 'bg-yellow-100 text-yellow-800', icon: AlertTriangle, label: 'Warning' },
      info: { color: 'bg-blue-100 text-blue-800', icon: Info, label: 'Info' },
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
            <Input type="date" value={filters.dateFrom} onChange={(e) => setFilters({ ...filters, dateFrom: e.target.value })} />
            <Input type="date" value={filters.dateTo} onChange={(e) => setFilters({ ...filters, dateTo: e.target.value })} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[150px]">Time</TableHead>
                  <TableHead className="w-[120px]">Level</TableHead>
                  <TableHead className="w-[200px]">User</TableHead>
                  <TableHead>Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLogs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={4} className="text-center py-8">No logs</TableCell>
                  </TableRow>
                ) : (
                  filteredLogs.map((log) => (
                    <TableRow key={log.id}>
                      <TableCell className="font-mono text-sm">
                        {new Date(log.timestamp).toLocaleString('en-US')}
                      </TableCell>
                      <TableCell>{getLevelBadge(log.level)}</TableCell>
                      <TableCell className="font-medium">{log.user}</TableCell>
                      <TableCell>
                        <div>
                          <p className="text-sm">{log.message}</p>
                          {log.metadata && (
                            <details className="mt-1">
                              <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">Show details</summary>
                              <pre className="mt-2 text-xs bg-muted p-2 rounded overflow-x-auto">{JSON.stringify(log.metadata, null, 2)}</pre>
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
