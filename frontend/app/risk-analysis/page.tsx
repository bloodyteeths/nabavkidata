"use client";

// Phase 4: Network Intelligence & Investigation Platform
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
  FileWarning,
  FileText,
  Loader2,
  Info,
  Scale,
  Download,
  ChevronsLeft,
  ChevronsRight,
  Network,
  TrendingUp,
  TrendingDown,
  GitBranch,
  Target,
  Lightbulb,
  Cpu,
  Gauge,
  User,
  Trophy,
  Clock,
  Copy,
  UserMinus,
  Scissors,
  UserX,
  FileEdit
} from "lucide-react";
import { formatCurrency } from "@/lib/utils";
import { api } from "@/lib/api";
import Link from "next/link";
import { useDebounce } from "@/hooks/use-debounce";
import { TenderExplanation } from "@/components/explainability/TenderExplanation";
import { GraphExplorer } from "@/components/corruption/GraphExplorer";
import { AlertsFeed } from "@/components/corruption/AlertsFeed";

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

const FLAG_TYPES: Record<string, { icon: typeof Users; label: string; description: string; color: string }> = {
  // Original 5 indicators
  single_bidder: { icon: User, label: "1 понудувач", description: "Само една компанија поднела понуда", color: "text-amber-500 bg-amber-50 dark:bg-amber-900/20" },
  repeat_winner: { icon: Trophy, label: "Повторен победник", description: "Истата компанија често добива", color: "text-red-500 bg-red-50 dark:bg-red-900/20" },
  price_anomaly: { icon: TrendingDown, label: "Ценовна аномалија", description: "Невообичаена цена", color: "text-purple-500 bg-purple-50 dark:bg-purple-900/20" },
  bid_clustering: { icon: Users, label: "Кластер понуди", description: "Сомнително координирани понуди", color: "text-indigo-500 bg-indigo-50 dark:bg-indigo-900/20" },
  short_deadline: { icon: Clock, label: "Краток рок", description: "Невообичаено кус рок за понуди", color: "text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20" },
  // New 10 indicators
  procedure_type: { icon: FileWarning, label: "Ризична постапка", description: "Необично избрана постапка за набавка", color: "text-slate-500 bg-slate-50 dark:bg-slate-900/20" },
  identical_bids: { icon: Copy, label: "Идентични понуди", description: "Понуди со сомнително слични вредности", color: "text-rose-600 bg-rose-50 dark:bg-rose-900/20" },
  professional_loser: { icon: UserMinus, label: "Покривач понудувач", description: "Компанија која систематски губи понуди", color: "text-zinc-500 bg-zinc-50 dark:bg-zinc-900/20" },
  contract_splitting: { icon: Scissors, label: "Делење договори", description: "Поделба на набавки за избегнување прагови", color: "text-emerald-600 bg-emerald-50 dark:bg-emerald-900/20" },
  short_decision: { icon: Zap, label: "Брза одлука", description: "Невообичаено брзо донесување одлука", color: "text-cyan-500 bg-cyan-50 dark:bg-cyan-900/20" },
  strategic_disqualification: { icon: UserX, label: "Стратешка дисквалификација", description: "Систематско елиминирање на конкуренти", color: "text-red-600 bg-red-50 dark:bg-red-900/20" },
  contract_value_growth: { icon: TrendingUp, label: "Раст на вредност", description: "Значително зголемување на договорна вредност", color: "text-orange-600 bg-orange-50 dark:bg-orange-900/20" },
  bid_rotation: { icon: RefreshCw, label: "Ротација понуди", description: "Компании наизменично добиваат тендери", color: "text-violet-500 bg-violet-50 dark:bg-violet-900/20" },
  threshold_manipulation: { icon: Target, label: "Манипулација на праг", description: "Вредности блиску до прагови за друга постапка", color: "text-teal-500 bg-teal-50 dark:bg-teal-900/20" },
  late_amendment: { icon: FileEdit, label: "Доцен амандман", description: "Измени во последен момент пред затворање", color: "text-amber-600 bg-amber-50 dark:bg-amber-900/20" },
  // Legacy types (kept for backward compat)
  high_amendments: { icon: FileWarning, label: "Многу измени", description: "Премногу амандмани", color: "text-orange-500 bg-orange-50 dark:bg-orange-900/20" },
  spec_rigging: { icon: FileText, label: "Наместени спецификации", description: "Спецификации кои фаворизираат", color: "text-red-500 bg-red-50 dark:bg-red-900/20" },
  related_companies: { icon: Building2, label: "Поврзани компании", description: "Понудувачи со заедничко власништво", color: "text-purple-500 bg-purple-50 dark:bg-purple-900/20" }
};

