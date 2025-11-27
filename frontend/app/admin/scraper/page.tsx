'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { PlayCircle, StopCircle, RefreshCw, Clock, CheckCircle, XCircle, AlertCircle, Terminal, Database, FileText, Calendar, ScrollText, Loader2 } from 'lucide-react';
import { toast } from "sonner";
import { formatDateTime } from '@/lib/utils';

interface ScraperStatus {
  status: 'idle' | 'running' | 'completed' | 'failed';
  last_run: string | null;
  next_run: string | null;
  tenders_scraped: number;
}

// Backend response format
interface BackendScraperStatus {
  is_running: boolean;
  last_run: string | null;
  last_success: string | null;
  total_scraped: number;
  errors_count: number;
  next_scheduled_run: string | null;
}

interface ScrapingJob {
  job_id: string;
  started_at: string;
  completed_at: string | null;
  status: string;
  tenders_scraped: number;
  documents_scraped: number;
  errors_count: number;
  spider_name: string;
}

// Live status from EC2 server
interface LiveStatus {
  status: 'running' | 'idle';
  message: string;
  processes: { pid: string; command: string }[];
  log_tail: string[];
  log_file?: string;
  database_stats: {
    total_tenders: number;
    total_documents: number;
    downloaded_documents: number;
  };
  downloaded_files: number;
  timestamp: string;
}

// Scraper configuration
interface ScraperConfig {
  id: string;
  name: string;
  description: string;
  command: string;
  log_file: string;
  is_running: boolean;
}

// Cron job status
interface CronEntry {
  schedule: string;
  command: string;
  description: string;
}

interface LogFile {
  name: string;
  size: number;
  modified: string;
}

interface CronStatus {
  cron_entries: CronEntry[];
  log_files: LogFile[];
}

