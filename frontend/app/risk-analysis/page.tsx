"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  Building2,
  Brain,
  Shield,
  Search,
  Activity,
  Eye,
  RefreshCw,
  Zap,
  Users,
  Repeat,
  DollarSign,
  Timer,
  FileWarning,
  FileText,
  Link2,
  Radar,
  Loader2
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { api } from "@/lib/api";
import Link from "next/link";

const API_URL = typeof window !== 'undefined'
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : 'https://api.nabavkidata.com';

const RISK_LEVELS: Record<string, { bg: string; light: string; text: string; label: string }> = {
  critical: { bg: "bg-red-500", light: "bg-red-100", text: "text-red-700", label: "Критичен" },
  high: { bg: "bg-orange-500", light: "bg-orange-100", text: "text-orange-700", label: "Висок" },
  medium: { bg: "bg-yellow-500", light: "bg-yellow-100", text: "text-yellow-700", label: "Среден" },
  low: { bg: "bg-blue-500", light: "bg-blue-100", text: "text-blue-700", label: "Низок" },
  minimal: { bg: "bg-green-500", light: "bg-green-100", text: "text-green-700", label: "Минимален" }
};

const FLAG_TYPES: Record<string, { icon: typeof Users; label: string; description: string }> = {
  single_bidder: { icon: Users, label: "1 понудувач", description: "Само една компанија поднела понуда" },
  repeat_winner: { icon: Repeat, label: "Повторен победник", description: "Истата компанија често добива" },
  price_anomaly: { icon: DollarSign, label: "Ценовна аномалија", description: "Невообичаена цена" },
  bid_clustering: { icon: Link2, label: "Кластер понуди", description: "Сомнително координирани понуди" },
  short_deadline: { icon: Timer, label: "Краток рок", description: "Невообичаено кус рок за понуди" },
  high_amendments: { icon: FileWarning, label: "Многу измени", description: "Премногу амандмани" },
  spec_rigging: { icon: FileText, label: "Наместени спецификации", description: "Спецификации кои фаворизираат" },
  related_companies: { icon: Building2, label: "Поврзани компании", description: "Понудувачи со заедничко власништво" }
};

interface RiskFlag {
  flag_type: string;
  severity: string;
  score: number;
  description: string;
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
}