// CRI Score color and label based on 0-100 range (aligned with RISK_LEVELS)
function getCRIConfig(score: number): { color: string; bg: string; label: string } {
  if (score >= 80) return { color: "text-red-700", bg: "bg-red-500", label: "Критичен" };
  if (score >= 60) return { color: "text-orange-700", bg: "bg-orange-500", label: "Висок" };
  if (score >= 40) return { color: "text-yellow-700", bg: "bg-yellow-500", label: "Среден" };
  if (score >= 20) return { color: "text-blue-700", bg: "bg-blue-500", label: "Низок" };
  return { color: "text-green-700", bg: "bg-green-500", label: "Минимален" };
}

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
  has_winner: boolean;
  risk_score: number;
  risk_level: string;
  flag_count: number;
  flags: RiskFlag[];
}

interface CollusionCluster {
  cluster_id: string;
  num_companies: number;
  confidence: number;
  risk_level: string;
  pattern_type: string;
  top_companies: string[];
  companies?: string[];
  detection_method?: string;
}

interface CollusionStats {
  total_clusters: number;
  high_confidence_clusters: number;
  total_suspicious_companies: number;
  avg_cluster_size: number;
  largest_cluster_size: number;
  most_common_pattern: string;
}

interface CompanyRisk {
  company_name: string;
  probability: number;
  risk_level: string;
  prediction: number;
}

const PAGE_SIZE = 24;
const LEGACY_FLAG_TYPES = new Set(["high_amendments", "spec_rigging", "related_companies"]);
const ACTIVE_FLAG_COUNT = Object.keys(FLAG_TYPES).filter(k => !LEGACY_FLAG_TYPES.has(k)).length;

const STATUS_LABELS: Record<string, string> = {
  active: "Активен",
  awarded: "Доделен",
  cancelled: "Откажан",
  completed: "Завршен",
  planned: "Планиран",
};

const PATTERN_LABELS: Record<string, string> = {
  bid_clustering: "Групирање понуди",
  clique_detection: "Клика компании",
  community_detection: "Заедница",
  price_manipulation: "Ценовна манипулација",
  repeat_bidding: "Повторувачко понудување",
  unknown: "Непознат образец"
};

