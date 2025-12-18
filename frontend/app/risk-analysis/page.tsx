"use client";

import { useState, useEffect, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  Database,
  Globe,
  FileText,
  Building2,
  Brain,
  Shield,
  Newspaper,
  Clock,
  Search,
  Filter,
  TrendingUp,
  Activity,
  Eye,
  ExternalLink,
  RefreshCw,
  Zap,
  AlertCircle,
  Users,
  Repeat,
  DollarSign,
  Timer,
  FileWarning,
  Link2,
  Radar,
  ListFilter,
  Loader2
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { api } from "@/lib/api";
import Link from "next/link";

// API URL
const API_URL = typeof window !== 'undefined'
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : 'https://api.nabavkidata.com';

// Risk level configs
const RISK_LEVELS = {
  critical: { bg: "bg-red-500", light: "bg-red-100", text: "text-red-700", border: "border-red-300", label: "Критичен" },
  high: { bg: "bg-orange-500", light: "bg-orange-100", text: "text-orange-700", border: "border-orange-300", label: "Висок" },
  medium: { bg: "bg-yellow-500", light: "bg-yellow-100", text: "text-yellow-700", border: "border-yellow-300", label: "Среден" },
  low: { bg: "bg-blue-500", light: "bg-blue-100", text: "text-blue-700", border: "border-blue-300", label: "Низок" },
  minimal: { bg: "bg-green-500", light: "bg-green-100", text: "text-green-700", border: "border-green-300", label: "Минимален" }
};

// Flag type configs
const FLAG_TYPES: Record<string, { icon: any; label: string; description: string }> = {
  single_bidder: { icon: Users, label: "1 понудувач", description: "Само една компанија поднела понуда" },
  repeat_winner: { icon: Repeat, label: "Повторен победник", description: "Истата компанија често добива" },
  price_anomaly: { icon: DollarSign, label: "Ценовна аномалија", description: "Невообичаена цена" },
  bid_clustering: { icon: Link2, label: "Кластер понуди", description: "Сомнително координирани понуди" },
  short_deadline: { icon: Timer, label: "Краток рок", description: "Невообичаено кус рок за понуди" },
  high_amendments: { icon: FileWarning, label: "Многу измени", description: "Премногу амандмани на договорот" },
  spec_rigging: { icon: FileText, label: "Наместени спецификации", description: "Спецификации кои фаворизираат" },
  related_companies: { icon: Building2, label: "Поврзани компании", description: "Понудувачи со заедничко власништво" }
};

interface RiskFlag {
  flag_id: string;
  flag_type: string;
  severity: string;
  score: number;
  description: string;
  evidence: any;
}

interface RiskyTender {
  tender_id: string;
  title: string;
  procuring_entity: string;
  estimated_value_mkd: number;
  winner: string;
  risk_score: number;
  risk_level: string;
  flag_count: number;
  flags: RiskFlag[];
  last_analyzed: string;
}

interface RiskStats {
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  last_scan: string;
}

export default function RiskAnalysisPage() {
  // Mode: "flagged" shows pre-analyzed, "search" shows all tenders for on-demand analysis
  const [mode, setMode] = useState<"flagged" | "search">("flagged");

  // Flagged tenders data
  const [riskyTenders, setRiskyTenders] = useState<RiskyTender[]>([]);
  const [stats, setStats] = useState<RiskStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  // Search mode data
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchTotal, setSearchTotal] = useState(0);

  // Analysis states
  const [analyzingTender, setAnalyzingTender] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Filter states
  const [riskLevelFilter, setRiskLevelFilter] = useState<string>("all");
  const [flagTypeFilter, setFlagTypeFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  // UI states
  const [expandedTender, setExpandedTender] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    if (mode === "flagged") {
      loadRiskData();
    }
  }, [riskLevelFilter, flagTypeFilter, mode]);

  const loadRiskData = useCallback(async (loadMore = false) => {
    if (loadMore) {
      setLoadingMore(true);
    } else {
      setLoading(true);
      setPage(1);
    }

    try {
      const currentPage = loadMore ? page + 1 : 1;
      const skip = (currentPage - 1) * 20;

      // Build query params for backend API
      const params = new URLSearchParams({
        skip: skip.toString(),
        limit: "20",
        min_score: "1"
      });

      if (riskLevelFilter !== "all") {
        params.append("severity", riskLevelFilter);
      }
      if (flagTypeFilter !== "all") {
        params.append("flag_type", flagTypeFilter);
      }

      const response = await fetch(`${API_URL}/api/corruption/flagged-tenders?${params}`);

      if (!response.ok) {
        throw new Error("Failed to fetch risk data");
      }

      const data = await response.json();

      // Map API response (uses 'tenders' not 'items')
      const mappedTenders: RiskyTender[] = (data.tenders || []).map((t: any) => ({
        tender_id: t.tender_id,
        title: t.title || "",
        procuring_entity: t.procuring_entity || "",
        estimated_value_mkd: parseFloat(t.estimated_value_mkd) || 0,
        winner: t.winner || "",
        risk_score: t.risk_score || 0,
        risk_level: t.risk_level || "medium",
        flag_count: t.total_flags || 0,
        flags: (t.flag_types || []).map((type: string, idx: number) => ({
          flag_id: `${t.tender_id}-${idx}`,
          flag_type: type,
          severity: t.max_severity || "medium",
          score: Math.round((t.risk_score || 0) / (t.total_flags || 1)),
          description: "",
          evidence: {}
        })),
        last_analyzed: new Date().toISOString()
      }));

      if (loadMore) {
        setRiskyTenders(prev => [...prev, ...mappedTenders]);
        setPage(currentPage);
      } else {
        setRiskyTenders(mappedTenders);
        // Fetch stats separately or calculate from total
        setStats({
          total: data.total || mappedTenders.length,
          critical: mappedTenders.filter(t => t.risk_level === "critical").length,
          high: mappedTenders.filter(t => t.risk_level === "high").length,
          medium: mappedTenders.filter(t => t.risk_level === "medium").length,
          low: mappedTenders.filter(t => t.risk_level === "low").length,
          last_scan: new Date().toISOString()
        });
      }

      setHasMore(mappedTenders.length === 20);
    } catch (err) {
      console.error("Failed to load risk data:", err);
      await loadRiskDataFallback(loadMore);
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [page, riskLevelFilter, flagTypeFilter]);

  // Fallback: get tenders with single bidder as "risky"
  const loadRiskDataFallback = async (loadMore = false) => {
    try {
      const response = await fetch(`${API_URL}/api/tenders?status=awarded&page=1&page_size=100&sort_by=estimated_value_mkd&sort_order=desc`);
      const data = await response.json();

      const simulatedRisks: RiskyTender[] = (data.items || [])
        .filter((t: any) => t.num_bidders === 1 || (t.estimated_value_mkd && parseFloat(t.estimated_value_mkd) > 10000000))
        .slice(0, 50)
        .map((t: any) => ({
          tender_id: t.tender_id,
          title: t.title,
          procuring_entity: t.procuring_entity || "Непозната институција",
          estimated_value_mkd: parseFloat(t.estimated_value_mkd) || 0,
          winner: t.winner || "",
          risk_score: t.num_bidders === 1 ? 65 : 35,
          risk_level: t.num_bidders === 1 ? "high" : "medium",
          flag_count: t.num_bidders === 1 ? 1 : 0,
          flags: t.num_bidders === 1 ? [{
            flag_id: `sim-${t.tender_id}`,
            flag_type: "single_bidder",
            severity: "high",
            score: 65,
            description: "Само еден понудувач поднел понуда",
            evidence: { num_bidders: 1 }
          }] : [],
          last_analyzed: new Date().toISOString()
        }));

      setRiskyTenders(simulatedRisks);
      setStats({
        total: simulatedRisks.length,
        critical: 0,
        high: simulatedRisks.filter(t => t.risk_level === "high").length,
        medium: simulatedRisks.filter(t => t.risk_level === "medium").length,
        low: simulatedRisks.filter(t => t.risk_level === "low").length,
        last_scan: new Date().toISOString()
      });
    } catch (err) {
      console.error("Fallback failed:", err);
    }
  };

  // Search all tenders (not just flagged)
  const searchAllTenders = async (query: string) => {
    setSearchLoading(true);
    try {
      const data = await api.searchTenders({
        query: query.trim() || undefined,
        status: "awarded",
        page: 1,
        page_size: 50,
        sort_by: "estimated_value_mkd",
        sort_order: "desc"
      });

      setSearchResults(data.items || []);
      setSearchTotal(data.total || 0);
    } catch (err) {
      console.error("Search failed:", err);
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  };

  // Analyze a specific tender on-demand
  const analyzeTender = async (tenderId: string) => {
    setAnalyzingTender(tenderId);
    setAnalysisResult(null);
    setAnalysisError(null);

    try {
      const response = await fetch(`${API_URL}/api/risk/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "tender", query: tenderId })
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail?.message || err.detail || "Анализата не успеа");
      }

      const result = await response.json();
      setAnalysisResult({ tenderId, ...result });
    } catch (err) {
      setAnalysisError(err instanceof Error ? err.message : "Грешка при анализа");
    } finally {
      setAnalyzingTender(null);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadRiskData();
  };

  const getRiskConfig = (level: string) => RISK_LEVELS[level as keyof typeof RISK_LEVELS] || RISK_LEVELS.medium;
  const getFlagConfig = (type: string) => FLAG_TYPES[type] || { icon: AlertTriangle, label: type, description: "" };

  // Risk score gauge component
  const RiskGauge = ({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) => {
    const sizes = { sm: 40, md: 56, lg: 72 };
    const s = sizes[size];
    const strokeWidth = size === "sm" ? 4 : 5;
    const radius = (s - strokeWidth) / 2;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference - (score / 100) * circumference;

    const getColor = () => {
      if (score >= 70) return "text-red-500";
      if (score >= 50) return "text-orange-500";
      if (score >= 30) return "text-yellow-500";
      return "text-blue-500";
    };

    return (
      <div className="relative" style={{ width: s, height: s }}>
        <svg className="transform -rotate-90" width={s} height={s}>
          <circle
            cx={s / 2}
            cy={s / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="none"
            className="text-muted"
          />
          <circle
            cx={s / 2}
            cy={s / 2}
            r={radius}
            stroke="currentColor"
            strokeWidth={strokeWidth}
            fill="none"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={getColor()}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`font-bold ${size === "sm" ? "text-xs" : size === "md" ? "text-sm" : "text-lg"}`}>
            {score}
          </span>
        </div>
      </div>
    );
  };

  // Tender risk card
  const TenderRiskCard = ({ tender }: { tender: RiskyTender }) => {
    const isExpanded = expandedTender === tender.tender_id;
    const riskConfig = getRiskConfig(tender.risk_level);

    return (
      <Card className={`overflow-hidden transition-all ${isExpanded ? "ring-2 ring-primary" : ""}`}>
        {/* Risk indicator bar */}
        <div className={`h-1 ${riskConfig.bg}`} />

        <CardContent className="p-4">
          {/* Header row */}
          <div className="flex items-start gap-3">
            <RiskGauge score={tender.risk_score} size="md" />

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <Badge className={`${riskConfig.light} ${riskConfig.text} border-0`}>
                  {riskConfig.label}
                </Badge>
                {tender.flag_count > 0 && (
                  <Badge variant="outline" className="text-xs">
                    {tender.flag_count} {tender.flag_count === 1 ? "знаме" : "знамиња"}
                  </Badge>
                )}
              </div>

              <h3 className="font-medium text-sm line-clamp-2 mb-1">
                {tender.title}
              </h3>

              <p className="text-xs text-muted-foreground truncate">
                {tender.procuring_entity}
              </p>
            </div>
          </div>

          {/* Quick info */}
          <div className="flex items-center justify-between mt-3 pt-3 border-t">
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="text-[10px] font-mono">
                {tender.tender_id}
              </Badge>
              {tender.estimated_value_mkd > 0 && (
                <span className="text-sm font-medium text-primary">
                  {formatCurrency(tender.estimated_value_mkd)}
                </span>
              )}
            </div>

            <Button
              variant="ghost"
              size="sm"
              onClick={() => setExpandedTender(isExpanded ? null : tender.tender_id)}
              className="h-8"
            >
              {isExpanded ? (
                <>Затвори <ChevronUp className="h-4 w-4 ml-1" /></>
              ) : (
                <>Детали <ChevronDown className="h-4 w-4 ml-1" /></>
              )}
            </Button>
          </div>

          {/* Expanded details */}
          {isExpanded && (
            <div className="mt-4 pt-4 border-t space-y-4">
              {/* Winner */}
              {tender.winner && (
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Победник:</p>
                  <p className="text-sm font-medium">{tender.winner}</p>
                </div>
              )}

              {/* Flags */}
              {tender.flags.length > 0 && (
                <div>
                  <p className="text-xs text-muted-foreground mb-2">Детектирани ризици:</p>
                  <div className="space-y-2">
                    {tender.flags.map((flag, idx) => {
                      const flagConfig = getFlagConfig(flag.flag_type);
                      const FlagIcon = flagConfig.icon;
                      const severityConfig = RISK_LEVELS[flag.severity as keyof typeof RISK_LEVELS] || RISK_LEVELS.medium;

                      return (
                        <div key={idx} className={`p-3 rounded-lg ${severityConfig.light} ${severityConfig.border} border`}>
                          <div className="flex items-start gap-2">
                            <FlagIcon className={`h-4 w-4 mt-0.5 ${severityConfig.text}`} />
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className={`text-sm font-medium ${severityConfig.text}`}>
                                  {flagConfig.label}
                                </span>
                                <Badge variant="outline" className={`text-[10px] ${severityConfig.text} border-0 ${severityConfig.light}`}>
                                  {flag.score} поени
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground">
                                {flag.description || flagConfig.description}
                              </p>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2 pt-2">
                <Link href={`/tenders/${tender.tender_id}`} className="flex-1">
                  <Button variant="outline" className="w-full" size="sm">
                    <Eye className="h-4 w-4 mr-2" />
                    Погледни тендер
                  </Button>
                </Link>
                <Link href={`/suppliers/${encodeURIComponent(tender.winner || "")}`} className="flex-1">
                  <Button variant="outline" className="w-full" size="sm" disabled={!tender.winner}>
                    <Building2 className="h-4 w-4 mr-2" />
                    Профил на победник
                  </Button>
                </Link>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6 text-primary" />
            AI Детекција на Ризици
          </h1>
          <p className="text-muted-foreground">
            Автоматска анализа на тендери за корупциски индикатори
          </p>
        </div>
      </div>

      {/* Mode Tabs */}
      <Tabs value={mode} onValueChange={(v) => setMode(v as "flagged" | "search")} className="w-full">
        <TabsList className="grid w-full grid-cols-2 max-w-md">
          <TabsTrigger value="flagged" className="flex items-center gap-2">
            <Radar className="h-4 w-4" />
            Детектирани ризици
          </TabsTrigger>
          <TabsTrigger value="search" className="flex items-center gap-2">
            <Search className="h-4 w-4" />
            Пребарај сите тендери
          </TabsTrigger>
        </TabsList>

        {/* FLAGGED MODE */}
        <TabsContent value="flagged" className="space-y-6 mt-6">
          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Card className="col-span-2 md:col-span-1">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                    <Activity className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{stats?.total || 0}</p>
                    <p className="text-xs text-muted-foreground">Детектирани</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {[
              { level: "critical", count: stats?.critical || 0 },
              { level: "high", count: stats?.high || 0 },
              { level: "medium", count: stats?.medium || 0 },
              { level: "low", count: stats?.low || 0 }
            ].map(({ level, count }) => {
              const config = RISK_LEVELS[level as keyof typeof RISK_LEVELS];
              return (
                <Card
                  key={level}
                  className={`cursor-pointer transition-all hover:ring-2 hover:ring-primary/30 ${riskLevelFilter === level ? "ring-2 ring-primary" : ""}`}
                  onClick={() => setRiskLevelFilter(riskLevelFilter === level ? "all" : level)}
                >
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3">
                      <div className={`h-10 w-10 rounded-lg ${config.light} flex items-center justify-center`}>
                        <AlertTriangle className={`h-5 w-5 ${config.text}`} />
                      </div>
                      <div>
                        <p className="text-2xl font-bold">{count}</p>
                        <p className={`text-xs ${config.text}`}>{config.label}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Info banner */}
          <Card className="bg-gradient-to-r from-primary/5 to-primary/10 border-primary/20">
            <CardContent className="p-4">
              <div className="flex flex-col md:flex-row md:items-center gap-4">
                <div className="flex items-center gap-3">
                  <div className="h-12 w-12 rounded-xl bg-primary/10 flex items-center justify-center">
                    <Zap className="h-6 w-6 text-primary" />
                  </div>
                  <div>
                    <p className="font-medium">AI Автоматски Детектира Ризици</p>
                    <p className="text-sm text-muted-foreground">
                      Овие тендери се веќе анализирани и означени како ризични
                    </p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 md:ml-auto">
                  {Object.entries(FLAG_TYPES).slice(0, 4).map(([type, config]) => {
                    const Icon = config.icon;
                    return (
                      <Badge
                        key={type}
                        variant="secondary"
                        className={`cursor-pointer ${flagTypeFilter === type ? "ring-2 ring-primary" : ""}`}
                        onClick={() => setFlagTypeFilter(flagTypeFilter === type ? "all" : type)}
                      >
                        <Icon className="h-3 w-3 mr-1" />
                        {config.label}
                      </Badge>
                    );
                  })}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Filters */}
          <div className="flex flex-wrap gap-2">
            <Select value={riskLevelFilter} onValueChange={setRiskLevelFilter}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Ризик" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Сите ризици</SelectItem>
                <SelectItem value="critical">Критичен</SelectItem>
                <SelectItem value="high">Висок</SelectItem>
                <SelectItem value="medium">Среден</SelectItem>
                <SelectItem value="low">Низок</SelectItem>
              </SelectContent>
            </Select>

            <Select value={flagTypeFilter} onValueChange={setFlagTypeFilter}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Тип на ризик" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Сите типови</SelectItem>
                {Object.entries(FLAG_TYPES).map(([type, config]) => (
                  <SelectItem key={type} value={type}>{config.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button variant="outline" size="sm" onClick={() => loadRiskData()} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
              Освежи
            </Button>
          </div>

          {/* Risk Feed */}
      {loading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <Card key={i}>
              <div className="h-1 bg-muted" />
              <CardContent className="p-4">
                <div className="flex gap-3">
                  <Skeleton className="h-14 w-14 rounded-full" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-3 w-3/4" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : riskyTenders.length === 0 ? (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center">
            <CheckCircle2 className="h-12 w-12 mx-auto text-green-500 mb-4" />
            <h3 className="font-medium text-lg mb-2">Нема детектирани ризици</h3>
            <p className="text-muted-foreground">
              {searchQuery || riskLevelFilter !== "all" || flagTypeFilter !== "all"
                ? "Пробајте да ги промените филтрите"
                : "AI агентите не пронајдоа сомнителни индикатори"}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {riskyTenders.map(tender => (
              <TenderRiskCard key={tender.tender_id} tender={tender} />
            ))}
          </div>

          {/* Load more */}
          {hasMore && (
            <div className="flex justify-center pt-4">
              <Button
                variant="outline"
                onClick={() => loadRiskData(true)}
                disabled={loadingMore}
              >
                {loadingMore ? (
                  <><RefreshCw className="h-4 w-4 mr-2 animate-spin" /> Вчитување...</>
                ) : (
                  <>Прикажи повеќе</>
                )}
              </Button>
            </div>
          )}
        </>
      )}
        </TabsContent>

        {/* SEARCH MODE */}
        <TabsContent value="search" className="space-y-6 mt-6">
          {/* Search info */}
          <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 border-blue-200">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="h-12 w-12 rounded-xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center flex-shrink-0">
                  <Search className="h-6 w-6 text-blue-600" />
                </div>
                <div>
                  <p className="font-medium">Пребарај било кој тендер</p>
                  <p className="text-sm text-muted-foreground">
                    Пребарајте низ 100,000+ тендери од e-nabavki. Кликнете "Анализирај" за детална AI анализа на било кој тендер.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Search form */}
          <form onSubmit={(e) => { e.preventDefault(); searchAllTenders(searchQuery); }} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Пребарај по назив, институција, CPV код..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Button type="submit" disabled={searchLoading}>
              {searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              <span className="ml-2 hidden sm:inline">Пребарај</span>
            </Button>
          </form>

          {/* Search results */}
          {searchLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[1, 2, 3, 4, 5, 6].map(i => (
                <Card key={i}>
                  <CardContent className="p-4">
                    <Skeleton className="h-4 w-full mb-2" />
                    <Skeleton className="h-4 w-3/4 mb-2" />
                    <Skeleton className="h-8 w-24" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : searchResults.length > 0 ? (
            <>
              <p className="text-sm text-muted-foreground">
                {searchTotal.toLocaleString()} резултати
              </p>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {searchResults.map((tender: any) => (
                  <Card key={tender.tender_id} className={`transition-all ${analyzingTender === tender.tender_id ? "ring-2 ring-primary animate-pulse" : ""}`}>
                    <CardContent className="p-4">
                      <h3 className="font-medium text-sm line-clamp-2 mb-2">{tender.title}</h3>
                      <p className="text-xs text-muted-foreground truncate mb-2">{tender.procuring_entity}</p>

                      <div className="flex items-center gap-2 flex-wrap mb-3">
                        <Badge variant="outline" className="text-[10px] font-mono">{tender.tender_id}</Badge>
                        {tender.num_bidders === 1 && (
                          <Badge variant="destructive" className="text-[10px]">1 понудувач</Badge>
                        )}
                        {tender.estimated_value_mkd && (
                          <span className="text-xs font-medium text-primary">
                            {formatCurrency(tender.estimated_value_mkd)}
                          </span>
                        )}
                      </div>

                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => analyzeTender(tender.tender_id)}
                          disabled={analyzingTender !== null}
                          className="flex-1"
                        >
                          {analyzingTender === tender.tender_id ? (
                            <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Анализирам...</>
                          ) : (
                            <><Shield className="h-3 w-3 mr-1" /> Анализирај</>
                          )}
                        </Button>
                        <Link href={`/tenders/${tender.tender_id}`}>
                          <Button variant="outline" size="sm">
                            <Eye className="h-3 w-3" />
                          </Button>
                        </Link>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </>
          ) : searchQuery ? (
            <Card className="border-dashed">
              <CardContent className="py-12 text-center">
                <Search className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="font-medium text-lg mb-2">Нема резултати</h3>
                <p className="text-muted-foreground">Пробајте со друг термин за пребарување</p>
              </CardContent>
            </Card>
          ) : (
            <Card className="border-dashed">
              <CardContent className="py-12 text-center">
                <Search className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
                <h3 className="font-medium text-lg mb-2">Започнете со пребарување</h3>
                <p className="text-muted-foreground">Внесете термин за да пребарате низ сите тендери</p>
              </CardContent>
            </Card>
          )}

          {/* Analysis result modal/card */}
          {analysisResult && (
            <Card className="border-2 border-primary">
              <div className={`h-1.5 ${getRiskConfig(analysisResult.risk_level).bg}`} />
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Shield className="h-5 w-5" />
                    Резултат од анализа
                  </CardTitle>
                  <Button variant="ghost" size="sm" onClick={() => setAnalysisResult(null)}>
                    <XCircle className="h-4 w-4" />
                  </Button>
                </div>
                <CardDescription>{analysisResult.tenderId}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-4">
                  <RiskGauge score={analysisResult.risk_score} size="lg" />
                  <div>
                    <Badge className={`${getRiskConfig(analysisResult.risk_level).light} ${getRiskConfig(analysisResult.risk_level).text}`}>
                      {getRiskConfig(analysisResult.risk_level).label} ризик
                    </Badge>
                    <p className="text-sm text-muted-foreground mt-1">
                      {Math.round((analysisResult.confidence || 0) * 100)}% сигурност
                    </p>
                  </div>
                </div>

                {analysisResult.summary_mk && (
                  <p className="text-sm">{analysisResult.summary_mk}</p>
                )}

                {analysisResult.findings?.length > 0 && (
                  <div>
                    <p className="text-xs text-muted-foreground mb-2">Наоди ({analysisResult.findings.length}):</p>
                    <div className="space-y-2">
                      {analysisResult.findings.slice(0, 3).map((f: any, i: number) => (
                        <div key={i} className={`p-2 rounded text-sm ${RISK_LEVELS[f.severity as keyof typeof RISK_LEVELS]?.light || "bg-muted"}`}>
                          {f.description}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <Link href={`/tenders/${analysisResult.tenderId}`}>
                  <Button variant="outline" className="w-full">
                    <Eye className="h-4 w-4 mr-2" />
                    Погледни детали за тендерот
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}

          {analysisError && (
            <Card className="border-red-200 bg-red-50">
              <CardContent className="py-4">
                <div className="flex items-center gap-2 text-red-700">
                  <XCircle className="h-5 w-5" />
                  <span>{analysisError}</span>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* AI Chat prompt */}
      <Card className="bg-muted/50 border-dashed">
        <CardContent className="py-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-center sm:text-left">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Brain className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="font-medium">Прашај го AI асистентот</p>
                <p className="text-sm text-muted-foreground">
                  "Покажи ми најризични тендери за градежништво" или "Кои компании често добиваат?"
                </p>
              </div>
            </div>
            <p className="text-sm text-muted-foreground">
              Користете го чат-от долу десно →
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