export default function AdminScraperPage() {
  const [status, setStatus] = useState<ScraperStatus>({
    status: 'idle',
    last_run: null,
    next_run: null,
    tenders_scraped: 0,
  });
  const [liveStatus, setLiveStatus] = useState<LiveStatus | null>(null);
  const [jobs, setJobs] = useState<ScrapingJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [scrapers, setScrapers] = useState<ScraperConfig[]>([]);
  const [cronStatus, setCronStatus] = useState<CronStatus | null>(null);
  const [selectedLog, setSelectedLog] = useState<string | null>(null);
  const [logContent, setLogContent] = useState<string[]>([]);
  const [loadingScrapers, setLoadingScrapers] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState('status');

  const fetchLiveStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/admin/scraper/live-status', {
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });
      if (res.ok) {
        const data: LiveStatus = await res.json();
        setLiveStatus(data);
        // Update main status based on live status
        setStatus(prev => ({
          ...prev,
          status: data.status === 'running' ? 'running' : prev.status,
          tenders_scraped: data.database_stats?.total_tenders || prev.tenders_scraped,
        }));
      }
    } catch (error) {
      console.error('Error fetching live status:', error);
    }
  }, []);

  const fetchScrapers = useCallback(async () => {
    try {
      const res = await fetch('/api/admin/scraper/scrapers', {
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });
      if (res.ok) {
        const data = await res.json();
        setScrapers(data.scrapers || []);
      }
    } catch (error) {
      console.error('Error fetching scrapers:', error);
    }
  }, []);

  const fetchCronStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/admin/scraper/cron-status', {
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });
      if (res.ok) {
        const data: CronStatus = await res.json();
        setCronStatus(data);
      }
    } catch (error) {
      console.error('Error fetching cron status:', error);
    }
  }, []);

  const fetchLogContent = async (logName: string) => {
    try {
      setSelectedLog(logName);
      const res = await fetch(`/api/admin/scraper/logs/${encodeURIComponent(logName)}?lines=200`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });
      if (res.ok) {
        const data = await res.json();
        setLogContent(data.content || []);
      }
    } catch (error) {
      console.error('Error fetching log content:', error);
      toast.error('Failed to fetch log content');
    }
  };

  const handleRunScraper = async (scraperId: string) => {
    setLoadingScrapers(prev => ({ ...prev, [scraperId]: true }));
    try {
      const res = await fetch(`/api/admin/scraper/run/${scraperId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });
      if (res.ok) {
        toast.success('Scraper started successfully');
        setTimeout(() => {
          fetchScrapers();
          fetchLiveStatus();
        }, 2000);
      } else {
        const data = await res.json();
        toast.error(data.detail || 'Failed to start scraper');
      }
    } catch (error) {
      console.error('Error starting scraper:', error);
      toast.error('Failed to start scraper');
    } finally {
      setLoadingScrapers(prev => ({ ...prev, [scraperId]: false }));
    }
  };

  const handleStopScraper = async (scraperId: string) => {
    setLoadingScrapers(prev => ({ ...prev, [scraperId]: true }));
    try {
      const res = await fetch(`/api/admin/scraper/stop/${scraperId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });
      if (res.ok) {
        toast.success('Scraper stopped successfully');
        setTimeout(() => {
          fetchScrapers();
          fetchLiveStatus();
        }, 2000);
      } else {
        const data = await res.json();
        toast.error(data.detail || 'Failed to stop scraper');
      }
    } catch (error) {
      console.error('Error stopping scraper:', error);
      toast.error('Failed to stop scraper');
    } finally {
      setLoadingScrapers(prev => ({ ...prev, [scraperId]: false }));
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchLiveStatus();
    fetchScrapers();
    fetchCronStatus();
  }, [fetchLiveStatus, fetchScrapers, fetchCronStatus]);

  // Auto-refresh when enabled
  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => {
      fetchLiveStatus();
      fetchScrapers();
    }, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [autoRefresh, fetchLiveStatus, fetchScrapers]);

  const fetchStatus = async () => {
    try {
      setLoading(true);

      const statusRes = await fetch('/api/admin/scraper/status', {
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });

      if (statusRes.ok) {
        const data: BackendScraperStatus = await statusRes.json();
        // Map backend format to frontend format
        let statusValue: 'idle' | 'running' | 'completed' | 'failed' = 'idle';
        if (data.is_running) {
          statusValue = 'running';
        } else if (data.last_success) {
          statusValue = 'completed';
        }

        setStatus({
          status: statusValue,
          last_run: data.last_run,
          next_run: data.next_scheduled_run,
          tenders_scraped: data.total_scraped,
        });
      }
    } catch (error) {
      console.error('Error fetching scraper status:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleTrigger = async () => {
    try {
      const response = await fetch('/api/admin/scraper/trigger', {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('auth_token')}` },
      });

      if (response.ok) {
        toast.success('Scraper triggered successfully');
        fetchStatus();
      } else {
        toast.error('Failed to trigger scraper');
      }
    } catch (error) {
      console.error('Error triggering scraper:', error);
      toast.error('Failed to trigger scraper');
    }
  };

  const getStatusBadge = (status: string) => {
    const config: Record<string, { color: string; icon: any; label: string }> = {
      idle: { color: 'bg-gray-100 text-gray-800', icon: Clock, label: 'Idle' },
      running: { color: 'bg-blue-100 text-blue-800', icon: RefreshCw, label: 'Running' },
      completed: { color: 'bg-green-100 text-green-800', icon: CheckCircle, label: 'Completed' },
      failed: { color: 'bg-red-100 text-red-800', icon: XCircle, label: 'Failed' },
    };

    const { color, icon: Icon, label } = config[status] || config.idle;

    return (
      <Badge className={`${color} flex items-center gap-1`}>
        <Icon className={`w-3 h-3 ${status === 'running' ? 'animate-spin' : ''}`} />
        {label}
      </Badge>
    );
  };

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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Scraper Management</h1>
          <p className="text-muted-foreground mt-1">Control and monitor the tender scrapers</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={autoRefresh ? "default" : "outline"}
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${autoRefresh ? 'animate-spin' : ''}`} />
            {autoRefresh ? 'Auto-Refresh ON' : 'Auto-Refresh'}
          </Button>
          <Button variant="outline" onClick={() => { fetchStatus(); fetchLiveStatus(); fetchScrapers(); fetchCronStatus(); }}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="status">Live Status</TabsTrigger>
          <TabsTrigger value="scrapers">Scrapers</TabsTrigger>
          <TabsTrigger value="cron">Cron Jobs & Logs</TabsTrigger>
        </TabsList>

        <TabsContent value="status" className="space-y-6">

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Status</CardTitle>
          </CardHeader>
          <CardContent>
            {getStatusBadge(status.status)}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Tenders Scraped</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{status.tenders_scraped}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Last Run</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">
              {status.last_run ? formatDateTime(status.last_run, { dateStyle: 'medium', timeStyle: 'short' }, 'en-US') : 'Never'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Next Run</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">
              {status.next_run ? formatDateTime(status.next_run, { dateStyle: 'medium', timeStyle: 'short' }, 'en-US') : 'Not scheduled'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Live Server Status */}
      {liveStatus && (
        <Card className={liveStatus.status === 'running' ? 'border-green-500' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Terminal className="w-5 h-5" />
              Live Server Status
              {liveStatus.status === 'running' && (
                <Badge className="bg-green-100 text-green-800 ml-2">
                  <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                  Running
                </Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Process Info */}
            {liveStatus.processes.length > 0 && (
              <div className="bg-green-50 p-4 rounded-lg">
                <h4 className="font-semibold mb-2 flex items-center gap-2">
                  <PlayCircle className="w-4 h-4 text-green-600" />
                  Running Processes ({liveStatus.processes.length})
                </h4>
                {liveStatus.processes.map((proc, idx) => (
                  <div key={idx} className="text-xs font-mono bg-white p-2 rounded mt-1 overflow-x-auto">
                    <span className="text-muted-foreground">PID {proc.pid}:</span> {proc.command}
                  </div>
                ))}
              </div>
            )}

            {/* Database Stats */}
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-muted p-3 rounded-lg text-center">
                <Database className="w-5 h-5 mx-auto mb-1 text-blue-500" />
                <p className="text-2xl font-bold">{liveStatus.database_stats?.total_tenders || 0}</p>
                <p className="text-xs text-muted-foreground">Tenders</p>
              </div>
              <div className="bg-muted p-3 rounded-lg text-center">
                <FileText className="w-5 h-5 mx-auto mb-1 text-purple-500" />
                <p className="text-2xl font-bold">{liveStatus.database_stats?.total_documents || 0}</p>
                <p className="text-xs text-muted-foreground">Documents</p>
              </div>
              <div className="bg-muted p-3 rounded-lg text-center">
                <CheckCircle className="w-5 h-5 mx-auto mb-1 text-green-500" />
                <p className="text-2xl font-bold">{liveStatus.database_stats?.downloaded_documents || 0}</p>
                <p className="text-xs text-muted-foreground">Downloaded</p>
              </div>
            </div>

            {/* Log Output */}
            {liveStatus.log_tail.length > 0 && (
              <div>
                <h4 className="font-semibold mb-2 flex items-center gap-2">
                  <Terminal className="w-4 h-4" />
                  Log Output
                  <span className="text-xs text-muted-foreground font-normal">
                    ({liveStatus.log_file})
                  </span>
                </h4>
                <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-xs max-h-64 overflow-y-auto">
                  {liveStatus.log_tail.slice(-20).map((line, idx) => (
                    <div key={idx} className="whitespace-pre-wrap break-all">
                      {line}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <p className="text-xs text-muted-foreground">
              Last updated: {formatDateTime(liveStatus.timestamp, { dateStyle: 'medium', timeStyle: 'short' }, 'en-US')}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>About the Scraper</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            The scraper collects tender data from the e-nabavki.gov.mk portal. It runs automatically
            on a schedule, but you can also trigger it manually.
          </p>
          <div className="bg-muted p-4 rounded-lg">
            <h4 className="font-semibold mb-2">Data Collected:</h4>
            <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
              <li>Tender announcements and details</li>
              <li>Procuring entity information</li>
              <li>Estimated values and deadlines</li>
              <li>Categories and CPV codes</li>
            </ul>
          </div>
          <div className="flex items-start gap-2 text-sm text-muted-foreground">
            <AlertCircle className="w-4 h-4 mt-0.5 text-yellow-500" />
            <p>
              Note: The scraper runs on the server. Triggering it here queues a new scraping job.
            </p>
          </div>
        </CardContent>
      </Card>
        </TabsContent>

        {/* Scrapers Tab */}
        <TabsContent value="scrapers" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PlayCircle className="w-5 h-5" />
                Available Scrapers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {scrapers.map((scraper) => (
                  <Card key={scraper.id} className={scraper.is_running ? 'border-green-500' : ''}>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base flex items-center justify-between">
                        <span>{scraper.name}</span>
                        {scraper.is_running && (
                          <Badge className="bg-green-100 text-green-800">
                            <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                            Running
                          </Badge>
                        )}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <p className="text-sm text-muted-foreground">{scraper.description}</p>
                      <div className="text-xs font-mono bg-muted p-2 rounded overflow-x-auto">
                        {scraper.command}
                      </div>
                      <div className="flex gap-2">
                        {scraper.is_running ? (
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleStopScraper(scraper.id)}
                            disabled={loadingScrapers[scraper.id]}
                          >
                            {loadingScrapers[scraper.id] ? (
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                              <StopCircle className="w-4 h-4 mr-2" />
                            )}
                            Stop
                          </Button>
                        ) : (
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() => handleRunScraper(scraper.id)}
                            disabled={loadingScrapers[scraper.id]}
                          >
                            {loadingScrapers[scraper.id] ? (
                              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            ) : (
                              <PlayCircle className="w-4 h-4 mr-2" />
                            )}
                            Run
                          </Button>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
              {scrapers.length === 0 && (
                <p className="text-muted-foreground text-center py-8">
                  No scrapers configured. API endpoint may not be available.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Cron Jobs & Logs Tab */}
        <TabsContent value="cron" className="space-y-6">
          {/* Cron Entries */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                Scheduled Cron Jobs
              </CardTitle>
            </CardHeader>
            <CardContent>
              {cronStatus?.cron_entries && cronStatus.cron_entries.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Schedule</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Command</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cronStatus.cron_entries.map((entry, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-mono text-sm">{entry.schedule}</TableCell>
                        <TableCell>{entry.description}</TableCell>
                        <TableCell className="font-mono text-xs max-w-md truncate">{entry.command}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <p className="text-muted-foreground text-center py-4">
                  No cron jobs configured or API not available.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Log Files */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ScrollText className="w-5 h-5" />
                Log Files
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {cronStatus?.log_files && cronStatus.log_files.length > 0 ? (
                <>
                  <div className="flex flex-wrap gap-2">
                    {cronStatus.log_files.map((log) => (
                      <Button
                        key={log.name}
                        variant={selectedLog === log.name ? "default" : "outline"}
                        size="sm"
                        onClick={() => fetchLogContent(log.name)}
                      >
                        <FileText className="w-4 h-4 mr-2" />
                        {log.name}
                        <span className="ml-2 text-xs opacity-70">
                          ({(log.size / 1024).toFixed(1)} KB)
                        </span>
                      </Button>
                    ))}
                  </div>
                  {selectedLog && logContent.length > 0 && (
                    <div>
                      <h4 className="font-semibold mb-2 flex items-center gap-2">
                        <Terminal className="w-4 h-4" />
                        {selectedLog}
                      </h4>
                      <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-xs max-h-96 overflow-y-auto">
                        {logContent.map((line, idx) => (
                          <div key={idx} className="whitespace-pre-wrap break-all">
                            {line}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-muted-foreground text-center py-4">
                  No log files found or API not available.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
