'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from 'sonner';
import { useRouter } from 'next/navigation';
import { ExternalLink, Check, Inbox, Filter, ThumbsUp, ThumbsDown } from 'lucide-react';
import { Select } from '@/components/ui/select';

interface AlertMatch {
  match_id: string;
  alert_id: string;
  alert_name: string;
  tender_id: string;
  tender_title: string;
  match_score: number;
  match_reasons: string[];
  is_read: boolean;
  matched_at: string;
  tender?: {
    procuring_entity?: string;
    estimated_value_mkd?: number;
    closing_date?: string;
    cpv_code?: string;
  };
}

export function AlertMatches() {
  const [matches, setMatches] = useState<AlertMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedAlert, setSelectedAlert] = useState<string>('all');
  const [alerts, setAlerts] = useState<any[]>([]);
  const [feedbackState, setFeedbackState] = useState<Record<string, 'up' | 'down' | null>>({});
  const router = useRouter();

  useEffect(() => {
    loadData();
  }, [selectedAlert]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [matchesData, alertsData] = await Promise.all([
        api.getAlertMatches(selectedAlert === 'all' ? undefined : selectedAlert),
        api.getAlerts(),
      ]);
      // Handle both array and {matches: [...]} response formats
      const matchesList = Array.isArray(matchesData) ? matchesData : (matchesData.matches || []);
      // Normalize match fields (backend may use different names)
      const normalized = matchesList.map((m: any) => ({
        ...m,
        tender_title: m.tender_title || m.tender_details?.title || m.tender?.title || '',
        matched_at: m.matched_at || m.created_at || '',
        tender: m.tender || m.tender_details || null,
      }));
      setMatches(normalized);
      // Handle both array and {alerts: [...]} response formats
      const alertsList = Array.isArray(alertsData) ? alertsData : (alertsData.alerts || []);
      setAlerts(alertsList);
    } catch (error: any) {
      console.error('Failed to load matches:', error);
      toast.error('Грешка при вчитување на совпаѓањата');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkAsRead = async (matchIds: string[]) => {
    try {
      await api.markMatchesRead(matchIds);
      setMatches((prev) =>
        prev.map((match) =>
          matchIds.includes(match.match_id) ? { ...match, is_read: true } : match
        )
      );
      toast.success('Означено како прочитано');
    } catch (error: any) {
      console.error('Failed to mark as read:', error);
      toast.error('Грешка при означување');
    }
  };

  const handleViewTender = (tenderId: string, matchId: string) => {
    handleMarkAsRead([matchId]);
    router.push(`/tenders/${encodeURIComponent(tenderId)}`);
  };

  const handleFeedback = async (matchId: string, feedback: 'up' | 'down') => {
    try {
      await api.submitMatchFeedback(matchId, feedback);
      setFeedbackState((prev) => ({ ...prev, [matchId]: feedback }));
      toast.success(feedback === 'up' ? 'Релевантен' : 'Нерелевантен');
    } catch {
      toast.error('Грешка при испраќање');
    }
  };

  const getScoreBadgeVariant = (score: number): 'default' | 'secondary' | 'outline' => {
    if (score >= 70) return 'default';
    if (score >= 40) return 'secondary';
    return 'outline';
  };

  const getScoreColor = (score: number): string => {
    if (score >= 70) return 'bg-green-500';
    if (score >= 40) return 'bg-yellow-500';
    return 'bg-gray-500';
  };

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Card key={i}>
            <CardContent className="p-6">
              <div className="space-y-3">
                <Skeleton className="h-6 w-1/3" />
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-8 w-full" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const unreadCount = matches.filter((m) => !m.is_read).length;

  return (
    <div className="space-y-4">
      {/* Filter Section */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Филтер:</span>
            </div>
            <select
              value={selectedAlert}
              onChange={(e) => setSelectedAlert(e.target.value)}
              className="flex h-9 rounded-md border border-input bg-background px-3 py-1 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="all">Сите алерти</option>
              {alerts.map((alert) => (
                <option key={alert.id} value={alert.id}>
                  {alert.name}
                </option>
              ))}
            </select>
            {unreadCount > 0 && (
              <Badge variant="default">{unreadCount} непрочитани</Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Matches List */}
      {matches.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 text-center">
            <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
              <Inbox className="w-8 h-8 text-muted-foreground" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Нема совпаѓања</h3>
            <p className="text-muted-foreground max-w-md">
              Сè уште нема тендери кои се совпаѓаат со вашите алерти. Проверете повторно подоцна.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {matches.map((match) => (
            <Card
              key={match.match_id}
              className={`${!match.is_read ? 'border-l-4 border-l-primary' : ''} transition-all hover:shadow-md`}
            >
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <Badge variant="outline" className="text-xs">
                        {match.alert_name}
                      </Badge>
                      <Badge
                        variant={getScoreBadgeVariant(match.match_score)}
                        className={`${getScoreColor(match.match_score)} text-primary-foreground`}
                      >
                        {match.match_score}% совпаѓање
                      </Badge>
                      {!match.is_read && (
                        <Badge variant="default" className="bg-blue-500">
                          Ново
                        </Badge>
                      )}
                    </div>
                    <CardTitle className="text-lg mb-1">
                      {match.tender_title}
                    </CardTitle>
                    {match.tender && (
                      <CardDescription className="text-sm">
                        {match.tender.procuring_entity && (
                          <span className="block">{match.tender.procuring_entity}</span>
                        )}
                        {match.tender.estimated_value_mkd && (
                          <span className="block">
                            Проценета вредност: {match.tender.estimated_value_mkd.toLocaleString()} МКД
                          </span>
                        )}
                        {match.tender.closing_date && (
                          <span className="block">
                            Рок: {new Date(match.tender.closing_date).toLocaleDateString('mk-MK')}
                          </span>
                        )}
                      </CardDescription>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {match.match_reasons && match.match_reasons.length > 0 && (
                  <div className="mb-4">
                    <p className="text-sm font-medium mb-2">Причини за совпаѓање:</p>
                    <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                      {match.match_reasons.map((reason, idx) => (
                        <li key={idx}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="flex items-center gap-2 flex-wrap">
                  <Button
                    size="sm"
                    onClick={() => handleViewTender(match.tender_id, match.match_id)}
                  >
                    <ExternalLink className="w-4 h-4 mr-1" />
                    Отвори Тендер
                  </Button>
                  {!match.is_read && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleMarkAsRead([match.match_id])}
                    >
                      <Check className="w-4 h-4 mr-1" />
                      Означи прочитано
                    </Button>
                  )}
                  <div className="flex items-center gap-1 ml-2">
                    <Button
                      variant={feedbackState[match.match_id] === 'up' ? 'default' : 'ghost'}
                      size="sm"
                      onClick={() => handleFeedback(match.match_id, 'up')}
                      className="h-8 w-8 p-0"
                      title="Релевантен"
                    >
                      <ThumbsUp className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant={feedbackState[match.match_id] === 'down' ? 'destructive' : 'ghost'}
                      size="sm"
                      onClick={() => handleFeedback(match.match_id, 'down')}
                      className="h-8 w-8 p-0"
                      title="Нерелевантен"
                    >
                      <ThumbsDown className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                  <span className="text-xs text-muted-foreground ml-auto">
                    {match.matched_at ? new Date(match.matched_at).toLocaleString('mk-MK') : ''}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {matches.length > 0 && unreadCount > 0 && (
        <div className="flex justify-center">
          <Button
            variant="outline"
            onClick={() => handleMarkAsRead(matches.filter((m) => !m.is_read).map((m) => m.match_id))}
          >
            <Check className="w-4 h-4 mr-2" />
            Означи сè како прочитано
          </Button>
        </div>
      )}
    </div>
  );
}