export default function RiskAnalysisPage() {
  const [tier, setTier] = useState<string>("free");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

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
  const [submittingReview, setSubmittingReview] = useState(false);

  // Collusion state
  const [collusionLoading, setCollusionLoading] = useState(false);
  const [collusionStats, setCollusionStats] = useState<CollusionStats | null>(null);
  const [collusionClusters, setCollusionClusters] = useState<CollusionCluster[]>([]);
  const [companyRisks, setCompanyRisks] = useState<CompanyRisk[]>([]);
  const [selectedCluster, setSelectedCluster] = useState<CollusionCluster | null>(null);

  // ML Explanation for individual tenders
  const [showMLExplanation, setShowMLExplanation] = useState<string | null>(null);

  // Check subscription tier
  useEffect(() => {
    async function checkAuth() {
      try {
        const status = await api.getSubscriptionStatus();
        setTier(status.tier || "free");
        setIsLoggedIn(true);
      } catch {
        setTier("free");
        setIsLoggedIn(false);
      } finally {
        setAuthChecked(true);
      }
    }
    checkAuth();
  }, []);

  // Load stats separately (cached)
  useEffect(() => {
    if (!authChecked || !isLoggedIn || !["professional", "enterprise"].includes(tier)) return;
    async function loadStats() {
      try {
        const token = localStorage.getItem('auth_token');
        const res = await fetch(`${API_URL}/api/corruption/stats`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: 'include',
        });
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
  }, [authChecked, isLoggedIn, tier]);

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

  // Load collusion data when tab is selected
  useEffect(() => {
    if (mode === "collusion" && collusionClusters.length === 0 && !collusionLoading) {
      loadCollusionData();
    }
  }, [mode]);

  async function loadCollusionData() {
    setCollusionLoading(true);
    try {
      const [statsRes, clustersRes, risksRes] = await Promise.all([
        api.getCollusionStats().catch(() => null),
        api.getCollusionClusters({ min_confidence: 50, limit: 50 }).catch(() => []),
        api.getCompanyRiskScores({ limit: 30, min_probability: 0.5 }).catch(() => [])
      ]);
      if (statsRes) setCollusionStats(statsRes);
      setCollusionClusters(clustersRes || []);
      setCompanyRisks(risksRes || []);
    } catch (err) {
      console.error("Failed to load collusion data:", err);
    } finally {
      setCollusionLoading(false);
    }
  }

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

      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API_URL}/api/corruption/flagged-tenders?${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
      });
      if (!res.ok) throw new Error("API error");

      const data = await res.json();
      setTotalItems(data.total || 0);

      const mapped: RiskyTender[] = (data.tenders || []).map((t: any) => ({
        tender_id: t.tender_id,
        title: t.title || "Без наслов",
        procuring_entity: t.procuring_entity || "",
        estimated_value_mkd: parseFloat(t.estimated_value_mkd) || 0,
        winner: t.winner || "",
        has_winner: t.has_winner !== false,
        risk_score: t.risk_score || 0,
        risk_level: t.risk_level || "medium",
        flag_count: t.total_flags || 0,
        flags: (t.flag_types || []).map((type: string) => ({
          flag_type: type,
          severity: t.max_severity || "medium",
          score: t.risk_score || 0,
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
        const token = localStorage.getItem('auth_token');
        const res = await fetch(`${API_URL}/api/corruption/tender/${encodeURIComponent(id)}/analysis`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          credentials: 'include',
        });
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
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API_URL}/api/corruption/flags/${flagId}/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({
          false_positive: isFalsePositive,
          review_notes: reviewNotes
        })
      });

      if (res.ok) {
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

  // Tier gate: Risk analysis requires Pro+
  if (!authChecked) {
    return (
      <div className="p-6 flex justify-center items-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isLoggedIn || !["professional", "enterprise"].includes(tier)) {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6 text-primary" />
            AI Систем за Детекција на Корупција
          </h1>
          <p className="text-sm text-muted-foreground">
            Напредна анализа со машинско учење
          </p>
        </div>
        <Card className="border-2 border-dashed">
          <CardContent className="py-12 flex flex-col items-center text-center space-y-4">
            <div className="p-4 bg-muted rounded-full">
              <Shield className="h-8 w-8 text-muted-foreground" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">Премиум функција</h2>
              <p className="text-muted-foreground mt-1 max-w-md">
                Анализата на ризик и детекцијата на корупција е достапна за корисници со Pro план или повисок.
                {!isLoggedIn && " Најавете се за да продолжите."}
              </p>
            </div>
            <div className="flex gap-3">
              {!isLoggedIn ? (
                <>
                  <Link href="/auth/login">
                    <Button>Најава</Button>
                  </Link>
                  <Link href="/auth/register">
                    <Button variant="outline">Регистрација</Button>
                  </Link>
                </>
              ) : (
                <Link href="/settings">
                  <Button>Надоградете план</Button>
                </Link>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="h-6 w-6 text-primary" />
          AI Систем за Детекција на Корупција
        </h1>
        <p className="text-muted-foreground">
          Напредна анализа со машинско учење: Random Forest, XGBoost, Graph Neural Networks
        </p>
        <div className="flex flex-wrap gap-2 mt-2">
          <Badge variant="outline" className="text-[10px]">
            <Cpu className="h-3 w-3 mr-1" /> ML Предвидување
          </Badge>
          <Badge variant="outline" className="text-[10px]">
            <Network className="h-3 w-3 mr-1" /> Детекција на мрежи
          </Badge>
          <Badge variant="outline" className="text-[10px]">
            <Lightbulb className="h-3 w-3 mr-1" /> SHAP/LIME објаснувања
          </Badge>
          <Badge variant="outline" className="text-[10px]">
            <Gauge className="h-3 w-3 mr-1" /> CRI ({ACTIVE_FLAG_COUNT} индикатори)
          </Badge>
        </div>
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
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="flagged" className="gap-2">
            <Shield className="h-4 w-4" />
            <span className="hidden sm:inline">Ризици</span>
          </TabsTrigger>
          <TabsTrigger value="collusion" className="gap-2">
            <Network className="h-4 w-4" />
            <span className="hidden sm:inline">Колузија</span>
          </TabsTrigger>
          <TabsTrigger value="networks" className="gap-2">
            <GitBranch className="h-4 w-4" />
            <span className="hidden sm:inline">Мрежи</span>
          </TabsTrigger>
          <TabsTrigger value="alerts" className="gap-2">
            <Activity className="h-4 w-4" />
            <span className="hidden sm:inline">Аларми</span>
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
              <SelectTrigger className="w-full sm:w-[150px]">
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
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Тип на ризик" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Сите типови ({ACTIVE_FLAG_COUNT})</SelectItem>
                {Object.entries(FLAG_TYPES)
                  .filter(([key]) => !LEGACY_FLAG_TYPES.has(key))
                  .map(([key, val]) => {
                    const FIcon = val.icon;
                    return (
                      <SelectItem key={key} value={key}>
                        <span className="flex items-center gap-2">
                          <FIcon className={`h-3.5 w-3.5 ${val.color.split(" ")[0]}`} />
                          {val.label}
                        </span>
                      </SelectItem>
                    );
                  })}
              </SelectContent>
            </Select>

            <Button variant="outline" onClick={() => loadFlaggedTenders()} disabled={loading}>
              <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
              Освежи
            </Button>

            <div className="flex-1" />

            <Button variant="outline" onClick={exportToCSV} disabled={riskyTenders.length === 0} title={`Извези ги прикажаните ${riskyTenders.length} тендери`}>
              <Download className="h-4 w-4 mr-2" />
              CSV ({riskyTenders.length})
            </Button>
          </div>

          {/* Current filter info */}
          {(riskFilter !== "all" || flagFilter !== "all" || searchInput || winnerInput) && (
            <div className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Филтри:</span>
              {riskFilter !== "all" && (
                <Badge variant="secondary" className="gap-1">
                  {RISK_LEVELS[riskFilter]?.label}
                  <button type="button" aria-label="Отстрани филтер" onClick={() => setRiskFilter("all")} className="focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary rounded-full">
                    <XCircle className="h-3 w-3" />
                  </button>
                </Badge>
              )}
              {flagFilter !== "all" && (
                <Badge variant="secondary" className="gap-1">
                  {FLAG_TYPES[flagFilter]?.label}
                  <button type="button" aria-label="Отстрани филтер" onClick={() => setFlagFilter("all")} className="focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary rounded-full">
                    <XCircle className="h-3 w-3" />
                  </button>
                </Badge>
              )}
              {searchInput && (
                <Badge variant="secondary" className="gap-1">
                  Институција: &quot;{searchInput}&quot;
                  <button type="button" aria-label="Отстрани филтер" onClick={() => setSearchInput("")} className="focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary rounded-full">
                    <XCircle className="h-3 w-3" />
                  </button>
                </Badge>
              )}
              {winnerInput && (
                <Badge variant="secondary" className="gap-1">
                  Компанија: &quot;{winnerInput}&quot;
                  <button type="button" aria-label="Отстрани филтер" onClick={() => setWinnerInput("")} className="focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary rounded-full">
                    <XCircle className="h-3 w-3" />
                  </button>
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
                          role="button"
                          tabIndex={0}
                          aria-expanded={isOpen}
                          className="flex items-start gap-3 mb-3 cursor-pointer hover:bg-muted/50 -m-1 p-1 rounded transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                          onClick={() => handleExpand(tender.tender_id)}
                          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleExpand(tender.tender_id); } }}
                        >
                          <div className="relative w-12 h-12 flex-shrink-0">
                            <svg className="transform -rotate-90 w-12 h-12">
                              <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="4" fill="none" className="text-muted" />
                              <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="4" fill="none"
                                strokeDasharray={`${(Math.min(tender.risk_score, 100) / 100) * 125} 125`}
                                className={getCRIConfig(tender.risk_score).bg.replace("bg-", "text-")}
                              />
                            </svg>
                            <span className="absolute inset-0 flex items-center justify-center text-xs font-bold">
                              {Math.min(tender.risk_score, 100)}
                            </span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-1.5 mb-1">
                              <Badge className={`${cfg.light} ${cfg.text} border-0`}>{cfg.label}</Badge>
                              <span className={`text-[10px] font-semibold ${getCRIConfig(tender.risk_score).color}`}>CRI</span>
                            </div>
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
                            {!tender.has_winner && (
                              <Badge variant="outline" className="text-[10px] shrink-0 bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400 dark:border-amber-800">
                                <Info className="h-3 w-3 mr-0.5" />Нецелосни податоци
                              </Badge>
                            )}
                            {tender.estimated_value_mkd > 0 && (
                              <span className="text-xs font-medium text-primary truncate">
                                {formatCurrency(tender.estimated_value_mkd)}
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-muted-foreground shrink-0">
                            {tender.flag_count}/{ACTIVE_FLAG_COUNT} индикатори
                          </span>
                        </div>

                        {isOpen && (
                          <div className="mt-4 pt-4 border-t space-y-3">
                            {tender.winner ? (
                              <div>
                                <p className="text-xs text-muted-foreground">Победник:</p>
                                <p className="text-sm font-medium">{tender.winner}</p>
                              </div>
                            ) : (
                              <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 rounded-md p-2">
                                <Info className="h-4 w-4 shrink-0" />
                                <p className="text-xs">Нема податоци за победник — анализата се базира само на структурни индикатори</p>
                              </div>
                            )}

                            {loadingDetail === tender.tender_id ? (
                              <div className="flex items-center gap-2 py-4 justify-center">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span className="text-sm text-muted-foreground">Вчитување детали...</span>
                              </div>
                            ) : detailedAnalysis[tender.tender_id]?.flags?.length > 0 ? (
                              <div>
                                <p className="text-xs text-muted-foreground mb-2">Детални ризици ({detailedAnalysis[tender.tender_id].flags.length}/{ACTIVE_FLAG_COUNT}):</p>
                                {detailedAnalysis[tender.tender_id].flags.slice(0, 5).map((flag: any, i: number) => {
                                  const flagCfg = FLAG_TYPES[flag.flag_type] || { icon: AlertTriangle, label: flag.flag_type, color: "text-muted-foreground bg-muted" };
                                  const FlagIcon = flagCfg.icon;
                                  const flagColor = flagCfg.color || "";

                                  return (
                                    <div key={i} className={`p-2 rounded mb-2 ${flagColor.split(" ").slice(1).join(" ")}`}>
                                      <div className="flex items-center gap-2">
                                        <FlagIcon className={`h-4 w-4 ${flagColor.split(" ")[0]}`} />
                                        <span className="text-sm font-medium">{flagCfg.label}</span>
                                        <span className="ml-auto text-xs font-mono">{flag.score} pts</span>
                                      </div>
                                    </div>
                                  );
                                })}
                                {detailedAnalysis[tender.tender_id].flags.length > 5 && (
                                  <p className="text-xs text-muted-foreground text-center">
                                    + уште {detailedAnalysis[tender.tender_id].flags.length - 5} индикатори
                                  </p>
                                )}
                              </div>
                            ) : tender.flags.length > 0 && (
                              <div>
                                <p className="text-xs text-muted-foreground mb-2">Ризици ({tender.flags.length}/{ACTIVE_FLAG_COUNT}):</p>
                                {tender.flags.map((flag, i) => {
                                  const flagCfg = FLAG_TYPES[flag.flag_type] || { icon: AlertTriangle, label: flag.flag_type, color: "text-muted-foreground bg-muted" };
                                  const FlagIcon = flagCfg.icon;
                                  const flagColor = flagCfg.color || "";
                                  return (
                                    <div key={i} className={`p-2 rounded mb-1 ${flagColor.split(" ").slice(1).join(" ")}`}>
                                      <div className="flex items-center gap-2">
                                        <FlagIcon className={`h-4 w-4 ${flagColor.split(" ")[0]}`} />
                                        <span className="text-sm">{flagCfg.label}</span>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}

                            {/* ML Explanation Toggle */}
                            <Button
                              variant={showMLExplanation === tender.tender_id ? "default" : "secondary"}
                              size="sm"
                              className="w-full mb-3"
                              onClick={() => setShowMLExplanation(showMLExplanation === tender.tender_id ? null : tender.tender_id)}
                            >
                              <Brain className="h-4 w-4 mr-2" />
                              {showMLExplanation === tender.tender_id ? "Сокриј AI анализа" : "Детална AI анализа"}
                            </Button>

                            {/* ML Explanation Component */}
                            {showMLExplanation === tender.tender_id && (
                              <div className="mb-3">
                                <TenderExplanation tenderId={tender.tender_id} compact={true} />
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


        <TabsContent value="networks" className="mt-6">
          <GraphExplorer />
        </TabsContent>

        {/* COLLUSION/NETWORKS TAB */}
        <TabsContent value="collusion" className="space-y-6 mt-6">
          <Card className="bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-950/20 dark:to-orange-950/20 border-red-200">
            <CardContent className="p-4 flex items-center gap-3">
              <Network className="h-6 w-6 text-red-600" />
              <div>
                <p className="font-medium">Мрежи на поврзани компании</p>
                <p className="text-sm text-muted-foreground">
                  AI детекција на групи компании кои можеби координираат понуди
                </p>
              </div>
            </CardContent>
          </Card>

          {collusionLoading ? (
            <div className="grid gap-4 md:grid-cols-2">
              {Array.from({ length: 4 }).map((_, i) => (
                <Card key={i}><CardContent className="p-4"><Skeleton className="h-32" /></CardContent></Card>
              ))}
            </div>
          ) : (
            <>
              {/* Collusion Stats */}
              {collusionStats && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                          <GitBranch className="h-5 w-5 text-red-600" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold">{collusionStats.total_clusters}</p>
                          <p className="text-xs text-muted-foreground">Детектирани мрежи</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-lg bg-orange-100 dark:bg-orange-900/30 flex items-center justify-center">
                          <AlertTriangle className="h-5 w-5 text-orange-600" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold">{collusionStats.high_confidence_clusters}</p>
                          <p className="text-xs text-muted-foreground">Висока сигурност</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                          <Users className="h-5 w-5 text-purple-600" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold">{collusionStats.total_suspicious_companies}</p>
                          <p className="text-xs text-muted-foreground">Сомнителни компании</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  <Card>
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                          <Activity className="h-5 w-5 text-blue-600" />
                        </div>
                        <div>
                          <p className="text-2xl font-bold">{collusionStats.avg_cluster_size.toFixed(1)}</p>
                          <p className="text-xs text-muted-foreground">Просечна големина</p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              )}

              <div className="grid md:grid-cols-2 gap-6">
                {/* Collusion Clusters */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Network className="h-5 w-5" />
                      Детектирани мрежи
                    </CardTitle>
                    <CardDescription>
                      Групи компании со сомнително координирање
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3 max-h-[400px] overflow-y-auto">
                      {collusionClusters.length > 0 ? (
                        collusionClusters.map((cluster) => (
                          <div
                            key={cluster.cluster_id}
                            className={`p-3 rounded-lg border cursor-pointer transition-all hover:bg-muted/50 ${selectedCluster?.cluster_id === cluster.cluster_id ? 'ring-2 ring-primary bg-muted/30' : ''}`}
                            onClick={() => setSelectedCluster(selectedCluster?.cluster_id === cluster.cluster_id ? null : cluster)}
                          >
                            <div className="flex items-center justify-between mb-2">
                              <div className="flex items-center gap-2">
                                <Badge variant={cluster.risk_level === 'critical' || cluster.risk_level === 'high' ? 'destructive' : 'secondary'}>
                                  {cluster.confidence.toFixed(0)}%
                                </Badge>
                                <span className="text-sm font-medium">{cluster.num_companies} компании</span>
                              </div>
                              <Badge variant="outline" className="text-[10px]">
                                {PATTERN_LABELS[cluster.pattern_type] || cluster.pattern_type}
                              </Badge>
                            </div>
                            <div className="text-xs text-muted-foreground line-clamp-2">
                              {cluster.top_companies?.slice(0, 3).join(', ')}
                              {cluster.top_companies && cluster.top_companies.length > 3 && ` и уште ${cluster.top_companies.length - 3}`}
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="text-center py-8 text-muted-foreground">
                          <Network className="h-8 w-8 mx-auto mb-2 opacity-50" />
                          <p>Нема детектирани мрежи</p>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* Selected Cluster Details or Risky Companies */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      {selectedCluster ? (
                        <>
                          <GitBranch className="h-5 w-5" />
                          Детали за мрежа
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="h-5 w-5 text-orange-500" />
                          Најризични компании
                        </>
                      )}
                    </CardTitle>
                    <CardDescription>
                      {selectedCluster
                        ? `${selectedCluster.num_companies} компании • ${selectedCluster.confidence.toFixed(0)}% сигурност`
                        : 'Компании со највисок ризик за сомнително однесување'
                      }
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {selectedCluster ? (
                      <div className="space-y-3">
                        <div className="flex flex-wrap gap-2 mb-4">
                          <Badge variant="outline">{PATTERN_LABELS[selectedCluster.pattern_type] || selectedCluster.pattern_type}</Badge>
                          <Badge className={RISK_LEVELS[selectedCluster.risk_level]?.light + ' ' + RISK_LEVELS[selectedCluster.risk_level]?.text + ' border-0'}>
                            {RISK_LEVELS[selectedCluster.risk_level]?.label || selectedCluster.risk_level}
                          </Badge>
                        </div>
                        <div className="space-y-2 max-h-[300px] overflow-y-auto">
                          {(selectedCluster.companies || selectedCluster.top_companies)?.map((company, i) => (
                            <div key={i} className="flex items-center gap-2 p-2 rounded bg-muted/50">
                              <Building2 className="h-4 w-4 text-muted-foreground" />
                              <span className="text-sm flex-1 truncate">{company}</span>
                              <Link href={`/suppliers?search=${encodeURIComponent(company)}`} target="_blank">
                                <Button variant="ghost" size="sm"><Eye className="h-3 w-3" /></Button>
                              </Link>
                            </div>
                          ))}
                        </div>
                        <Button variant="outline" className="w-full mt-4" onClick={() => setSelectedCluster(null)}>
                          Назад кон листа
                        </Button>
                      </div>
                    ) : (
                      <div className="space-y-2 max-h-[350px] overflow-y-auto">
                        {companyRisks.length > 0 ? (
                          companyRisks.map((company, i) => (
                            <div key={i} className="flex items-center gap-3 p-2 rounded border hover:bg-muted/50 transition-colors">
                              <div className="relative w-10 h-10 flex-shrink-0">
                                <svg className="transform -rotate-90 w-10 h-10">
                                  <circle cx="20" cy="20" r="16" stroke="currentColor" strokeWidth="3" fill="none" className="text-muted" />
                                  <circle cx="20" cy="20" r="16" stroke="currentColor" strokeWidth="3" fill="none"
                                    strokeDasharray={`${(company.probability) * 100} 100`}
                                    className={company.probability > 0.7 ? 'text-red-500' : company.probability > 0.5 ? 'text-orange-500' : 'text-yellow-500'}
                                  />
                                </svg>
                                <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold">
                                  {(company.probability * 100).toFixed(0)}
                                </span>
                              </div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium truncate">{company.company_name}</p>
                                <Badge variant="outline" className={`text-[9px] ${RISK_LEVELS[company.risk_level]?.text || ''}`}>
                                  {RISK_LEVELS[company.risk_level]?.label || company.risk_level}
                                </Badge>
                              </div>
                              <Link href={`/suppliers?search=${encodeURIComponent(company.company_name)}`} target="_blank">
                                <Button variant="ghost" size="sm"><Eye className="h-3 w-3" /></Button>
                              </Link>
                            </div>
                          ))
                        ) : (
                          <div className="text-center py-8 text-muted-foreground">
                            <Users className="h-8 w-8 mx-auto mb-2 opacity-50" />
                            <p>Нема податоци за компании</p>
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Refresh button */}
              <div className="flex justify-end">
                <Button variant="outline" onClick={loadCollusionData} disabled={collusionLoading}>
                  <RefreshCw className={`h-4 w-4 mr-2 ${collusionLoading ? 'animate-spin' : ''}`} />
                  Освежи податоци
                </Button>
              </div>
            </>
          )}
        </TabsContent>

        <TabsContent value="alerts" className="mt-6">
          <AlertsFeed />
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
