"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Search,
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
  Users,
  Newspaper,
  Clock,
  TrendingUp,
  ArrowRight,
  Sparkles,
  Eye,
  UserCheck,
  Banknote,
  AlertCircle,
  ChevronRight,
  ExternalLink
} from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import Link from "next/link";

// Agent definitions
const AGENTS = [
  { id: "db", name: "База", icon: Database },
  { id: "enabavki", name: "e-Набавки", icon: Globe },
  { id: "web", name: "Веб", icon: Newspaper },
  { id: "company", name: "Компании", icon: Building2 },
  { id: "documents", name: "Документи", icon: FileText },
  { id: "synthesis", name: "AI", icon: Brain }
];

const SEVERITY_CONFIG: Record<string, any> = {
  critical: { bg: "bg-red-100", text: "text-red-700", border: "border-red-200", label: "Критичен" },
  high: { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-200", label: "Висок" },
  medium: { bg: "bg-yellow-100", text: "text-yellow-700", border: "border-yellow-200", label: "Среден" },
  low: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-200", label: "Низок" }
};

interface Finding {
  source: string;
  type: string;
  description: string;
  severity: "low" | "medium" | "high" | "critical";
  evidence: string[];
  confidence?: number;
  corroborated?: boolean;
}

interface InvestigationResult {
  risk_score: number;
  risk_level: "minimal" | "low" | "medium" | "high" | "critical";
  confidence: number;
  findings: Finding[];
  sources_checked: { database: boolean; enabavki: boolean; web_search: boolean; company: boolean; documents: boolean };
  recommendations: string[];
  summary_mk: string;
  data_quality: { missing_info: string[] };
  investigated_at: string;
  cached: boolean;
}

interface TenderSuggestion {
  tender_id: string;
  title: string;
  estimated_value_mkd?: number;
  procuring_entity?: string;
  status?: string;
  winner?: string;
  num_bidders?: number;
}

export default function RiskAnalysisPage() {
  // Data states
  const [singleBidderTenders, setSingleBidderTenders] = useState<TenderSuggestion[]>([]);
  const [highValueTenders, setHighValueTenders] = useState<TenderSuggestion[]>([]);
  const [recentTenders, setRecentTenders] = useState<TenderSuggestion[]>([]);
  const [loading, setLoading] = useState(true);

  // Investigation states
  const [selectedTender, setSelectedTender] = useState<TenderSuggestion | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedFindings, setExpandedFindings] = useState<Set<number>>(new Set());
  const [agentStatuses, setAgentStatuses] = useState<{ id: string; status: "pending" | "running" | "completed" | "error"; findingsCount: number }[]>(
    AGENTS.map(a => ({ id: a.id, status: "pending", findingsCount: 0 }))
  );

  // Load data on mount
  useEffect(() => {
    loadTenderSuggestions();
  }, []);

  async function loadTenderSuggestions() {
    setLoading(true);
    try {
      // Fetch different categories in parallel
      const [singleBidder, highValue, recent] = await Promise.all([
        // Single bidder tenders (high risk pattern)
        api.searchTenders({ status: 'awarded', page: 1, page_size: 8, sort_by: 'estimated_value_mkd', sort_order: 'desc' })
          .then(r => (r.items || []).filter((t: any) => t.num_bidders === 1)),
        // High value tenders
        api.searchTenders({ status: 'awarded', page: 1, page_size: 8, sort_by: 'estimated_value_mkd', sort_order: 'desc' }),
        // Recent tenders
        api.searchTenders({ status: 'awarded', page: 1, page_size: 8, sort_by: 'created_at', sort_order: 'desc' })
      ]);

      setSingleBidderTenders(singleBidder.slice(0, 6));
      setHighValueTenders((highValue.items || []).slice(0, 6));
      setRecentTenders((recent.items || []).slice(0, 6));
    } catch (err) {
      console.error('Failed to load suggestions:', err);
    } finally {
      setLoading(false);
    }
  }

  const handleInvestigate = async (tender: TenderSuggestion) => {
    setSelectedTender(tender);
    setIsAnalyzing(true);
    setResult(null);
    setError(null);
    setExpandedFindings(new Set());
    setAgentStatuses(AGENTS.map(a => ({ id: a.id, status: "pending", findingsCount: 0 })));

    // Simulate agent progress
    const agentOrder = ["db", "enabavki", "web", "company", "documents", "synthesis"];
    let currentAgentIndex = 0;
    const progressInterval = setInterval(() => {
      if (currentAgentIndex < agentOrder.length) {
        setAgentStatuses(prev => prev.map(a => ({
          ...a,
          status: a.id === agentOrder[currentAgentIndex] ? "running" :
                  a.id === agentOrder[currentAgentIndex - 1] ? "completed" : a.status
        })));
        currentAgentIndex++;
      }
    }, 1200);

    try {
      const response = await fetch('/api/risk/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'tender', query: tender.tender_id })
      });

      clearInterval(progressInterval);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail?.message || errorData.detail || 'Анализата не успеа');
      }

      const data: InvestigationResult = await response.json();

      // Update agent statuses
      const findingsBySource: Record<string, number> = {};
      data.findings.forEach(f => { findingsBySource[f.source] = (findingsBySource[f.source] || 0) + 1; });

      setAgentStatuses([
        { id: "db", status: "completed", findingsCount: findingsBySource["db"] || findingsBySource["database"] || 0 },
        { id: "enabavki", status: "completed", findingsCount: findingsBySource["enabavki"] || findingsBySource["verification"] || 0 },
        { id: "web", status: "completed", findingsCount: findingsBySource["web"] || 0 },
        { id: "company", status: "completed", findingsCount: findingsBySource["company"] || 0 },
        { id: "documents", status: "completed", findingsCount: findingsBySource["document"] || findingsBySource["documents"] || 0 },
        { id: "synthesis", status: "completed", findingsCount: findingsBySource["synthesis"] || findingsBySource["llm"] || 0 }
      ]);

      setResult(data);
    } catch (err) {
      clearInterval(progressInterval);
      setError(err instanceof Error ? err.message : 'Непозната грешка');
      setAgentStatuses(prev => prev.map(a => ({ ...a, status: "error" })));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const getRiskColor = (level: string) => {
    const colors: Record<string, any> = {
      minimal: { bg: "bg-green-500", text: "text-green-700", light: "bg-green-100" },
      low: { bg: "bg-blue-500", text: "text-blue-700", light: "bg-blue-100" },
      medium: { bg: "bg-yellow-500", text: "text-yellow-700", light: "bg-yellow-100" },
      high: { bg: "bg-orange-500", text: "text-orange-700", light: "bg-orange-100" },
      critical: { bg: "bg-red-500", text: "text-red-700", light: "bg-red-100" }
    };
    return colors[level] || colors.medium;
  };

  const getRiskLabel = (level: string) => {
    const labels: Record<string, string> = { minimal: "Минимален", low: "Низок", medium: "Среден", high: "Висок", critical: "Критичен" };
    return labels[level] || "Непознат";
  };

  const getSourceName = (source: string) => {
    const names: Record<string, string> = {
      db: "База", database: "База", enabavki: "e-Набавки", verification: "Верификација",
      web: "Веб", company: "Компании", document: "Документи", documents: "Документи", synthesis: "AI", llm: "AI"
    };
    return names[source] || source;
  };

  // Tender Card Component
  const TenderCard = ({ tender, highlight }: { tender: TenderSuggestion; highlight?: string }) => (
    <div className="p-4 rounded-lg border hover:border-primary/50 hover:bg-primary/5 transition-all group">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm line-clamp-2 group-hover:text-primary">{tender.title}</p>
          {tender.procuring_entity && (
            <p className="text-xs text-muted-foreground mt-1 truncate">{tender.procuring_entity}</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 flex-wrap mb-3">
        <Badge variant="outline" className="text-[10px]">{tender.tender_id}</Badge>
        {tender.num_bidders === 1 && (
          <Badge variant="destructive" className="text-[10px]">1 понудувач</Badge>
        )}
        {highlight && (
          <Badge variant="secondary" className="text-[10px]">{highlight}</Badge>
        )}
      </div>

      <div className="flex items-center justify-between">
        {tender.estimated_value_mkd ? (
          <span className="text-sm font-semibold text-primary">{formatCurrency(tender.estimated_value_mkd)}</span>
        ) : (
          <span className="text-xs text-muted-foreground">Без вредност</span>
        )}
        <Button
          size="sm"
          onClick={() => handleInvestigate(tender)}
          disabled={isAnalyzing}
          className="h-8"
        >
          <Shield className="h-3 w-3 mr-1" />
          Истражи
        </Button>
      </div>
    </div>
  );

  // If investigating, show analysis view
  if (selectedTender && (isAnalyzing || result)) {
    return (
      <div className="p-4 md:p-6 space-y-4">
        {/* Back button and header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => { setSelectedTender(null); setResult(null); }}>
            <ChevronRight className="h-4 w-4 rotate-180 mr-1" />
            Назад
          </Button>
          <div className="flex-1">
            <h1 className="text-xl font-bold flex items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              Анализа на ризик
            </h1>
          </div>
        </div>

        {/* Tender being analyzed */}
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium">{selectedTender.title}</p>
                <p className="text-sm text-muted-foreground">{selectedTender.procuring_entity}</p>
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="outline">{selectedTender.tender_id}</Badge>
                  {selectedTender.estimated_value_mkd && (
                    <span className="text-sm font-medium text-primary">{formatCurrency(selectedTender.estimated_value_mkd)}</span>
                  )}
                </div>
              </div>
              <Link href={`/tenders/${selectedTender.tender_id}`} target="_blank">
                <Button variant="outline" size="sm">
                  <ExternalLink className="h-4 w-4 mr-1" />
                  Детали
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>

        {/* Agent Progress */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              {isAnalyzing && <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />}
              {isAnalyzing ? "Агентите истражуваат..." : "Анализа завршена"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {AGENTS.map(agent => {
                const status = agentStatuses.find(s => s.id === agent.id);
                const Icon = agent.icon;
                return (
                  <div
                    key={agent.id}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs transition-all ${
                      status?.status === "running" ? "bg-primary/10 text-primary ring-2 ring-primary/30" :
                      status?.status === "completed" ? "bg-green-100 text-green-700" :
                      status?.status === "error" ? "bg-red-100 text-red-700" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {status?.status === "running" ? (
                      <div className="h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                    ) : status?.status === "completed" ? (
                      <CheckCircle2 className="h-3 w-3" />
                    ) : status?.status === "error" ? (
                      <XCircle className="h-3 w-3" />
                    ) : (
                      <Icon className="h-3 w-3" />
                    )}
                    <span>{agent.name}</span>
                    {status?.status === "completed" && status.findingsCount > 0 && (
                      <Badge variant="secondary" className="h-4 px-1 text-[10px] ml-1">{status.findingsCount}</Badge>
                    )}
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Error */}
        {error && (
          <Card className="border-red-200 bg-red-50">
            <CardContent className="pt-4">
              <div className="flex items-center gap-2 text-red-700">
                <XCircle className="h-5 w-5" />
                <span>{error}</span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-4">
            {/* Score Card */}
            <Card>
              <div className={`h-1.5 ${getRiskColor(result.risk_level).bg}`} />
              <CardContent className="pt-4">
                <div className="flex flex-col sm:flex-row gap-4">
                  <div className="flex items-center gap-4">
                    <div className="relative w-20 h-20">
                      <svg className="w-full h-full transform -rotate-90">
                        <circle cx="40" cy="40" r="36" stroke="currentColor" strokeWidth="6" fill="none" className="text-muted" />
                        <circle cx="40" cy="40" r="36" stroke="currentColor" strokeWidth="6" fill="none"
                          strokeDasharray={`${(result.risk_score / 100) * 226} 226`}
                          strokeLinecap="round"
                          className={getRiskColor(result.risk_level).bg.replace('bg-', 'text-')}
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-2xl font-bold">{result.risk_score}</span>
                      </div>
                    </div>
                    <div>
                      <Badge className={`${getRiskColor(result.risk_level).light} ${getRiskColor(result.risk_level).text}`}>
                        {getRiskLabel(result.risk_level)} ризик
                      </Badge>
                      <p className="text-sm text-muted-foreground mt-1">{Math.round(result.confidence * 100)}% сигурност</p>
                    </div>
                  </div>
                  <div className="flex-1">
                    <p className="text-sm">{result.summary_mk || "Анализата е завршена."}</p>
                    {result.cached && (
                      <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                        <Clock className="h-3 w-3" /> Кеширан резултат
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Findings */}
            {result.findings.length > 0 && (
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Наоди ({result.findings.length})</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {result.findings.map((finding, idx) => {
                    const config = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.low;
                    const isExpanded = expandedFindings.has(idx);

                    return (
                      <div key={idx} className={`rounded-lg border ${config.border} overflow-hidden`}>
                        <button
                          onClick={() => setExpandedFindings(prev => {
                            const s = new Set(prev);
                            s.has(idx) ? s.delete(idx) : s.add(idx);
                            return s;
                          })}
                          className={`w-full p-3 flex items-start gap-2 text-left ${config.bg}`}
                        >
                          <AlertTriangle className={`h-4 w-4 mt-0.5 ${config.text}`} />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 flex-wrap mb-1">
                              <Badge variant="outline" className={`text-[10px] ${config.bg} ${config.text} border-0`}>{config.label}</Badge>
                              <Badge variant="outline" className="text-[10px]">{getSourceName(finding.source)}</Badge>
                            </div>
                            <p className="text-sm">{finding.description}</p>
                          </div>
                          {finding.evidence.length > 0 && (
                            isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />
                          )}
                        </button>
                        {isExpanded && finding.evidence.length > 0 && (
                          <div className="p-3 border-t bg-background text-sm">
                            <p className="font-medium text-muted-foreground mb-2">Докази:</p>
                            <ul className="space-y-1">
                              {finding.evidence.map((ev, i) => (
                                <li key={i} className="flex gap-2 text-muted-foreground">
                                  <span>•</span><span>{ev}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            )}

            {/* No findings */}
            {result.findings.length === 0 && (
              <Card className="border-green-200 bg-green-50">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-6 w-6 text-green-600" />
                    <div>
                      <p className="font-medium text-green-700">Нема детектирани ризици</p>
                      <p className="text-sm text-green-600">Агентите не пронајдоа сомнителни индикатори</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Recommendations */}
            {result.recommendations.length > 0 && (
              <Card className="border-blue-200 bg-blue-50/50">
                <CardHeader className="pb-2">
                  <CardTitle className="text-base text-blue-700">Препораки</CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2">
                    {result.recommendations.map((rec, i) => (
                      <li key={i} className="flex gap-2 text-sm">
                        <span className="h-5 w-5 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-xs flex-shrink-0">{i + 1}</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    );
  }

  // Main discovery view
  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shield className="h-6 w-6 text-primary" />
          Анализа на ризик
        </h1>
        <p className="text-muted-foreground">6 AI агенти истражуваат тендери за корупциски ризици</p>
      </div>

      {/* How it works */}
      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="pt-4">
          <div className="flex items-start gap-3">
            <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
              <Sparkles className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="font-medium mb-1">Како работи?</p>
              <p className="text-sm text-muted-foreground">
                Изберете тендер за истражување. Нашите 6 AI агенти ќе анализираат податоци од база,
                е-набавки, веб, компании и документи за да детектираат потенцијални ризици.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {loading ? (
        <div className="space-y-6">
          {[1, 2, 3].map(i => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-48" />
                <Skeleton className="h-4 w-72" />
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {[1, 2, 3].map(j => <Skeleton key={j} className="h-32 rounded-lg" />)}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Single Bidder Tenders - High Risk */}
          {singleBidderTenders.length > 0 && (
            <Card className="border-orange-200">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <AlertCircle className="h-5 w-5 text-orange-500" />
                  Тендери со 1 понудувач
                  <Badge variant="destructive" className="ml-2">Висок ризик</Badge>
                </CardTitle>
                <CardDescription>
                  Тендери каде само една компанија поднела понуда - потенцијален индикатор за проблеми
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {singleBidderTenders.map(tender => (
                    <TenderCard key={tender.tender_id} tender={tender} />
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* High Value Tenders */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Banknote className="h-5 w-5 text-green-500" />
                Високо-вредни тендери
              </CardTitle>
              <CardDescription>
                Неодамна доделени тендери со највисока вредност
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {highValueTenders.map(tender => (
                  <TenderCard key={tender.tender_id} tender={tender} />
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Recent Tenders */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Clock className="h-5 w-5 text-blue-500" />
                Неодамнешни тендери
              </CardTitle>
              <CardDescription>
                Последно доделени тендери
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {recentTenders.map(tender => (
                  <TenderCard key={tender.tender_id} tender={tender} />
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Browse all */}
          <Card className="bg-muted/50">
            <CardContent className="pt-6">
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                <div>
                  <p className="font-medium">Барате конкретен тендер?</p>
                  <p className="text-sm text-muted-foreground">Пребарајте ги сите тендери и кликнете "Истражи" на детали страница</p>
                </div>
                <Link href="/tenders?status=awarded">
                  <Button>
                    <Search className="h-4 w-4 mr-2" />
                    Пребарај тендери
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
