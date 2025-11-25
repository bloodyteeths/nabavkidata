'use client';

import { useEffect, useState } from 'react';
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
import { PlayCircle, StopCircle, RefreshCw, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { toast } from "sonner";

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

export default function AdminScraperPage() {
  const [status, setStatus] = useState<ScraperStatus>({
    status: 'idle',
    last_run: null,
    next_run: null,
    tenders_scraped: 0,
  });
  const [jobs, setJobs] = useState<ScrapingJob[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
  }, []);

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
          <p className="text-muted-foreground mt-1">Control and monitor the tender scraper</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={fetchStatus}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button onClick={handleTrigger} disabled={status.status === 'running'}>
            <PlayCircle className="w-4 h-4 mr-2" />
            Trigger Scraper
          </Button>
        </div>
      </div>

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
              {status.last_run ? new Date(status.last_run).toLocaleString('en-US') : 'Never'}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Next Run</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm">
              {status.next_run ? new Date(status.next_run).toLocaleString('en-US') : 'Not scheduled'}
            </p>
          </CardContent>
        </Card>
      </div>

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
    </div>
  );
}
