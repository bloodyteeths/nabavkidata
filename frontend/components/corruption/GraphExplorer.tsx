"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Network, Users, Building2, GitBranch, ArrowRight, Eye,
  Loader2, RefreshCw, Shield, TrendingUp, Activity, ChevronRight,
} from "lucide-react";

// --- Constants & Types -------------------------------------------------------

const API_URL = typeof window !== "undefined"
  ? (window.location.hostname === "localhost" ? "http://localhost:8000" : "https://api.nabavkidata.com")
  : "https://api.nabavkidata.com";

const EDGE_LABELS: Record<string, string> = {
  co_bidding: "Ко-понудување",
  buyer_supplier: "Купувач-добавувач",
  repeat_partnership: "Повторно партнерство",
  value_concentration: "Концентрација на вредност",
};

const TYPE_LABELS: Record<string, string> = { company: "Компанија", institution: "Институција" };

interface GraphStats {
  nodes: number; edges: number; density: number; components: number;
  edge_types: Record<string, number>; communities: number;
  avg_degree: number; max_degree: number;
}
interface Gatekeeper {
  entity_id: string; entity_name: string; entity_type: string;
  betweenness: number; degree: number; edge_types: Record<string, number>;
}
interface RevolvingDoor {
  entity_id: string; entity_name: string;
  buyer_connections: number; supplier_connections: number; total_value: number;
}
interface ClusterMember { id: string; name: string; type: string; pagerank: number; }
interface Cluster {
  community_id: number; members: ClusterMember[];
  size: number; density: number; internal_edges: number;
}
interface Connection {
  entity_id: string; entity_name: string; entity_type: string;
  edge_types: string[]; total_weight: number; direction: string;
}

// --- Helpers -----------------------------------------------------------------

function authHeaders(): HeadersInit {
  const token = typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;
  return { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) };
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

const fmt = (n: number | null | undefined) => n == null ? "-" : n.toLocaleString();
const fmtDec = (n: number | null | undefined, d = 4) => n == null ? "-" : n.toFixed(d);

function TypeBadge({ type }: { type: string }) {
  const inst = type === "institution";
  return (
    <Badge className={inst
      ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300"
      : "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300"}>
      {inst ? <Building2 className="mr-1 h-3 w-3" /> : <Users className="mr-1 h-3 w-3" />}
      {TYPE_LABELS[type] ?? type}
    </Badge>
  );
}

function DirArrow({ dir }: { dir: string }) {
  if (dir === "outgoing") return <ArrowRight className="h-4 w-4 text-indigo-500" />;
  if (dir === "incoming") return <ArrowRight className="h-4 w-4 rotate-180 text-purple-500" />;
  return <ArrowRight className="h-4 w-4 text-muted-foreground" />;
}

// --- Shared skeletons & error ------------------------------------------------

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {[0, 1, 2, 3].map((i) => (
        <Card key={i} className="border-purple-200/50">
          <CardContent className="flex items-center gap-3 p-4">
            <Skeleton className="h-10 w-10 rounded-lg" />
            <div className="space-y-2"><Skeleton className="h-3 w-16" /><Skeleton className="h-5 w-12" /></div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function RowsSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3 rounded-lg border p-3">
          <Skeleton className="h-5 w-5 rounded" /><Skeleton className="h-4 flex-1" /><Skeleton className="h-4 w-16" />
        </div>
      ))}
    </div>
  );
}

function Err({ msg, onRetry }: { msg: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-center">
      <Shield className="h-8 w-8 text-red-400" />
      <p className="text-sm text-muted-foreground">{msg}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="mr-1 h-3 w-3" />Повтори
        </Button>
      )}
    </div>
  );
}

const hoverRow = "flex w-full items-center gap-3 rounded-lg border border-transparent p-3 text-left transition hover:border-purple-300 hover:bg-purple-50/50 dark:hover:border-purple-700 dark:hover:bg-purple-900/20";

// --- StatCard ----------------------------------------------------------------

