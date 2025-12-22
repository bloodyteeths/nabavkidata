"use client";

import { useState, useEffect, useCallback } from "react";
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
  ChevronLeft,
  ChevronRight,
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
  Loader2,
  Info,
  Scale,
  ClipboardCheck,
  Download,
  Printer,
  ChevronsLeft,
  ChevronsRight
} from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { formatCurrency } from "@/lib/utils";
import { api } from "@/lib/api";
import Link from "next/link";
import { useDebounce } from "@/hooks/use-debounce";

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
  evidence?: Record<string, any>;
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

const PAGE_SIZE = 24;

export default function RiskAnalysisPage() {
  const [mode, setMode] = useState<string>("flagged");
  const [riskyTenders, setRiskyTenders] = useState<RiskyTender[]>([]);
  const [loading, setLoading] = useState(true);
  const [riskFilter, setRiskFilter] = useState<string>("all");
  const [flagFilter, setFlagFilter] = useState<string>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailedAnalysis, setDetailedAnalysis] = useState<Record<string, any>>({});
  const [loadingDetail, setLoadingDetail] = useState<string | null>(null);

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const totalPages = Math.ceil(totalItems / PAGE_SIZE);

  // Search
  const [searchInput, setSearchInput] = useState("");
  const [winnerInput, setWinnerInput] = useState("");
  const debouncedSearch = useDebounce(searchInput, 300);
  const debouncedWinner = useDebounce(winnerInput, 300);

  // Stats (loaded separately)
  const [stats, setStats] = useState<{
    total: number;
    by_severity: Record<string, number>;
    by_type: Record<string, number>;
  } | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Investigation workflow
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [reviewNotes, setReviewNotes] = useState<string>("");
  const [reviewStatus, setReviewStatus] = useState<Record<string, { status: string; notes: string }>>({});
  const [submittingReview, setSubmittingReview] = useState(false);

  // Search mode
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any>(null);
  const [searchPage, setSearchPage] = useState(1);
  const [searchTotal, setSearchTotal] = useState(0);
  const [searchResultsPerPage] = useState(18);
  const [searchStatusFilter, setSearchStatusFilter] = useState<string>("all");

  // Load stats separately (cached)
  useEffect(() => {
    async function loadStats() {
      try {
        const res = await fetch(`${API_URL}/api/corruption/stats`);
        if (res.ok) {
          const data = await res.json();
          setStats({
            total: data.total_tenders_flagged || 0,
            by_severity: data.by_severity || {},
            by_type: data.by_type || {}
          });
        }
      } catch (err) {
        console.error("Failed to load stats:", err);
      } finally {
        setStatsLoading(false);
      }
    }
    loadStats();
  }, []);

  // Load flagged tenders with pagination
  useEffect(() => {
    if (mode === "flagged") {
      loadFlaggedTenders();
    }
  }, [mode, riskFilter, flagFilter, currentPage, debouncedSearch, debouncedWinner]);

  // Reset page when filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [riskFilter, flagFilter, debouncedSearch, debouncedWinner]);

  // Trigger search when page or filter changes (for search tab)
  useEffect(() => {
    if (mode === "search" && searchQuery && searchResults.length > 0) {
      searchTenders();
    }
  }, [searchPage, searchStatusFilter]);

  async function loadFlaggedTenders() {
    setLoading(true);
    try {
      const skip = (currentPage - 1) * PAGE_SIZE;
      const params = new URLSearchParams({
        limit: String(PAGE_SIZE),
        skip: String(skip),
        min_score: "1"
      });

      if (riskFilter !== "all") params.append("severity", riskFilter);
      if (flagFilter !== "all") params.append("flag_type", flagFilter);
      if (debouncedSearch) params.append("institution", debouncedSearch);
      if (debouncedWinner) params.append("winner", debouncedWinner);

      const res = await fetch(`${API_URL}/api/corruption/flagged-tenders?${params}`);
      if (!res.ok) throw new Error("API error");

      const data = await res.json();
      setTotalItems(data.total || 0);

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
    } catch (err) {
      console.error("Failed to load:", err);
      setRiskyTenders([]);
      setTotalItems(0);
    } finally {
      setLoading(false);
    }
  }

  async function searchTenders() {
    if (!searchQuery.trim()) return;
    setSearchLoading(true);
    try {
      // Search tenders - backend searches title, description, procuring_entity, and CPV code
      const data = await api.searchTenders({
        query: searchQuery.trim(),
        status: searchStatusFilter === "all" ? undefined : searchStatusFilter,
        page: searchPage,
        page_size: searchResultsPerPage,
        sort_by: "created_at",
        sort_order: "desc"
      });
      setSearchResults(data.items || []);
      setSearchTotal(data.total || 0);
    } catch (err) {
      console.error("Search failed:", err);
      setSearchResults([]);
      setSearchTotal(0);
    } finally {
      setSearchLoading(false);
    }
  }

  async function analyzeTender(tenderId: string) {
    setAnalyzingId(tenderId);
    setAnalysisResult(null);
    try {
      // Get auth token from localStorage
      const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
      if (!token) {
        alert("Ве молиме најавете се за да користите AI анализа");
        return;
      }

      const res = await fetch(`${API_URL}/api/risk/investigate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ type: "tender", query: tenderId })
      });

      if (res.status === 401) {
        alert("Ве молиме најавете се за да користите AI анализа");
        return;
      }

      if (res.status === 429) {
        const error = await res.json();
        alert(error.detail?.message || "Премногу барања. Ве молиме почекајте.");
        return;
      }

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Analysis failed");
      }

      const result = await res.json();
      setAnalysisResult({ tenderId, ...result });
    } catch (err: any) {
      console.error("Analysis error:", err);
      alert(`Грешка при анализа: ${err.message}`);
    } finally {
      setAnalyzingId(null);
    }
  }

  function getRiskConfig(level: string) {
    return RISK_LEVELS[level] || RISK_LEVELS.medium;
  }

  async function handleExpand(id: string) {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);

    if (!detailedAnalysis[id]) {
      setLoadingDetail(id);
      try {
        const res = await fetch(`${API_URL}/api/corruption/tender/${encodeURIComponent(id)}/analysis`);
        if (res.ok) {
          const data = await res.json();
          setDetailedAnalysis(prev => ({ ...prev, [id]: data }));
        }
      } catch (err) {
        console.error("Failed to load detailed analysis:", err);
      } finally {
        setLoadingDetail(null);
      }
    }
  }

  async function submitReview(tenderId: string, flagId: string, isFalsePositive: boolean) {
    if (!reviewNotes.trim()) {
      alert("Потребни се белешки за ревизијата");
      return;
    }

    setSubmittingReview(true);
    try {
      const res = await fetch(`${API_URL}/api/corruption/flags/${flagId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          false_positive: isFalsePositive,
          review_notes: reviewNotes
        })
      });

      if (res.ok) {
        setReviewStatus(prev => ({
          ...prev,
          [tenderId]: {
            status: isFalsePositive ? "dismissed" : "confirmed",
            notes: reviewNotes
          }
        }));
        setReviewingId(null);
        setReviewNotes("");
        loadFlaggedTenders();
      } else {
        alert("Грешка при зачувување на ревизијата");
      }
    } catch (err) {
      console.error("Review submission failed:", err);
      alert("Грешка при зачувување на ревизијата");
    } finally {
      setSubmittingReview(false);
    }
  }

  function exportToCSV() {
    const headers = ["tender_id", "title", "procuring_entity", "winner", "estimated_value_mkd", "risk_score", "risk_level", "flag_types", "source_url"];
    const rows = riskyTenders.map(t => {
      // Translate risk level to Macedonian
      const riskLevelMk = RISK_LEVELS[t.risk_level]?.label || t.risk_level;

      // Translate flag types to Macedonian
      const flagTypesMk = t.flags.map(f => FLAG_TYPES[f.flag_type]?.label || f.flag_type).join("; ");

      // Format currency value
      const formattedValue = t.estimated_value_mkd ? formatCurrency(t.estimated_value_mkd) : "";

      // Generate source URL
      const sourceUrl = `https://e-nabavki.gov.mk/PublicAccess/home.aspx#/dossie/${encodeURIComponent(t.tender_id)}`;

      return [
        t.tender_id,
        `"${t.title.replace(/"/g, '""')}"`,
        `"${(t.procuring_entity || "").replace(/"/g, '""')}"`,
        `"${(t.winner || "").replace(/"/g, '""')}"`,
        formattedValue,
        t.risk_score,
        riskLevelMk,
        `"${flagTypesMk}"`,
        sourceUrl
      ];
    });

    const csv = [headers.join(","), ...rows.map(r => r.join(","))].join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `risky_tenders_${new Date().toISOString().split("T")[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  // Pagination component
  function Pagination() {
    if (totalPages <= 1) return null;

    const pages: (number | string)[] = [];
    const showPages = 5;

    if (totalPages <= showPages + 2) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (currentPage > 3) pages.push("...");

      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);

      for (let i = start; i <= end; i++) pages.push(i);

      if (currentPage < totalPages - 2) pages.push("...");
      pages.push(totalPages);
    }

    return (
      <div className="flex items-center justify-center gap-1 mt-6">
        <Button
          variant="outline"
          size="sm"
          onClick={() => setCurrentPage(1)}
          disabled={currentPage === 1}
        >
          <ChevronsLeft className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
          disabled={currentPage === 1}
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>

        {pages.map((page, i) =>
          page === "..." ? (
            <span key={`ellipsis-${i}`} className="px-2">...</span>
          ) : (
            <Button
              key={page}
              variant={currentPage === page ? "default" : "outline"}
              size="sm"
              onClick={() => setCurrentPage(page as number)}
              className="min-w-[36px]"
            >
              {page}
            </Button>
          )
        )}

        <Button
          variant="outline"
          size="sm"
          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
          disabled={currentPage === totalPages}
        >
          <ChevronRight className="h-4 w-4" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setCurrentPage(totalPages)}
          disabled={currentPage === totalPages}
        >
          <ChevronsRight className="h-4 w-4" />
        </Button>

        <span className="text-sm text-muted-foreground ml-4">
          {((currentPage - 1) * PAGE_SIZE) + 1}-{Math.min(currentPage * PAGE_SIZE, totalItems)} од {totalItems.toLocaleString()}
        </span>
      </div>
    );
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

      {/* Legal Disclaimer */}
      <Card className="border-blue-200 bg-blue-50 dark:bg-blue-900/10 dark:border-blue-700">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <Scale className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
            <div className="text-sm">
              <p className="font-medium text-blue-800 dark:text-blue-300 mb-1">
                Правна напомена
              </p>
              <p className="text-blue-700 dark:text-blue-300 leading-relaxed">
                Оваа анализа е генерирана автоматски од AI алгоритми и служи <strong>исклучиво за информативни цели</strong>.
                Означувањето на тендер како „ризичен" <strong>не претставува доказ</strong> за незаконски дејствија.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

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
                  {statsLoading ? (
                    <Skeleton className="h-8 w-16" />
                  ) : (
                    <p className="text-2xl font-bold">{(stats?.total || totalItems).toLocaleString()}</p>
                  )}
                  <p className="text-xs text-muted-foreground">Вкупно</p>
                </div>
              </CardContent>
            </Card>
            {(["critical", "high", "medium", "low"] as const).map(level => {
              const cfg = RISK_LEVELS[level];
              const count = stats?.by_severity?.[level] || 0;
              return (
                <Card
                  key={level}
                  className={`cursor-pointer hover:ring-2 hover:ring-primary/30 transition-all ${riskFilter === level ? "ring-2 ring-primary" : ""}`}
                  onClick={() => setRiskFilter(riskFilter === level ? "all" : level)}
                >
                  <CardContent className="p-4 flex items-center gap-3">
                    <div className={`h-10 w-10 rounded-lg ${cfg.light} flex items-center justify-center`}>
                      <AlertTriangle className={`h-5 w-5 ${cfg.text}`} />
                    </div>
                    <div>
                      {statsLoading ? (
                        <Skeleton className="h-8 w-12" />
                      ) : (
                        <p className="text-2xl font-bold">{count.toLocaleString()}</p>
                      )}
                      <p className={`text-xs ${cfg.text}`}>{cfg.label}</p>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Search and Filters */}
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Пребарај институција (кирилица или латиница)..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                className="pl-9"
              />
            </div>

            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Building2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Пребарај по компанија..."
                value={winnerInput}
                onChange={(e) => setWinnerInput(e.target.value)}
                className="pl-9"
              />
            </div>

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

            <div className="flex-1" />

            <Button variant="outline" onClick={exportToCSV} disabled={riskyTenders.length === 0}>
              <Download className="h-4 w-4 mr-2" />
              CSV
            </Button>
          </div>

          {/* Current filter info */}
          {(riskFilter !== "all" || flagFilter !== "all" || searchInput || winnerInput) && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Филтри:</span>
              {riskFilter !== "all" && (
                <Badge variant="secondary" className="gap-1">
                  {RISK_LEVELS[riskFilter]?.label}
                  <XCircle className="h-3 w-3 cursor-pointer" onClick={() => setRiskFilter("all")} />
                </Badge>
              )}
              {flagFilter !== "all" && (
                <Badge variant="secondary" className="gap-1">
                  {FLAG_TYPES[flagFilter]?.label}
                  <XCircle className="h-3 w-3 cursor-pointer" onClick={() => setFlagFilter("all")} />
                </Badge>
              )}
              {searchInput && (
                <Badge variant="secondary" className="gap-1">
                  Институција: "{searchInput}"
                  <XCircle className="h-3 w-3 cursor-pointer" onClick={() => setSearchInput("")} />
                </Badge>
              )}
              {winnerInput && (
                <Badge variant="secondary" className="gap-1">
                  Компанија: "{winnerInput}"
                  <XCircle className="h-3 w-3 cursor-pointer" onClick={() => setWinnerInput("")} />
                </Badge>
              )}
              <Button variant="ghost" size="sm" onClick={() => { setRiskFilter("all"); setFlagFilter("all"); setSearchInput(""); setWinnerInput(""); }}>
                Исчисти
              </Button>
            </div>
          )}

          {/* Risk Feed */}
          {loading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {Array.from({ length: PAGE_SIZE }).map((_, i) => (
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
                  {riskFilter !== "all" || flagFilter !== "all" || searchInput || winnerInput
                    ? "Пробајте други филтри"
                    : "Нема ризични тендери"}
                </p>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {riskyTenders.map(tender => {
                  const cfg = getRiskConfig(tender.risk_level);
                  const isOpen = expandedId === tender.tender_id;

                  return (
                    <Card key={tender.tender_id} className={`transition-all ${isOpen ? "ring-2 ring-primary md:col-span-2" : ""}`}>
                      <div className={`h-1 ${cfg.bg}`} />
                      <CardContent className="p-4">
                        <div
                          className="flex items-start gap-3 mb-3 cursor-pointer hover:bg-muted/50 -m-1 p-1 rounded transition-colors"
                          onClick={() => handleExpand(tender.tender_id)}
                        >
                          <div className="relative w-12 h-12 flex-shrink-0">
                            <svg className="transform -rotate-90 w-12 h-12">
                              <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="4" fill="none" className="text-muted" />
                              <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="4" fill="none"
                                strokeDasharray={`${(Math.min(tender.risk_score, 100) / 100) * 125} 125`}
                                className={cfg.bg.replace("bg-", "text-")}
                              />
                            </svg>
                            <span className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                              {Math.min(tender.risk_score, 100)}
                            </span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <Badge className={`${cfg.light} ${cfg.text} border-0 mb-1`}>{cfg.label}</Badge>
                            <h3 className="font-medium text-sm line-clamp-2">{tender.title}</h3>
                            <p className="text-xs text-muted-foreground truncate">{tender.procuring_entity}</p>
                          </div>
                          <div className="flex items-center flex-shrink-0">
                            {isOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-3 border-t">
                          <div className="flex items-center gap-2 min-w-0">
                            <Badge variant="outline" className="text-[10px] font-mono shrink-0">{tender.tender_id}</Badge>
                            {tender.estimated_value_mkd > 0 && (
                              <span className="text-xs font-medium text-primary truncate">
                                {formatCurrency(tender.estimated_value_mkd)}
                              </span>
                            )}
                          </div>
                        </div>

                        {isOpen && (
                          <div className="mt-4 pt-4 border-t space-y-3">
                            {tender.winner && (
                              <div>
                                <p className="text-xs text-muted-foreground">Победник:</p>
                                <p className="text-sm font-medium">{tender.winner}</p>
                              </div>
                            )}

                            {loadingDetail === tender.tender_id ? (
                              <div className="flex items-center gap-2 py-4 justify-center">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span className="text-sm text-muted-foreground">Вчитување детали...</span>
                              </div>
                            ) : detailedAnalysis[tender.tender_id]?.flags?.length > 0 ? (
                              <div>
                                <p className="text-xs text-muted-foreground mb-2">Детални ризици:</p>
                                {detailedAnalysis[tender.tender_id].flags.slice(0, 3).map((flag: any, i: number) => {
                                  const flagCfg = FLAG_TYPES[flag.flag_type] || { icon: AlertTriangle, label: flag.flag_type };
                                  const FlagIcon = flagCfg.icon;
                                  const severityCfg = RISK_LEVELS[flag.severity] || RISK_LEVELS.medium;

                                  return (
                                    <div key={i} className={`p-2 rounded mb-2 ${severityCfg.light}`}>
                                      <div className="flex items-center gap-2">
                                        <FlagIcon className={`h-4 w-4 ${severityCfg.text}`} />
                                        <span className="text-sm font-medium">{flagCfg.label}</span>
                                        <span className="ml-auto text-xs font-mono">{flag.score} pts</span>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            ) : tender.flags.length > 0 && (
                              <div>
                                <p className="text-xs text-muted-foreground mb-2">Ризици:</p>
                                {tender.flags.map((flag, i) => {
                                  const flagCfg = FLAG_TYPES[flag.flag_type] || { icon: AlertTriangle, label: flag.flag_type };
                                  const FlagIcon = flagCfg.icon;
                                  return (
                                    <div key={i} className="p-2 rounded mb-1 bg-muted/50">
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
                              <Link href={`/tenders/${encodeURIComponent(tender.tender_id)}`} className="flex-1" target="_blank" rel="noopener noreferrer">
                                <Button variant="outline" size="sm" className="w-full">
                                  <Eye className="h-4 w-4 mr-1" /> Тендер
                                </Button>
                              </Link>
                              {tender.winner && (
                                <Link href={`/suppliers?search=${encodeURIComponent(tender.winner)}`} className="flex-1" target="_blank" rel="noopener noreferrer">
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

              <Pagination />
            </>
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
                  Пребарајте низ 270,000+ тендери и анализирајте ги за ризици
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="space-y-3">
            <form onSubmit={(e) => { e.preventDefault(); setSearchPage(1); searchTenders(); }} className="flex gap-2">
              <Input
                placeholder="Пребарај по назив, институција, CPV код, производ..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1"
              />
              <Select value={searchStatusFilter} onValueChange={(val) => { setSearchStatusFilter(val); setSearchPage(1); }}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Статус" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Сите</SelectItem>
                  <SelectItem value="active">Активни</SelectItem>
                  <SelectItem value="awarded">Доделени</SelectItem>
                  <SelectItem value="cancelled">Откажани</SelectItem>
                </SelectContent>
              </Select>
              <Button type="submit" disabled={searchLoading}>
                {searchLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              </Button>
            </form>

            {searchTotal > 0 && !searchLoading && (
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>Пронајдени {searchTotal.toLocaleString()} резултати</span>
                {searchTotal > searchResultsPerPage && (
                  <span>Страна {searchPage} од {Math.ceil(searchTotal / searchResultsPerPage)}</span>
                )}
              </div>
            )}
          </div>

          {searchLoading ? (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => <Card key={i}><CardContent className="p-4"><Skeleton className="h-24" /></CardContent></Card>)}
            </div>
          ) : searchResults.length > 0 ? (
            <>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {searchResults.map((t: any) => (
                  <Card key={t.tender_id} className={analyzingId === t.tender_id ? "ring-2 ring-primary animate-pulse" : ""}>
                    <CardContent className="p-4">
                      <div className="flex items-start gap-2 mb-2">
                        <h3 className="font-medium text-sm line-clamp-2 flex-1">{t.title}</h3>
                        {t.status && (
                          <Badge variant={t.status === 'active' ? 'default' : t.status === 'awarded' ? 'secondary' : 'outline'} className="text-[9px] shrink-0">
                            {t.status}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground truncate mb-2">{t.procuring_entity}</p>
                      <div className="flex items-center gap-2 mb-3 flex-wrap">
                        <Badge variant="outline" className="text-[10px] font-mono">{t.tender_id}</Badge>
                        {t.num_bidders === 1 && <Badge variant="destructive" className="text-[10px]">1 понудувач</Badge>}
                        {t.cpv_code && <Badge variant="outline" className="text-[9px]">{t.cpv_code.substring(0, 8)}</Badge>}
                      </div>
                      {t.estimated_value_mkd && (
                        <p className="text-xs font-medium text-primary mb-2">{formatCurrency(t.estimated_value_mkd)}</p>
                      )}
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => analyzeTender(t.tender_id)} disabled={analyzingId !== null} className="flex-1">
                          {analyzingId === t.tender_id ? <Loader2 className="h-3 w-3 animate-spin mr-1" /> : <Shield className="h-3 w-3 mr-1" />}
                          Анализирај
                        </Button>
                        <Link href={`/tenders/${encodeURIComponent(t.tender_id)}`} target="_blank" rel="noopener noreferrer">
                          <Button variant="outline" size="sm"><Eye className="h-3 w-3" /></Button>
                        </Link>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Search Pagination */}
              {searchTotal > searchResultsPerPage && (
                <div className="flex items-center justify-center gap-2 mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => { setSearchPage(1); }}
                    disabled={searchPage === 1}
                  >
                    <ChevronsLeft className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => { setSearchPage(p => Math.max(1, p - 1)); }}
                    disabled={searchPage === 1}
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <span className="px-3 text-sm">
                    {searchPage} / {Math.ceil(searchTotal / searchResultsPerPage)}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => { setSearchPage(p => Math.min(Math.ceil(searchTotal / searchResultsPerPage), p + 1)); }}
                    disabled={searchPage >= Math.ceil(searchTotal / searchResultsPerPage)}
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => { setSearchPage(Math.ceil(searchTotal / searchResultsPerPage)); }}
                    disabled={searchPage >= Math.ceil(searchTotal / searchResultsPerPage)}
                  >
                    <ChevronsRight className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </>
          ) : searchQuery && !searchLoading ? (
            <Card className="border-dashed">
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">Нема резултати за "{searchQuery}"</p>
                <p className="text-xs text-muted-foreground mt-2">Пробајте со друг термин за пребарување или статус филтер</p>
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
                  <div className="text-3xl font-bold">{Math.min(analysisResult.risk_score, 100)}<span className="text-lg text-muted-foreground">/100</span></div>
                  <Badge className={`${getRiskConfig(analysisResult.risk_level).light} ${getRiskConfig(analysisResult.risk_level).text}`}>
                    {getRiskConfig(analysisResult.risk_level).label} ризик
                  </Badge>
                </div>
                {analysisResult.summary_mk && <p className="text-sm mb-4">{analysisResult.summary_mk}</p>}
                <Link href={`/tenders/${encodeURIComponent(analysisResult.tenderId)}`} target="_blank" rel="noopener noreferrer">
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
