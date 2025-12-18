"use client";

import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
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
  Link2,
  Eye,
  Newspaper,
  Scale,
  Clock,
  Zap,
  Info,
  TrendingUp,
  ArrowRight,
  Sparkles
} from "lucide-react";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import Link from "next/link";

// Agent definitions
const AGENTS = [
  { id: "db", name: "База на податоци", icon: Database, color: "from-blue-500 to-blue-600", description: "Историја, понудувачи, цени" },
  { id: "enabavki", name: "e-Набавки", icon: Globe, color: "from-green-500 to-green-600", description: "Официјална верификација" },
  { id: "web", name: "Веб истражување", icon: Newspaper, color: "from-purple-500 to-purple-600", description: "Вести, контроверзии" },
  { id: "company", name: "Компании", icon: Building2, color: "from-orange-500 to-orange-600", description: "Сопственици, поврзаности" },
  { id: "documents", name: "Документи", icon: FileText, color: "from-cyan-500 to-cyan-600", description: "Спецификации, договори" },
  { id: "synthesis", name: "AI синтеза", icon: Brain, color: "from-pink-500 to-pink-600", description: "Вкрстена анализа" }
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

interface SuggestedTender {
  tender_id: string;
  title: string;
  estimated_value_mkd?: number;
  procuring_entity?: string;
  status?: string;
}

export default function RiskAnalysisPage() {
  const [activeTab, setActiveTab] = useState("tender");
  const [searchQuery, setSearchQuery] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedFindings, setExpandedFindings] = useState<Set<number>>(new Set());
  const [agentStatuses, setAgentStatuses] = useState<{ id: string; status: "pending" | "running" | "completed" | "error"; findingsCount: number }[]>(
    AGENTS.map(a => ({ id: a.id, status: "pending", findingsCount: 0 }))
  );

  // Suggestions
  const [suggestedTenders, setSuggestedTenders] = useState<SuggestedTender[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(true);

  // Load suggestions on mount
  useEffect(() => {
    loadSuggestions();
  }, []);

  async function loadSuggestions() {
    try {
      setLoadingSuggestions(true);
      // Fetch recent high-value awarded tenders as suggestions
      const response = await api.searchTenders({
        status: 'awarded',
        page: 1,
        page_size: 6,
        sort_by: 'estimated_value_mkd',
        sort_order: 'desc'
      });
      setSuggestedTenders(response.items || []);
    } catch (err) {
      console.error('Failed to load suggestions:', err);
    } finally {
      setLoadingSuggestions(false);
    }
  }

  const handleAnalyze = async (query?: string) => {
    const searchTerm = query || searchQuery;
    if (!searchTerm.trim()) return;

    setSearchQuery(searchTerm);
    setIsAnalyzing(true);
    setResult(null);
    setError(null);
    setExpandedFindings(new Set());
    setAgentStatuses(AGENTS.map(a => ({ id: a.id, status: "pending" as "pending" | "running" | "completed" | "error", findingsCount: 0 })));

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
        body: JSON.stringify({ type: activeTab, query: searchTerm })
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
      setAgentStatuses(prev => prev.map(a => ({ ...a, status: "error" as "pending" | "running" | "completed" | "error" })));
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
    const labels: Record<string, string> = {
      minimal: "Минимален", low: "Низок", medium: "Среден", high: "Висок", critical: "Критичен"
    };
    return labels[level] || "Непознат";
  };

  const getSourceName = (source: string) => {
    const names: Record<string, string> = {
      db: "База", database: "База", enabavki: "e-Набавки", verification: "Верификација",
      web: "Веб", company: "Компании", document: "Документи", documents: "Документи",
      synthesis: "AI", llm: "AI"
    };
    return names[source] || source;
  };

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Shield className="h-6 w-6 text-primary" />
            Анализа на ризик
          </h1>
          <p className="text-muted-foreground">6 AI агенти истражуваат тендери за корупциски ризици</p>
        </div>
      </div>

      {/* Search Section */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Истражи</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="grid w-full grid-cols-3 mb-4">
              <TabsTrigger value="tender"><FileText className="h-4 w-4 mr-1" /> Тендер</TabsTrigger>
              <TabsTrigger value="company"><Building2 className="h-4 w-4 mr-1" /> Компанија</TabsTrigger>
              <TabsTrigger value="institution"><Users className="h-4 w-4 mr-1" /> Институција</TabsTrigger>
            </TabsList>
          </Tabs>

          <div className="flex gap-2">
            <Input
              placeholder={
                activeTab === "tender" ? "ID на тендер (пр. 12345/2024)" :
                activeTab === "company" ? "Име на компанија" : "Име на институција"
              }
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
              disabled={isAnalyzing}
              className="flex-1"
            />
            <Button onClick={() => handleAnalyze()} disabled={!searchQuery.trim() || isAnalyzing}>
              {isAnalyzing ? <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" /> : <Search className="h-4 w-4" />}
              <span className="ml-2 hidden sm:inline">{isAnalyzing ? "Анализирам..." : "Истражи"}</span>
            </Button>
          </div>

          {/* Agent Pills - Always visible */}
          <div className="flex flex-wrap gap-2 pt-2">
            {AGENTS.map(agent => {
              const status = agentStatuses.find(s => s.id === agent.id);
              const Icon = agent.icon;
              return (
                <div
                  key={agent.id}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-xs transition-all ${
                    status?.status === "running" ? "bg-primary/10 text-primary ring-2 ring-primary/30" :
                    status?.status === "completed" ? "bg-green-100 text-green-700" :
                    status?.status === "error" ? "bg-red-100 text-red-700" : "bg-muted text-muted-foreground"
                  }`}
                >
                  {status?.status === "running" ? (
                    <div className="h-3 w-3 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                  ) : status?.status === "completed" ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : (
                    <Icon className="h-3 w-3" />
                  )}
                  <span>{agent.name}</span>
                  {status?.status === "completed" && status.findingsCount > 0 && (
                    <Badge variant="secondary" className="h-4 px-1 text-[10px]">{status.findingsCount}</Badge>
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Suggestions - Show when no result */}
      {!result && !isAnalyzing && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-yellow-500" />
              Предлози за истрага
            </CardTitle>
            <CardDescription>Неодамнешни тендери со висока вредност - кликни за анализа</CardDescription>
          </CardHeader>
          <CardContent>
            {loadingSuggestions ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {[...Array(6)].map((_, i) => (
                  <Skeleton key={i} className="h-24 rounded-lg" />
                ))}
              </div>
            ) : suggestedTenders.length > 0 ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {suggestedTenders.map(tender => (
                  <button
                    key={tender.tender_id}
                    onClick={() => {
                      setActiveTab("tender");
                      handleAnalyze(tender.tender_id);
                    }}
                    className="p-3 rounded-lg border hover:border-primary hover:bg-primary/5 transition-all text-left group"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium text-sm line-clamp-2 group-hover:text-primary">{tender.title}</p>
                      <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary flex-shrink-0" />
                    </div>
                    {tender.procuring_entity && <p className="text-xs text-muted-foreground mt-1 truncate">{tender.procuring_entity}</p>}
                    <div className="flex items-center justify-between mt-2">
                      <Badge variant="outline" className="text-[10px]">{tender.tender_id}</Badge>
                      {tender.estimated_value_mkd && <span className="text-xs font-medium text-primary">{formatCurrency(tender.estimated_value_mkd)}</span>}
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground text-sm text-center py-4">Нема достапни предлози</p>
            )}

            <div className="mt-4 pt-4 border-t">
              <p className="text-sm text-muted-foreground mb-3">Или истражи од листата на тендери:</p>
              <Link href="/tenders?status=awarded">
                <Button variant="outline" className="w-full sm:w-auto">
                  <Search className="h-4 w-4 mr-2" />
                  Прегледај ги сите тендери
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

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
      {result && !isAnalyzing && (
        <div className="space-y-4">
          {/* Score Card */}
          <Card>
            <div className={`h-1.5 ${getRiskColor(result.risk_level).bg}`} />
            <CardContent className="pt-4">
              <div className="flex flex-col sm:flex-row gap-4">
                {/* Score */}
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

                {/* Summary */}
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
                <CardTitle className="text-lg">Наоди ({result.findings.length})</CardTitle>
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
                            {finding.corroborated && <Badge variant="outline" className="text-[10px] bg-green-100 text-green-700 border-0">Потврдено</Badge>}
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

          {/* New search */}
          <div className="flex justify-center pt-4">
            <Button variant="outline" onClick={() => { setResult(null); setSearchQuery(""); }}>
              <Search className="h-4 w-4 mr-2" />
              Нова истрага
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