function StatCard({ icon: Icon, label, value, sub }: {
  icon: typeof Network; label: string; value: string; sub?: string;
}) {
  return (
    <Card className="border-purple-200/50 dark:border-purple-800/30">
      <CardContent className="flex items-center gap-3 p-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900/30">
          <Icon className="h-5 w-5 text-purple-600 dark:text-purple-400" />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{label}</p>
          <p className="text-lg font-bold leading-tight">{value}</p>
          {sub && <p className="truncate text-xs text-muted-foreground">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

// --- Gatekeepers -------------------------------------------------------------

function GatekeepersView({ onSelect }: { onSelect: (id: string, name: string) => void }) {
  const [data, setData] = useState<Gatekeeper[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await apiFetch<{ gatekeepers: Gatekeeper[] }>("/api/corruption/graph/gatekeepers?top_n=20");
      setData(r.gatekeepers ?? []);
    } catch { setError("Грешка при вчитување на привратници."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <RowsSkeleton />;
  if (error) return <Err msg={error} onRetry={load} />;
  if (!data.length) return <p className="py-6 text-center text-sm text-muted-foreground">Нема податоци.</p>;

  const maxB = Math.max(...data.map((g) => g.betweenness), 0.001);

  return (
    <div className="space-y-1.5">
      {data.map((g, i) => (
        <button key={g.entity_id} onClick={() => onSelect(g.entity_id, g.entity_name)} className={hoverRow}>
          <span className="w-5 shrink-0 text-center text-xs font-medium text-muted-foreground">{i + 1}</span>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">{g.entity_name}</span>
              <TypeBadge type={g.entity_type} />
            </div>
            <div className="mt-1.5 flex items-center gap-2">
              <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-gradient-to-r from-purple-500 to-indigo-500"
                  style={{ width: `${(g.betweenness / maxB) * 100}%` }} />
              </div>
              <span className="shrink-0 text-xs text-muted-foreground">{fmtDec(g.betweenness)}</span>
            </div>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-0.5">
            <span className="text-xs text-muted-foreground">Врски</span>
            <span className="text-sm font-semibold">{fmt(g.degree)}</span>
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
      ))}
    </div>
  );
}

// --- Revolving Doors ---------------------------------------------------------

function RevolvingDoorsView({ onSelect }: { onSelect: (id: string, name: string) => void }) {
  const [data, setData] = useState<RevolvingDoor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await apiFetch<{ revolving_doors: RevolvingDoor[] }>("/api/corruption/graph/revolving-doors");
      setData(r.revolving_doors ?? []);
    } catch { setError("Грешка при вчитување на ротирачки врати."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <RowsSkeleton />;
  if (error) return <Err msg={error} onRetry={load} />;
  if (!data.length) return <p className="py-6 text-center text-sm text-muted-foreground">Нема податоци.</p>;

  return (
    <div className="space-y-1.5">
      {data.map((rd) => (
        <button key={rd.entity_id} onClick={() => onSelect(rd.entity_id, rd.entity_name)} className={hoverRow}>
          <GitBranch className="h-4 w-4 shrink-0 text-indigo-500" />
          <span className="min-w-0 flex-1 truncate text-sm font-medium">{rd.entity_name}</span>
          <div className="flex shrink-0 items-center gap-4 text-xs">
            <div className="flex flex-col items-center">
              <span className="text-muted-foreground">Купувач</span>
              <span className="font-semibold text-indigo-600 dark:text-indigo-400">{fmt(rd.buyer_connections)}</span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-muted-foreground">Добавувач</span>
              <span className="font-semibold text-purple-600 dark:text-purple-400">{fmt(rd.supplier_connections)}</span>
            </div>
            <div className="flex flex-col items-center">
              <span className="text-muted-foreground">Вредност</span>
              <span className="font-semibold">{fmt(rd.total_value)} ден.</span>
            </div>
          </div>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        </button>
      ))}
    </div>
  );
}

// --- Clusters ----------------------------------------------------------------

function ClustersView({ onSelect }: { onSelect: (id: string, name: string) => void }) {
  const [data, setData] = useState<Cluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await apiFetch<{ clusters: Cluster[] }>("/api/corruption/graph/clusters?min_size=3");
      setData(r.clusters ?? []);
    } catch { setError("Грешка при вчитување на кластери."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = (id: number) => setExpanded((prev) => {
    const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s;
  });

  if (loading) return <RowsSkeleton />;
  if (error) return <Err msg={error} onRetry={load} />;
  if (!data.length) return <p className="py-6 text-center text-sm text-muted-foreground">Нема кластери.</p>;

  return (
    <div className="space-y-2">
      {data.map((cl) => {
        const open = expanded.has(cl.community_id);
        return (
          <div key={cl.community_id} className="rounded-lg border border-purple-200/50 dark:border-purple-800/30">
            <button onClick={() => toggle(cl.community_id)}
              className="flex w-full items-center gap-3 p-3 text-left transition hover:bg-purple-50/50 dark:hover:bg-purple-900/20">
              <Network className="h-4 w-4 shrink-0 text-purple-500" />
              <span className="min-w-0 flex-1 text-sm font-medium">Кластер #{cl.community_id}</span>
              <div className="flex shrink-0 items-center gap-4 text-xs">
                <div className="flex flex-col items-center">
                  <span className="text-muted-foreground">Членови</span>
                  <span className="font-semibold">{fmt(cl.size)}</span>
                </div>
                <div className="flex flex-col items-center">
                  <span className="text-muted-foreground">Густина</span>
                  <span className="font-semibold">{fmtDec(cl.density, 2)}</span>
                </div>
                <div className="flex flex-col items-center">
                  <span className="text-muted-foreground">Врски</span>
                  <span className="font-semibold">{fmt(cl.internal_edges)}</span>
                </div>
              </div>
              <ChevronRight className={`h-4 w-4 shrink-0 text-muted-foreground transition ${open ? "rotate-90" : ""}`} />
            </button>
            {open && (
              <div className="border-t px-3 pb-3 pt-2 space-y-1">
                {cl.members.map((m) => (
                  <button key={m.id} onClick={() => onSelect(m.id, m.name)}
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm transition hover:bg-purple-50 dark:hover:bg-purple-900/20">
                    <span className="min-w-0 flex-1 truncate">{m.name}</span>
                    <TypeBadge type={m.type} />
                    <span className="shrink-0 text-xs text-muted-foreground">PR: {fmtDec(m.pagerank)}</span>
                    <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                  </button>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// --- Entity Explorer ---------------------------------------------------------

function EntityExplorer({ entityId, entityName, onBack, onSelect }: {
  entityId: string; entityName: string; onBack: () => void;
  onSelect: (id: string, name: string) => void;
}) {
  const [conns, setConns] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const r = await apiFetch<{ entity_id: string; connections: Connection[] }>(
        `/api/corruption/graph/entity/${encodeURIComponent(entityId)}/connections`);
      setConns(r.connections ?? []);
    } catch { setError("Грешка при вчитување на поврзувања."); }
    finally { setLoading(false); }
  }, [entityId]);

  useEffect(() => { load(); }, [load]);

  const grouped = conns.reduce<Record<string, Connection[]>>((acc, c) => {
    for (const et of c.edge_types) { (acc[et] ??= []).push(c); }
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={onBack}>
          <ChevronRight className="mr-1 h-3 w-3 rotate-180" />Назад
        </Button>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold">{entityName}</h3>
          <p className="text-xs text-muted-foreground">{fmt(conns.length)} поврзувања</p>
        </div>
        <Eye className="h-5 w-5 shrink-0 text-purple-500" />
      </div>

      {loading && <RowsSkeleton rows={4} />}
      {error && <Err msg={error} onRetry={load} />}
      {!loading && !error && !conns.length && (
        <p className="py-6 text-center text-sm text-muted-foreground">Нема поврзувања за овој ентитет.</p>
      )}

      {!loading && !error && Object.entries(grouped).map(([et, list]) => (
        <div key={et}>
          <div className="mb-1.5 flex items-center gap-2">
            <Activity className="h-3.5 w-3.5 text-indigo-500" />
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {EDGE_LABELS[et] ?? et}
            </span>
            <Badge variant="secondary" className="text-[10px]">{list.length}</Badge>
          </div>
          <div className="space-y-1">
            {list.map((c) => (
              <button key={`${c.entity_id}-${et}`} onClick={() => onSelect(c.entity_id, c.entity_name)}
                className="flex w-full items-center gap-2 rounded-lg border border-transparent px-3 py-2 text-left text-sm transition hover:border-purple-300 hover:bg-purple-50/50 dark:hover:border-purple-700 dark:hover:bg-purple-900/20">
                <DirArrow dir={c.direction} />
                <span className="min-w-0 flex-1 truncate">{c.entity_name}</span>
                <TypeBadge type={c.entity_type} />
                <span className="shrink-0 text-xs text-muted-foreground">Тежина: {fmtDec(c.total_weight, 2)}</span>
                <ChevronRight className="h-3 w-3 shrink-0 text-muted-foreground" />
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// --- Main Component ----------------------------------------------------------

export function GraphExplorer() {
  const [stats, setStats] = useState<GraphStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ id: string; name: string } | null>(null);
  const [tab, setTab] = useState("gatekeepers");

  const loadStats = useCallback(async () => {
    setStatsLoading(true); setStatsError(null);
    try { setStats(await apiFetch<GraphStats>("/api/corruption/graph/stats")); }
    catch { setStatsError("Грешка при вчитување на статистики."); }
    finally { setStatsLoading(false); }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  const pick = useCallback((id: string, name: string) => setSelected({ id, name }), []);
  const back = useCallback(() => setSelected(null), []);

  return (
    <div className="space-y-4">
      {/* Section 1 - Stats */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Network className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            <h2 className="text-base font-semibold">Граф на поврзаност</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={loadStats} disabled={statsLoading}>
            {statsLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          </Button>
        </div>

        {statsLoading && <StatsSkeleton />}
        {statsError && <Err msg={statsError} onRetry={loadStats} />}
        {stats && !statsLoading && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard icon={Users} label="Ентитети" value={fmt(stats.nodes)}
              sub={`Макс. степен: ${fmt(stats.max_degree)}`} />
            <StatCard icon={GitBranch} label="Врски" value={fmt(stats.edges)}
              sub={`Просек: ${fmtDec(stats.avg_degree, 1)}`} />
            <StatCard icon={Shield} label="Заедници" value={fmt(stats.communities)}
              sub={`${fmt(stats.components)} компоненти`} />
            <StatCard icon={TrendingUp} label="Густина" value={fmtDec(stats.density, 4)}
              sub={stats.edge_types
                ? Object.entries(stats.edge_types).map(([k, v]) => `${EDGE_LABELS[k] ?? k}: ${fmt(v)}`).join(" | ")
                : undefined} />
          </div>
        )}
      </div>

      {/* Section 2 & 3 - Tabs / Explorer */}
      <Card className="border-purple-200/50 dark:border-purple-800/30">
        <CardHeader className="pb-3 pt-4 px-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Eye className="h-4 w-4 text-purple-600 dark:text-purple-400" />
            {selected ? "Истражување на ентитет" : "Анализа на мрежа"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          {selected ? (
            <EntityExplorer entityId={selected.id} entityName={selected.name} onBack={back} onSelect={pick} />
          ) : (
            <Tabs value={tab} onValueChange={setTab}>
              <TabsList className="w-full">
                <TabsTrigger value="gatekeepers" className="flex-1 text-xs">
                  <Shield className="mr-1 h-3.5 w-3.5" />Привратници
                </TabsTrigger>
                <TabsTrigger value="revolving" className="flex-1 text-xs">
                  <GitBranch className="mr-1 h-3.5 w-3.5" />Ротирачки врати
                </TabsTrigger>
                <TabsTrigger value="clusters" className="flex-1 text-xs">
                  <Network className="mr-1 h-3.5 w-3.5" />Кластери
                </TabsTrigger>
              </TabsList>
              <TabsContent value="gatekeepers" className="mt-3">
                <GatekeepersView onSelect={pick} />
              </TabsContent>
              <TabsContent value="revolving" className="mt-3">
                <RevolvingDoorsView onSelect={pick} />
              </TabsContent>
              <TabsContent value="clusters" className="mt-3">
                <ClustersView onSelect={pick} />
              </TabsContent>
            </Tabs>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default GraphExplorer;