export default function RiskAnalysisPage() {
  const [mode, setMode] = useState<string>("flagged");
  const [riskyTenders, setRiskyTenders] = useState<RiskyTender[]>([]);
  const [loading, setLoading] = useState(true);
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [flagFilter, setFlagFilter] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Search mode
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any>(null);

  // Stats
  const [stats, setStats] = useState({ total: 0, critical: 0, high: 0, medium: 0, low: 0 });

  useEffect(() => {
    if (mode === "flagged") {
      loadFlaggedTenders();
    }
  }, [mode, riskFilter, flagFilter]);

  async function loadFlaggedTenders() {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "50", min_score: "1" });
      if (riskFilter !== "all") params.append("severity", riskFilter);
      if (flagFilter !== "all") params.append("flag_type", flagFilter);

      const res = await fetch(`${API_URL}/api/corruption/flagged-tenders?${params}`);
      if (!res.ok) throw new Error("API error");

      const data = await res.json();
      const mapped: RiskyTender[] = (data.tenders || []).map((t: any) => ({
        tender_id: t.tender_id,
        title: t.title || "Без наслов",
        procuring_entity: t.procuring_entity || "",
        estimated_value_mkd: parseFloat(t.estimated_value_mkd) || 0,
        winner: t.winner || "",
        risk_score: t.risk_score || 0,
        risk_level: t.risk_level || "medium",
        flag_count: t.total_flags || 0,
        flags: (t.flag_types || []).map((type: string) => ({
          flag_type: type,
          severity: t.max_severity || "medium",
          score: Math.round((t.risk_score || 0) / (t.total_flags || 1)),
          description: FLAG_TYPES[type]?.description || ""
        }))
      }));

      setRiskyTenders(mapped);
      setStats({
        total: data.total || mapped.length,
        critical: mapped.filter(t => t.risk_level === "critical").length,
        high: mapped.filter(t => t.risk_level === "high").length,
        medium: mapped.filter(t => t.risk_level === "medium").length,
        low: mapped.filter(t => t.risk_level === "low").length
      });
    } catch (err) {
      console.error("Failed to load:", err);
      // Fallback
      try {
        const res = await fetch(`${API_URL}/api/tenders?status=awarded&page=1&page_size=50`);
        const data = await res.json();
        const fallback: RiskyTender[] = (data.items || [])
          .filter((t: any) => t.num_bidders === 1)
          .slice(0, 30)
          .map((t: any) => ({
            tender_id: t.tender_id,
            title: t.title,
            procuring_entity: t.procuring_entity || "",
            estimated_value_mkd: parseFloat(t.estimated_value_mkd) || 0,
            winner: t.winner || "",
            risk_score: 65,
            risk_level: "high",
            flag_count: 1,
            flags: [{ flag_type: "single_bidder", severity: "high", score: 65, description: "Само еден понудувач" }]
          }));
        setRiskyTenders(fallback);
        setStats({ total: fallback.length, critical: 0, high: fallback.length, medium: 0, low: 0 });
      } catch (e) {
        console.error("Fallback failed:", e);
      }
    } finally {
      setLoading(false);
    }
  }

  async function searchTenders() {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    try {
      const data = await api.searchTenders({
        query: searchQuery.trim(),
        status: "awarded",
        page: 1,
        page_size: 50
      });
      setSearchResults(data.items || []);
    } catch (err) {
      console.error("Search failed:", err);
    } finally {
      setSearchLoading(false);
    }
  }

  async function analyzeTender(tenderId: string) {
    setAnalyzingId(tenderId);
    setAnalysisResult(null);
    try {
      const res = await fetch(`${API_URL}/api/risk/investigate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "tender", query: tenderId })
      });
      if (!res.ok) throw new Error("Analysis failed");
      const result = await res.json();
      setAnalysisResult({ tenderId, ...result });
    } catch (err) {
      console.error("Analysis error:", err);
    } finally {
      setAnalyzingId(null);
    }
  }

  function getRiskConfig(level: string) {
    return RISK_LEVELS[level] || RISK_LEVELS.medium;
  }

  function handleExpand(id: string) {
    setExpandedId(expandedId === id ? null : id);
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="h-6 w-6 text-primary" />
          AI Детекција на Ризици
        </h1>
        <p className="text-muted-foreground">
          Автоматска анализа на тендери за корупциски индикатори
        </p>
      </div>

      {/* Tabs */}
      <Tabs value={mode} onValueChange={setMode}>
        <TabsList className="grid w-full grid-cols-2 max-w-md">
          <TabsTrigger value="flagged" className="gap-2">
            <Radar className="h-4 w-4" />
            Детектирани ризици
          </TabsTrigger>
          <TabsTrigger value="search" className="gap-2">
            <Search className="h-4 w-4" />
            Пребарај тендери
          </TabsTrigger>
        </TabsList>

        {/* FLAGGED TAB */}
        <TabsContent value="flagged" className="space-y-6 mt-6">
          {/* Stats */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Card>
              <CardContent className="p-4 flex items-center gap-3">
                <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
                  <Activity className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-bold">{stats.total}</p>
                  <p className="text-xs text-muted-foreground">Вкупно</p>
                </div>
              </CardContent>
            </Card>
            {(["critical", "high", "medium", "low"] as const).map(level => {
              const cfg = RISK_LEVELS[level];
              const count = stats[level];
              return (
                <Card
                  key={level}
                  className={`cursor-pointer hover:ring-2 hover:ring-primary/30 ${riskFilter === level ? "ring-2 ring-primary" : ""}`}
                  onClick={() => setRiskFilter(riskFilter === level ? "all" : level)}
                >
                  <CardContent className="p-4 flex items-center gap-3">
                    <div className={`h-10 w-10 rounded-lg ${cfg.light} flex items-center justify-center`}>
                      <AlertTriangle className={`h-5 w-5 ${cfg.text}`} />
                    </div>
                    <div>
                      <p className="text-2xl font-bold">{count}</p>
                      <p className={`text-xs ${cfg.text}`}>{cfg.label}</p>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Info */}
          <Card className="bg-primary/5 border-primary/20">
            <CardContent className="p-4 flex items-center gap-3">
              <Zap className="h-6 w-6 text-primary" />
              <div>
                <p className="font-medium">AI автоматски детектира ризици</p>
                <p className="text-sm text-muted-foreground">
                  Овие тендери се означени како ризични од нашите AI агенти
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Filters */}
          <div className="flex flex-wrap gap-3">
            <Select value={riskFilter} onValueChange={(val) => setRiskFilter(val)}>
              <SelectTrigger className="w-[150px]">
                <SelectValue placeholder="Ниво на ризик" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Сите ризици</SelectItem>
                <SelectItem value="critical">Критичен</SelectItem>
                <SelectItem value="high">Висок</SelectItem>
                <SelectItem value="medium">Среден</SelectItem>
                <SelectItem value="low">Низок</SelectItem>
              </SelectContent>
            </Select>

            <Select value={flagFilter} onValueChange={(val) => setFlagFilter(val)}>
              <SelectTrigger className="w-[170px]">
                <SelectValue placeholder="Тип на ризик" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Сите типови</SelectItem>
                {Object.entries(FLAG_TYPES).map(([key, val]) => (
                  <SelectItem key={key} value={key}>{val.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button variant="outline" onClick={() => loadFlaggedTenders()} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
              Освежи
            </Button>
          </div>

          {/* Risk Feed */}
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[1,2,3,4,5,6].map(i => (
                <Card key={i}>
                  <CardContent className="p-4 space-y-3">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-4 w-1/2" />
                    <Skeleton className="h-8 w-20" />
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : riskyTenders.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="py-12 text-center">
                <CheckCircle2 className="h-12 w-12 mx-auto text-green-500 mb-4" />
                <h3 className="font-medium text-lg">Нема детектирани ризици</h3>
                <p className="text-muted-foreground">
                  {riskFilter !== "all" || flagFilter !== "all"
                    ? "Пробајте други филтри"
                    : "Нема ризични тендери"}
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {riskyTenders.map(tender => {
                const cfg = getRiskConfig(tender.risk_level);
                const isOpen = expandedId === tender.tender_id;

                return (
                  <Card key={tender.tender_id} className={isOpen ? "ring-2 ring-primary" : ""}>
                    <div className={`h-1 ${cfg.bg}`} />
                    <CardContent className="p-4">
                      <div className="flex items-start gap-3 mb-3">
                        <div className="relative w-12 h-12">
                          <svg className="transform -rotate-90 w-12 h-12">
                            <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="4" fill="none" className="text-muted" />
                            <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="4" fill="none"
                              strokeDasharray={`${(tender.risk_score / 100) * 125} 125`}
                              className={cfg.bg.replace("bg-", "text-")}
                            />
                          </svg>
                          <span className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                            {tender.risk_score}
                          </span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <Badge className={`${cfg.light} ${cfg.text} border-0 mb-1`}>{cfg.label}</Badge>
                          <h3 className="font-medium text-sm line-clamp-2">{tender.title}</h3>
                          <p className="text-xs text-muted-foreground truncate">{tender.procuring_entity}</p>
                        </div>
                      </div>

                      <div className="flex items-center justify-between pt-3 border-t">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-[10px] font-mono">{tender.tender_id}</Badge>
                          {tender.estimated_value_mkd > 0 && (
                            <span className="text-xs font-medium text-primary">
                              {formatCurrency(tender.estimated_value_mkd)}
                            </span>
                          )}
                        </div>
                        <Button variant="ghost" size="sm" onClick={() => handleExpand(tender.tender_id)}>
                          {isOpen ? <>Затвори <ChevronUp className="h-4 w-4 ml-1" /></> : <>Детали <ChevronDown className="h-4 w-4 ml-1" /></>}
                        </Button>
                      </div>

                      {isOpen && (
                        <div className="mt-4 pt-4 border-t space-y-3">
                          {tender.winner && (
                            <div>
                              <p className="text-xs text-muted-foreground">Победник:</p>
                              <p className="text-sm font-medium">{tender.winner}</p>
                            </div>
                          )}
                          {tender.flags.length > 0 && (
                            <div>
                              <p className="text-xs text-muted-foreground mb-2">Ризици:</p>
                              {tender.flags.map((flag, i) => {
                                const flagCfg = FLAG_TYPES[flag.flag_type] || { icon: AlertTriangle, label: flag.flag_type };
                                const FlagIcon = flagCfg.icon;
                                return (
                                  <div key={i} className="p-2 rounded mb-1 bg-muted/50 border">
                                    <div className="flex items-center gap-2">
                                      <FlagIcon className="h-4 w-4 text-muted-foreground" />
                                      <span className="text-sm">{flagCfg.label}</span>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                          <div className="flex gap-2">
                            <Link href={`/tenders/${encodeURIComponent(tender.tender_id)}`} className="flex-1">
                              <Button variant="outline" size="sm" className="w-full">
                                <Eye className="h-4 w-4 mr-1" /> Тендер
                              </Button>
                            </Link>
                            {tender.winner && (
                              <Link href={`/suppliers?search=${encodeURIComponent(tender.winner)}`} className="flex-1">
                                <Button variant="outline" size="sm" className="w-full">
                                  <Building2 className="h-4 w-4 mr-1" /> Победник
                                </Button>
                              </Link>
                            )}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </TabsContent>

        {/* SEARCH TAB */}
        <TabsContent value="search" className="space-y-6 mt-6">
          <Card className="bg-blue-50 dark:bg-blue-950/20 border-blue-200">
            <CardContent className="p-4 flex items-center gap-3">
              <Search className="h-6 w-6 text-blue-600" />
              <div>
                <p className="font-medium">Пребарај било кој тендер</p>
                <p className="text-sm text-muted-foreground">
                  Пребарајте низ 100,000+ тендери и анализирајте ги за ризици
                </p>
              </div>
            </CardContent>
          </Card>

          <form onSubmit={(e) => { e.preventDefault(); searchTenders(); }} className="flex gap-2">
            <Input
              placeholder="Пребарај по назив, институција, CPV..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1"
            />
            <Button type="submit" disabled={searchLoading}>
              {searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            </Button>
          </form>

          {searchLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {[1,2,3].map(i => <Card key={i}><CardContent className="p-4"><Skeleton className="h-20" /></CardContent></Card>)}
            </div>
          ) : searchResults.length > 0 ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {searchResults.map((t: any) => (
                <Card key={t.tender_id} className={analyzingId === t.tender_id ? "ring-2 ring-primary animate-pulse" : ""}>
                  <CardContent className="p-4">
                    <h3 className="font-medium text-sm line-clamp-2 mb-2">{t.title}</h3>
                    <p className="text-xs text-muted-foreground truncate mb-2">{t.procuring_entity}</p>
                    <div className="flex items-center gap-2 mb-3">
                      <Badge variant="outline" className="text-[10px]">{t.tender_id}</Badge>
                      {t.num_bidders === 1 && <Badge variant="destructive" className="text-[10px]">1 понудувач</Badge>}
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => analyzeTender(t.tender_id)} disabled={analyzingId !== null} className="flex-1">
                        {analyzingId === t.tender_id ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Shield className="h-3 w-3 mr-1" />}
                        Анализирај
                      </Button>
                      <Link href={`/tenders/${encodeURIComponent(t.tender_id)}`}>
                        <Button variant="outline" size="sm"><Eye className="h-3 w-3" /></Button>
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : searchQuery && !searchLoading ? (
            <Card className="border-dashed">
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">Нема резултати за "{searchQuery}"</p>
              </CardContent>
            </Card>
          ) : null}

          {analysisResult && (
            <Card className="border-2 border-primary">
              <div className={`h-1.5 ${getRiskConfig(analysisResult.risk_level).bg}`} />
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Резултат од анализа</CardTitle>
                  <Button variant="ghost" size="sm" onClick={() => setAnalysisResult(null)}>
                    <XCircle className="h-4 w-4" />
                  </Button>
                </div>
                <CardDescription>{analysisResult.tenderId}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-4 mb-4">
                  <div className="text-3xl font-bold">{analysisResult.risk_score}</div>
                  <Badge className={`${getRiskConfig(analysisResult.risk_level).light} ${getRiskConfig(analysisResult.risk_level).text}`}>
                    {getRiskConfig(analysisResult.risk_level).label} ризик
                  </Badge>
                </div>
                {analysisResult.summary_mk && <p className="text-sm mb-4">{analysisResult.summary_mk}</p>}
                <Link href={`/tenders/${encodeURIComponent(analysisResult.tenderId)}`}>
                  <Button variant="outline" className="w-full"><Eye className="h-4 w-4 mr-2" /> Погледни тендер</Button>
                </Link>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Chat hint */}
      <Card className="bg-muted/50 border-dashed">
        <CardContent className="py-6 flex items-center gap-4">
          <Brain className="h-8 w-8 text-primary" />
          <div>
            <p className="font-medium">Прашај го AI асистентот</p>
            <p className="text-sm text-muted-foreground">
              Користете го чат-от долу десно за прашања за ризици
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
