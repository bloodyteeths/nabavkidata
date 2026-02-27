"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Bell, BellRing, AlertTriangle, CheckCircle2, Eye, Trash2, Plus, RefreshCw, Loader2, Filter, Clock } from "lucide-react";
import Link from "next/link";
import { tenderUrl } from "@/lib/utils";

const API_URL = typeof window !== "undefined"
  ? (window.location.hostname === "localhost" ? "http://localhost:8000" : "https://api.nabavkidata.com")
  : "https://api.nabavkidata.com";

interface Alert {
  alert_id: string; tender_id: string; rule_type: string;
  severity: string; title: string; details: string;
  read: boolean; created_at: string;
}
interface AlertsResponse { alerts: Alert[]; total: number; unread_count: number; }
interface AlertStats {
  total_alerts: number; unread_count: number;
  by_severity: Record<string, number>; by_rule_type: Record<string, number>;
  recent_24h: number; recent_7d: number;
}
interface Subscription {
  id: string; rule_type: string; rule_config: Record<string, any>;
  severity_filter: string; is_active?: boolean; created_at?: string;
}

const RULE_TYPE_LABELS: Record<string, string> = {
  high_risk_score: "Висок ризик скор",
  single_bidder_high_value: "Еден понудувач + висока вредност",
  watched_entity: "Следена компанија",
  multiple_red_flags: "Повеќе црвени знамиња",
  repeat_pattern: "Повторен образец",
  escalating_risk: "Ескалирачки ризик",
};
const SEV_COLORS: Record<string, string> = {
  critical: "bg-red-500", high: "bg-orange-500", medium: "bg-yellow-500", low: "bg-blue-500",
};
const SEV_BADGE: Record<string, string> = {
  critical: "bg-red-100 text-red-700 border-red-200",
  high: "bg-orange-100 text-orange-700 border-orange-200",
  medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
  low: "bg-blue-100 text-blue-700 border-blue-200",
};
const SEV_LABEL: Record<string, string> = {
  critical: "Критично", high: "Високо", medium: "Средно", low: "Ниско",
};
const PAGE_SIZE = 20;

function authHeaders(): HeadersInit {
  const t = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
  return { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}) };
}

function timeAgo(dateStr: string): string {
  try {
    const ms = Date.now() - new Date(dateStr).getTime();
    const m = Math.floor(ms / 60000), h = Math.floor(m / 60), d = Math.floor(h / 24);
    if (m < 1) return "сега";
    if (m < 60) return `пред ${m} ${m === 1 ? "минута" : "минути"}`;
    if (h < 24) return `пред ${h} ${h === 1 ? "час" : "часови"}`;
    if (d < 30) return `пред ${d} ${d === 1 ? "ден" : "денови"}`;
    return new Date(dateStr).toLocaleDateString("mk-MK");
  } catch { return ""; }
}

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { ...opts, headers: { ...authHeaders(), ...opts?.headers } });
  if (!res.ok) throw new Error("Грешка");
  return res.json();
}

