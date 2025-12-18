"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
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
  ShoppingCart,
  Newspaper,
  Scale,
  Clock,
  Zap,
  Info
} from "lucide-react";

// Agent definitions with descriptions
const AGENTS = [
  {
    id: "db",
    name: "База на податоци",
    nameEn: "Database Research",
    icon: Database,
    color: "blue",
    description: "Анализа на историја на тендери, понудувачи, договори и цени од нашата база",
    checks: ["Историја на тендерот", "Понудувачи и понуди", "Претходни договори", "Споредба на цени"]
  },
  {
    id: "enabavki",
    name: "e-Набавки верификација",
    nameEn: "Official Portal",
    icon: Globe,
    color: "green",
    description: "Верификација на податоци од официјалниот портал e-nabavki.gov.mk",
    checks: ["Официјален број на понудувачи", "Статус на тендер", "Датуми и рокови", "Вредност на договор"]
  },
  {
    id: "web",
    name: "Веб истражување",
    nameEn: "Web Research",
    icon: Newspaper,
    color: "purple",
    description: "Пребарување на вести, контроверзии и јавни информации",
    checks: ["Новински написи", "Јавни контроверзии", "Претходни истраги", "Медиумско присуство"]
  },
  {
    id: "company",
    name: "Анализа на компании",
    nameEn: "Company Analysis",
    icon: Building2,
    color: "orange",
    description: "Истражување на сопственичка структура, поврзаности и историја на компании",
    checks: ["Сопственичка структура", "Поврзани компании", "Историја на добивање тендери", "Деловни партнери"]
  },
  {
    id: "documents",
    name: "Анализа на документи",
    nameEn: "Document Analysis",
    icon: FileText,
    color: "cyan",
    description: "AI анализа на тендерска документација, спецификации и договори",
    checks: ["Техничка спецификација", "Критериуми за избор", "Договорни услови", "Потенцијални рестрикции"]
  },
  {
    id: "synthesis",
    name: "AI синтеза",
    nameEn: "AI Synthesis",
    icon: Brain,
    color: "pink",
    description: "Вкрстена анализа на сите извори со Gemini AI за детекција на ризици",
    checks: ["Вкрстена верификација", "Детекција на аномалии", "Пресметка на ризик", "Генерирање на препораки"]
  }
];

// Finding severity colors
const SEVERITY_CONFIG = {
  critical: { bg: "bg-red-100", text: "text-red-700", border: "border-red-200", label: "Критичен" },
  high: { bg: "bg-orange-100", text: "text-orange-700", border: "border-orange-200", label: "Висок" },
  medium: { bg: "bg-yellow-100", text: "text-yellow-700", border: "border-yellow-200", label: "Среден" },
  low: { bg: "bg-blue-100", text: "text-blue-700", border: "border-blue-200", label: "Низок" }
};