export function AlertsFeed() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [stats, setStats] = useState<AlertStats | null>(null);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loadingMore, setLoadingMore] = useState(false);
  const [markingAll, setMarkingAll] = useState(false);
  const [subs, setSubs] = useState<Subscription[]>([]);
  const [subsLoading, setSubsLoading] = useState(true);
  const [subsError, setSubsError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [newRule, setNewRule] = useState("");
  const [newSev, setNewSev] = useState("medium");
  const [newThreshold, setNewThreshold] = useState("70");
  const [newEntity, setNewEntity] = useState("");
  const [creating, setCreating] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const loadAlerts = useCallback(async (reset = true) => {
    try {
      reset ? setAlertsLoading(true) : setLoadingMore(true);
      if (reset) setOffset(0);
      setAlertsError(null);
      const off = reset ? 0 : offset + PAGE_SIZE;
      const data = await apiFetch<AlertsResponse>(
        `/api/corruption/alerts?limit=${PAGE_SIZE}&offset=${off}&unread_only=false&severity=all`
      );
      reset ? setAlerts(data.alerts) : (setAlerts(p => [...p, ...data.alerts]), setOffset(off));
      setTotal(data.total);
    } catch (e: any) { setAlertsError(e.message || "Грешка при вчитување"); }
    finally { setAlertsLoading(false); setLoadingMore(false); }
  }, [offset]);

  const loadStats = useCallback(async () => {
    try { setStats(await apiFetch<AlertStats>("/api/corruption/alerts/stats")); } catch {}
  }, []);

  const loadSubs = useCallback(async () => {
    try {
      setSubsLoading(true); setSubsError(null);
      const d = await apiFetch<any>("/api/corruption/alerts/subscriptions");
      const list = Array.isArray(d) ? d : (d?.subscriptions || []);
      setSubs(list.map((s: any) => ({ ...s, id: s.id || s.subscription_id })));
    } catch (e: any) { setSubsError(e.message || "Грешка"); }
    finally { setSubsLoading(false); }
  }, []);

  useEffect(() => { loadAlerts(true); loadStats(); loadSubs(); }, []);

  const handleMarkRead = async (id: string) => {
    try {
      await apiFetch<void>(`/api/corruption/alerts/${id}/read`, { method: "PATCH" });
      setAlerts(p => p.map(a => a.alert_id === id ? { ...a, read: true } : a));
      setStats(p => p ? { ...p, unread_count: Math.max(0, p.unread_count - 1) } : p);
    } catch {}
  };

  const handleMarkAllRead = async () => {
    try {
      setMarkingAll(true);
      await apiFetch<void>("/api/corruption/alerts/mark-all-read", { method: "PATCH" });
      setAlerts(p => p.map(a => ({ ...a, read: true })));
      setStats(p => p ? { ...p, unread_count: 0 } : p);
    } catch { setAlertsError("Грешка при означување"); }
    finally { setMarkingAll(false); }
  };

  const handleDeleteSub = async (id: string) => {
    if (!confirm("Дали сте сигурни дека сакате да ја избришете претплатата?")) return;
    try {
      setDeletingId(id);
      await apiFetch<void>(`/api/corruption/alerts/subscriptions/${id}`, { method: "DELETE" });
      setSubs(p => p.filter(s => s.id !== id));
    } catch (e: any) { setSubsError(e.message || "Грешка при бришење"); }
    finally { setDeletingId(null); }
  };

  const handleCreateSub = async () => {
    if (!newRule) return;
    try {
      setCreating(true);
      const cfg: Record<string, any> = {};
      if (newRule === "high_risk_score") cfg.threshold = parseInt(newThreshold, 10) || 70;
      if (newRule === "watched_entity" && newEntity.trim()) cfg.watched_entities = [newEntity.trim()];
      const raw = await apiFetch<any>("/api/corruption/alerts/subscriptions", {
        method: "POST", body: JSON.stringify({ rule_type: newRule, rule_config: cfg, severity_filter: newSev }),
      });
      const sub: Subscription = { ...raw, id: raw.id || raw.subscription_id };
      setSubs(p => [...p, sub]);
      setNewRule(""); setNewSev("medium"); setNewThreshold("70"); setNewEntity("");
    } catch (e: any) { setSubsError(e.message || "Грешка при креирање"); }
    finally { setCreating(false); }
  };

  const hasMore = alerts.length < total;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* LEFT COLUMN: Alert Feed */}
      <div className="lg:col-span-2 space-y-4">
        {/* Stats Bar */}
        <Card>
          <CardContent className="p-4">
            {stats ? (
              <div className="flex flex-wrap items-center gap-4">
                <div className="flex items-center gap-2">
                  <Bell className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">Вкупно: {stats.total_alerts}</span>
                </div>
                <div className="flex items-center gap-2">
                  <BellRing className="h-4 w-4 text-red-500" />
                  <Badge className="bg-red-500 text-primary-foreground hover:bg-red-600">
                    {stats.unread_count} непрочитани
                  </Badge>
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">24ч: {stats.recent_24h}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">7д: {stats.recent_7d}</span>
                </div>
                <div className="ml-auto flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={handleMarkAllRead}
                    disabled={markingAll || stats.unread_count === 0}>
                    {markingAll
                      ? <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      : <CheckCircle2 className="h-4 w-4 mr-1" />}
                    Означи ги сите
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => { loadAlerts(true); loadStats(); }}>
                    <RefreshCw className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-4">
                <Skeleton className="h-5 w-24" /><Skeleton className="h-5 w-32" />
                <Skeleton className="h-5 w-20" /><Skeleton className="h-5 w-20" />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Error */}
        {alertsError && (
          <div className="text-sm text-destructive p-3 bg-destructive/10 rounded-md">
            <AlertTriangle className="h-4 w-4 inline mr-2" />{alertsError}
          </div>
        )}

        {/* Alert List */}
        {alertsLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map(i => (
              <Card key={i}><CardContent className="p-4">
                <div className="flex gap-3">
                  <Skeleton className="h-16 w-1.5 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-5 w-3/4" /><Skeleton className="h-4 w-1/2" />
                    <Skeleton className="h-3 w-1/4" />
                  </div>
                </div>
              </CardContent></Card>
            ))}
          </div>
        ) : alerts.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12 text-center">
              <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                <Bell className="w-8 h-8 text-muted-foreground" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Нема алерти</h3>
              <p className="text-muted-foreground max-w-md">
                Кога ќе се детектираат нови ризични тендери, тие ќе се прикажат тука.
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {alerts.map(alert => (
              <Card key={alert.alert_id}
                className={`cursor-pointer transition-all hover:shadow-md ${
                  !alert.read ? "border-l-4 border-l-blue-500 bg-blue-50/30 dark:bg-blue-950/10" : ""
                }`}
                onClick={() => { if (!alert.read) handleMarkRead(alert.alert_id); }}>
                <CardContent className="p-4">
                  <div className="flex gap-3">
                    <div className={`w-1.5 rounded-full flex-shrink-0 ${SEV_COLORS[alert.severity] || "bg-gray-400"}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h4 className="text-sm font-semibold leading-tight line-clamp-2">{alert.title}</h4>
                        {!alert.read && (
                          <span className="flex-shrink-0 mt-1">
                            <span className="block w-2.5 h-2.5 rounded-full bg-blue-500" />
                          </span>
                        )}
                      </div>
                      {alert.details && (
                        <p className="text-xs text-muted-foreground line-clamp-2 mb-2">{alert.details}</p>
                      )}
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge variant="outline" className={SEV_BADGE[alert.severity] || ""}>
                          {SEV_LABEL[alert.severity] || alert.severity}
                        </Badge>
                        <Badge variant="secondary" className="text-xs">
                          {RULE_TYPE_LABELS[alert.rule_type] || alert.rule_type}
                        </Badge>
                        {alert.tender_id && (
                          <Link href={tenderUrl(alert.tender_id)}
                            onClick={e => e.stopPropagation()}
                            className="text-xs text-blue-600 hover:underline dark:text-blue-400">
                            {alert.tender_id}
                          </Link>
                        )}
                        {mounted && (
                          <span className="text-xs text-muted-foreground ml-auto flex items-center gap-1">
                            <Clock className="h-3 w-3" />{timeAgo(alert.created_at)}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            {hasMore && (
              <div className="flex justify-center pt-2">
                <Button variant="outline" onClick={() => loadAlerts(false)} disabled={loadingMore}>
                  {loadingMore
                    ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    : <Eye className="h-4 w-4 mr-2" />}
                  Прикажи повеќе ({alerts.length} / {total})
                </Button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* RIGHT COLUMN: Subscriptions */}
      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <BellRing className="h-5 w-5" />Мои претплати
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {subsError && (
              <div className="text-sm text-destructive p-2 bg-destructive/10 rounded-md">{subsError}</div>
            )}
            {subsLoading ? (
              <div className="space-y-3">
                {[1, 2].map(i => (
                  <div key={i} className="flex items-center gap-3">
                    <Skeleton className="h-10 flex-1" /><Skeleton className="h-8 w-8" />
                  </div>
                ))}
              </div>
            ) : subs.length === 0 ? (
              <div className="text-center py-6 text-muted-foreground">
                <Bell className="h-10 w-10 mx-auto mb-2 opacity-30" />
                <p className="text-sm">Немате активни претплати</p>
              </div>
            ) : (
              <div className="space-y-2">
                {subs.map(sub => (
                  <div key={sub.id}
                    className="flex items-center gap-2 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {RULE_TYPE_LABELS[sub.rule_type] || sub.rule_type}
                      </p>
                      <div className="flex items-center gap-1.5 mt-1">
                        <Badge variant="outline" className={`text-xs ${SEV_BADGE[sub.severity_filter] || ""}`}>
                          {SEV_LABEL[sub.severity_filter] || sub.severity_filter}+
                        </Badge>
                        {sub.rule_config?.threshold && (
                          <span className="text-xs text-muted-foreground">&ge;{sub.rule_config.threshold}</span>
                        )}
                        {sub.rule_config?.entity_name && (
                          <span className="text-xs text-muted-foreground truncate">{sub.rule_config.entity_name}</span>
                        )}
                      </div>
                    </div>
                    <Button variant="ghost" size="icon"
                      className="h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
                      onClick={() => handleDeleteSub(sub.id)} disabled={deletingId === sub.id}>
                      {deletingId === sub.id
                        ? <Loader2 className="h-4 w-4 animate-spin" />
                        : <Trash2 className="h-4 w-4" />}
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Add Subscription Form */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Plus className="h-4 w-4" />Додади претплата
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Тип на правило</label>
              <Select value={newRule} onValueChange={setNewRule}>
                <SelectTrigger><SelectValue placeholder="Избери тип..." /></SelectTrigger>
                <SelectContent>
                  {Object.entries(RULE_TYPE_LABELS).map(([k, v]) => (
                    <SelectItem key={k} value={k}>{v}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">Минимална сериозност</label>
              <Select value={newSev} onValueChange={setNewSev}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="critical">Критично</SelectItem>
                  <SelectItem value="high">Високо</SelectItem>
                  <SelectItem value="medium">Средно</SelectItem>
                  <SelectItem value="low">Ниско</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {newRule === "high_risk_score" && (
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">Праг на ризик скор</label>
                <Input type="number" min={0} max={100} value={newThreshold}
                  onChange={e => setNewThreshold(e.target.value)} placeholder="70" />
              </div>
            )}
            {newRule === "watched_entity" && (
              <div>
                <label className="text-xs font-medium text-muted-foreground mb-1 block">
                  Име на компанија / институција
                </label>
                <Input value={newEntity} onChange={e => setNewEntity(e.target.value)}
                  placeholder="Внесете име..." />
              </div>
            )}
            <Button className="w-full" onClick={handleCreateSub}
              disabled={creating || !newRule || (newRule === "watched_entity" && !newEntity.trim())}>
              {creating
                ? <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                : <Plus className="h-4 w-4 mr-2" />}
              Претплати се
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default AlertsFeed;