// Finding type icons
const FINDING_TYPE_ICONS: Record<string, any> = {
  red_flag: AlertTriangle,
  discrepancy: Scale,
  connection: Link2,
  anomaly: Zap,
  info: Info
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

interface SourcesChecked {
  database: boolean;
  enabavki: boolean;
  web_search: boolean;
  company: boolean;
  documents: boolean;
}

interface DataQuality {
  db_data_complete?: boolean;
  official_data_available?: boolean;
  web_data_found?: boolean;
  missing_info: string[];
}

interface InvestigationResult {
  risk_score: number;
  risk_level: "minimal" | "low" | "medium" | "high" | "critical";
  confidence: number;
  findings: Finding[];
  sources_checked: SourcesChecked;
  recommendations: string[];
  summary_mk: string;
  data_quality: DataQuality;
  investigated_at: string;
  cached: boolean;
}

interface AgentStatus {
  id: string;
  status: "pending" | "running" | "completed" | "error";
  findingsCount: number;
}

export default function RiskAnalysisPage() {
  const [activeTab, setActiveTab] = useState("tender");
  const [searchQuery, setSearchQuery] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<InvestigationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expandedFindings, setExpandedFindings] = useState<Set<number>>(new Set());
  const [agentStatuses, setAgentStatuses] = useState<AgentStatus[]>(
    AGENTS.map(a => ({ id: a.id, status: "pending", findingsCount: 0 }))
  );

  const handleAnalyze = async () => {
    if (!searchQuery.trim()) return;

    setIsAnalyzing(true);
    setResult(null);
    setError(null);
    setExpandedFindings(new Set());

    // Reset agent statuses
    setAgentStatuses(AGENTS.map(a => ({ id: a.id, status: "pending", findingsCount: 0 })));

    // Simulate agent progress (since backend doesn't stream yet)
    const agentOrder = ["db", "enabavki", "web", "company", "documents", "synthesis"];
    let currentAgentIndex = 0;

    const progressInterval = setInterval(() => {
      if (currentAgentIndex < agentOrder.length) {
        setAgentStatuses(prev => prev.map(a =>
          a.id === agentOrder[currentAgentIndex]
            ? { ...a, status: "running" as const }
            : a.id === agentOrder[currentAgentIndex - 1]
              ? { ...a, status: "completed" as const }
              : a
        ));
        currentAgentIndex++;
      }
    }, 1500);

    try {
      const response = await fetch('/api/risk/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: activeTab, query: searchQuery })
      });

      clearInterval(progressInterval);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail?.message || errorData.detail || 'Анализата не успеа');
      }

      const data: InvestigationResult = await response.json();

      // Update agent statuses based on actual results
      const findingsBySource: Record<string, number> = {};
      data.findings.forEach(f => {
        findingsBySource[f.source] = (findingsBySource[f.source] || 0) + 1;
      });

      setAgentStatuses([
        { id: "db", status: data.sources_checked.database ? "completed" : "error", findingsCount: findingsBySource["db"] || 0 },
        { id: "enabavki", status: data.sources_checked.enabavki ? "completed" : "error", findingsCount: findingsBySource["enabavki"] || findingsBySource["verification"] || 0 },
        { id: "web", status: data.sources_checked.web_search ? "completed" : "error", findingsCount: findingsBySource["web"] || 0 },
        { id: "company", status: data.sources_checked.company ? "completed" : "error", findingsCount: findingsBySource["company"] || 0 },
        { id: "documents", status: data.sources_checked.documents ? "completed" : "error", findingsCount: findingsBySource["document"] || 0 },
        { id: "synthesis", status: "completed", findingsCount: findingsBySource["synthesis"] || findingsBySource["llm"] || 0 }
      ]);

      setResult(data);
    } catch (err) {
      clearInterval(progressInterval);
      setError(err instanceof Error ? err.message : 'Непозната грешка');
      setAgentStatuses(prev => prev.map(a => ({ ...a, status: "error" as const })));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const toggleFindingExpanded = (index: number) => {
    setExpandedFindings(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) newSet.delete(index);
      else newSet.add(index);
      return newSet;
    });
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case "minimal": return { bg: "bg-green-500", text: "text-green-700", light: "bg-green-100" };
      case "low": return { bg: "bg-blue-500", text: "text-blue-700", light: "bg-blue-100" };
      case "medium": return { bg: "bg-yellow-500", text: "text-yellow-700", light: "bg-yellow-100" };
      case "high": return { bg: "bg-orange-500", text: "text-orange-700", light: "bg-orange-100" };
      case "critical": return { bg: "bg-red-500", text: "text-red-700", light: "bg-red-100" };
      default: return { bg: "bg-gray-500", text: "text-gray-700", light: "bg-gray-100" };
    }
  };

  const getRiskLabel = (level: string) => {
    switch (level) {
      case "minimal": return "Минимален ризик";
      case "low": return "Низок ризик";
      case "medium": return "Среден ризик";
      case "high": return "Висок ризик";
      case "critical": return "Критичен ризик";
      default: return "Непознато";
    }
  };

  const getAgentColor = (color: string) => {
    const colors: Record<string, string> = {
      blue: "from-blue-500 to-blue-600",
      green: "from-green-500 to-green-600",
      purple: "from-purple-500 to-purple-600",
      orange: "from-orange-500 to-orange-600",
      cyan: "from-cyan-500 to-cyan-600",
      pink: "from-pink-500 to-pink-600"
    };
    return colors[color] || colors.blue;
  };

  const getSourceDisplayName = (source: string) => {
    const sourceMap: Record<string, string> = {
      db: "База на податоци",
      database: "База на податоци",
      enabavki: "e-Набавки",
      verification: "Верификација",
      web: "Веб истражување",
      company: "Анализа на компании",
      document: "Документи",
      documents: "Документи",
      synthesis: "AI синтеза",
      llm: "AI синтеза"
    };
    return sourceMap[source] || source;
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/20">
      <div className="container mx-auto px-4 py-8 max-w-7xl">

        {/* Hero Header */}
        <div className="mb-8 text-center">
          <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-gradient-to-br from-primary to-primary/80 mb-4 shadow-lg">
            <Shield className="h-8 w-8 text-primary-foreground" />
          </div>
          <h1 className="text-4xl font-bold mb-2">Детекција на корупциски ризици</h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            6 специјализирани AI агенти анализираат тендери од повеќе извори за да детектираат
            потенцијални ризици, неправилности и сомнителни обрасци
          </p>
        </div>

        {/* Agent Overview - Always visible */}
        {!isAnalyzing && !result && (
          <div className="mb-8">
            <h2 className="text-lg font-semibold mb-4 text-center">Нашите истражувачки агенти</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {AGENTS.map((agent) => {
                const IconComponent = agent.icon;
                return (
                  <Card key={agent.id} className="relative overflow-hidden group hover:shadow-md transition-shadow">
                    <div className={`absolute inset-0 bg-gradient-to-br ${getAgentColor(agent.color)} opacity-5 group-hover:opacity-10 transition-opacity`} />
                    <CardContent className="p-4 text-center">
                      <div className={`inline-flex items-center justify-center h-12 w-12 rounded-xl bg-gradient-to-br ${getAgentColor(agent.color)} mb-3 shadow-sm`}>
                        <IconComponent className="h-6 w-6 text-white" />
                      </div>
                      <h3 className="font-medium text-sm mb-1">{agent.name}</h3>
                      <p className="text-xs text-muted-foreground line-clamp-2">{agent.description}</p>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </div>
        )}

        {/* Search Card */}
        <Card className="mb-6 shadow-lg border-2">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2">
              <Search className="h-5 w-5" />
              Нова истрага
            </CardTitle>
            <CardDescription>
              Изберете тип и внесете ID на тендер, име на компанија или институција за длабинска анализа
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-4">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="tender" className="gap-2">
                  <FileText className="h-4 w-4" />
                  Тендер
                </TabsTrigger>
                <TabsTrigger value="company" className="gap-2">
                  <Building2 className="h-4 w-4" />
                  Компанија
                </TabsTrigger>
                <TabsTrigger value="institution" className="gap-2">
                  <Users className="h-4 w-4" />
                  Институција
                </TabsTrigger>
              </TabsList>
            </Tabs>

            <div className="flex gap-3">
              <Input
                placeholder={
                  activeTab === "tender" ? "пр. 12345/2024 или наслов на тендер..." :
                  activeTab === "company" ? "пр. Дрисла ДОО или ЕДБ број..." :
                  "пр. Министерство за здравство..."
                }
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                className="flex-1 h-12 text-lg"
                disabled={isAnalyzing}
              />
              <Button
                onClick={handleAnalyze}
                disabled={!searchQuery.trim() || isAnalyzing}
                className="h-12 px-8 text-lg"
                size="lg"
              >
                {isAnalyzing ? (
                  <>
                    <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary-foreground border-t-transparent mr-2" />
                    Анализирам...
                  </>
                ) : (
                  <>
                    <Shield className="h-5 w-5 mr-2" />
                    Истражи
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Agent Progress During Analysis */}
        {isAnalyzing && (
          <Card className="mb-6 border-2 border-primary/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                Агентите истражуваат...
              </CardTitle>
              <CardDescription>
                Собираме и анализираме податоци од повеќе независни извори
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {AGENTS.map((agent, idx) => {
                  const IconComponent = agent.icon;
                  const status = agentStatuses.find(s => s.id === agent.id);

                  return (
                    <div
                      key={agent.id}
                      className={`p-4 rounded-lg border-2 transition-all ${
                        status?.status === "running"
                          ? "border-primary bg-primary/5 shadow-md"
                          : status?.status === "completed"
                            ? "border-green-500 bg-green-50"
                            : "border-muted"
                      }`}
                    >
                      <div className="flex items-center gap-3 mb-2">
                        <div className={`h-10 w-10 rounded-lg flex items-center justify-center bg-gradient-to-br ${getAgentColor(agent.color)}`}>
                          <IconComponent className="h-5 w-5 text-white" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{agent.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {status?.status === "pending" && "Чека..."}
                            {status?.status === "running" && "Истражува..."}
                            {status?.status === "completed" && "Завршено"}
                            {status?.status === "error" && "Грешка"}
                          </p>
                        </div>
                        {status?.status === "running" && (
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                        )}
                        {status?.status === "completed" && (
                          <CheckCircle2 className="h-5 w-5 text-green-600" />
                        )}
                      </div>
                      {status?.status === "running" && (
                        <div className="space-y-1 mt-2">
                          {agent.checks.slice(0, 2).map((check, i) => (
                            <p key={i} className="text-xs text-muted-foreground flex items-center gap-1">
                              <span className="h-1 w-1 rounded-full bg-primary animate-pulse" />
                              {check}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Error State */}
        {error && (
          <Card className="mb-6 border-red-200 bg-red-50">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3 text-red-700">
                <XCircle className="h-6 w-6" />
                <div>
                  <p className="font-medium">Грешка при анализа</p>
                  <p className="text-sm">{error}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Results */}
        {result && !isAnalyzing && (
          <div className="space-y-6">

            {/* Risk Score Header */}
            <Card className="overflow-hidden">
              <div className={`h-2 ${getRiskColor(result.risk_level).bg}`} />
              <CardContent className="pt-6">
                <div className="grid md:grid-cols-4 gap-6">
                  {/* Risk Gauge */}
                  <div className="flex flex-col items-center justify-center">
                    <div className="relative w-36 h-36 mb-2">
                      <svg className="w-full h-full transform -rotate-90">
                        <circle cx="72" cy="72" r="64" stroke="currentColor" strokeWidth="12" fill="none" className="text-muted" />
                        <circle
                          cx="72" cy="72" r="64"
                          stroke="currentColor" strokeWidth="12" fill="none"
                          strokeDasharray={`${(result.risk_score / 100) * 402.12} 402.12`}
                          strokeLinecap="round"
                          className={getRiskColor(result.risk_level).bg.replace('bg-', 'text-')}
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-4xl font-bold">{result.risk_score}</span>
                        <span className="text-xs text-muted-foreground">од 100</span>
                      </div>
                    </div>
                    <Badge className={`${getRiskColor(result.risk_level).light} ${getRiskColor(result.risk_level).text} px-4 py-1`}>
                      {getRiskLabel(result.risk_level)}
                    </Badge>
                  </div>

                  {/* Stats */}
                  <div className="md:col-span-3 space-y-4">
                    <div>
                      <p className="text-sm text-muted-foreground mb-1">AI Резиме</p>
                      <p className="text-lg">{result.summary_mk || "Нема резиме"}</p>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                      <div className="p-3 rounded-lg bg-muted/50">
                        <p className="text-2xl font-bold">{result.findings.length}</p>
                        <p className="text-xs text-muted-foreground">Наоди</p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/50">
                        <p className="text-2xl font-bold">{Math.round(result.confidence * 100)}%</p>
                        <p className="text-xs text-muted-foreground">Доверливост</p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/50">
                        <p className="text-2xl font-bold flex items-center gap-1">
                          {Object.values(result.sources_checked).filter(Boolean).length}/5
                        </p>
                        <p className="text-xs text-muted-foreground">Извори</p>
                      </div>
                    </div>

                    {result.cached && (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Clock className="h-4 w-4" />
                        Кеширан резултат од {new Date(result.investigated_at).toLocaleString('mk-MK')}
                      </div>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Agent Results Summary */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Eye className="h-5 w-5" />
                  Резултати по агенти
                </CardTitle>
                <CardDescription>Што откри секој истражувачки агент</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
                  {AGENTS.map((agent) => {
                    const status = agentStatuses.find(s => s.id === agent.id);
                    const IconComponent = agent.icon;
                    const isActive = status?.status === "completed" && status.findingsCount > 0;

                    return (
                      <div
                        key={agent.id}
                        className={`p-3 rounded-lg border text-center ${
                          isActive ? "border-primary/50 bg-primary/5" : "border-muted bg-muted/20"
                        }`}
                      >
                        <IconComponent className={`h-6 w-6 mx-auto mb-2 ${isActive ? "text-primary" : "text-muted-foreground"}`} />
                        <p className="text-xs font-medium truncate">{agent.name}</p>
                        <p className={`text-lg font-bold ${isActive ? "text-primary" : "text-muted-foreground"}`}>
                          {status?.findingsCount || 0}
                        </p>
                        <p className="text-xs text-muted-foreground">наоди</p>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>

            {/* Detailed Findings */}
            {result.findings.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5" />
                    Детални наоди ({result.findings.length})
                  </CardTitle>
                  <CardDescription>
                    Сите пронајдени индикатори со докази и извори
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {result.findings.map((finding, idx) => {
                      const severityConfig = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.low;
                      const FindingIcon = FINDING_TYPE_ICONS[finding.type] || AlertTriangle;
                      const isExpanded = expandedFindings.has(idx);

                      return (
                        <div
                          key={idx}
                          className={`border rounded-lg overflow-hidden ${severityConfig.border}`}
                        >
                          <button
                            onClick={() => toggleFindingExpanded(idx)}
                            className={`w-full p-4 flex items-start gap-3 text-left hover:bg-muted/30 transition-colors ${severityConfig.bg}`}
                          >
                            <FindingIcon className={`h-5 w-5 mt-0.5 ${severityConfig.text}`} />
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-1 flex-wrap">
                                <Badge variant="outline" className={`${severityConfig.bg} ${severityConfig.text} border-0`}>
                                  {severityConfig.label}
                                </Badge>
                                <Badge variant="outline" className="text-xs">
                                  {getSourceDisplayName(finding.source)}
                                </Badge>
                                {finding.corroborated && (
                                  <Badge variant="outline" className="text-xs bg-green-100 text-green-700 border-0">
                                    <CheckCircle2 className="h-3 w-3 mr-1" />
                                    Потврдено
                                  </Badge>
                                )}
                                {finding.confidence && (
                                  <span className="text-xs text-muted-foreground">
                                    {Math.round(finding.confidence * 100)}% сигурност
                                  </span>
                                )}
                              </div>
                              <p className="font-medium">{finding.description}</p>
                            </div>
                            {finding.evidence.length > 0 && (
                              isExpanded
                                ? <ChevronUp className="h-5 w-5 text-muted-foreground" />
                                : <ChevronDown className="h-5 w-5 text-muted-foreground" />
                            )}
                          </button>

                          {isExpanded && finding.evidence.length > 0 && (
                            <div className="px-4 pb-4 pt-2 border-t bg-background">
                              <p className="text-sm font-medium mb-2 text-muted-foreground">Докази:</p>
                              <ul className="space-y-2">
                                {finding.evidence.map((ev, i) => (
                                  <li key={i} className="text-sm flex items-start gap-2">
                                    <span className="text-primary mt-1.5">•</span>
                                    <span className="text-muted-foreground">{ev}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* No Findings State */}
            {result.findings.length === 0 && (
              <Card className="border-green-200 bg-green-50/50">
                <CardContent className="pt-6">
                  <div className="flex items-center gap-4">
                    <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                      <CheckCircle2 className="h-6 w-6 text-green-600" />
                    </div>
                    <div>
                      <p className="font-medium text-green-700">Не се пронајдени значајни ризици</p>
                      <p className="text-sm text-green-600">
                        Агентите не детектираа сомнителни обрасци или индикатори за корупција
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Recommendations */}
            {result.recommendations.length > 0 && (
              <Card className="border-blue-200 bg-blue-50/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-blue-700">
                    <CheckCircle2 className="h-5 w-5" />
                    Препораки за дејствување
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    {result.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-3">
                        <span className="h-6 w-6 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-medium flex-shrink-0">
                          {idx + 1}
                        </span>
                        <span className="text-sm">{rec}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            {/* Data Quality Warning */}
            {result.data_quality.missing_info && result.data_quality.missing_info.length > 0 && (
              <Card className="border-yellow-200 bg-yellow-50/50">
                <CardContent className="pt-6">
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-yellow-600 mt-0.5" />
                    <div>
                      <p className="font-medium text-yellow-700 mb-1">Забелешка за квалитет на податоци</p>
                      <p className="text-sm text-yellow-600">
                        Недостасуваат: {result.data_quality.missing_info.join(", ")}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
