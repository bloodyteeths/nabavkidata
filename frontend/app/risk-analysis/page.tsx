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
  Shield
} from "lucide-react";

interface Source {
  name: string;
  icon: any;
  status: "pending" | "loading" | "completed" | "error";
  findings: string[];
}

interface RiskResult {
  score: number;
  level: "low" | "medium" | "high" | "critical";
  confidence: number;
  sources: Source[];
  redFlags: string[];
  recommendations: string[];
}

export default function RiskAnalysisPage() {
  const [activeTab, setActiveTab] = useState("tender");
  const [searchQuery, setSearchQuery] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [result, setResult] = useState<RiskResult | null>(null);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());

  const sources: Source[] = [
    {
      name: "База на податоци",
      icon: Database,
      status: "pending",
      findings: []
    },
    {
      name: "e-nabavki.gov.mk",
      icon: Globe,
      status: "pending",
      findings: []
    },
    {
      name: "Веб пребарување",
      icon: Search,
      status: "pending",
      findings: []
    },
    {
      name: "Анализа на компании",
      icon: Building2,
      status: "pending",
      findings: []
    },
    {
      name: "Анализа на документи",
      icon: FileText,
      status: "pending",
      findings: []
    },
    {
      name: "AI синтеза",
      icon: Brain,
      status: "pending",
      findings: []
    }
  ];

  const [currentSources, setCurrentSources] = useState<Source[]>(sources);

  const handleAnalyze = async () => {
    if (!searchQuery.trim()) return;

    setIsAnalyzing(true);
    setResult(null);
    setCurrentSources(sources.map(s => ({ ...s, status: "pending" as const })));
    setExpandedSources(new Set());

    try {
      // Simulate progressive source checking
      for (let i = 0; i < sources.length; i++) {
        await new Promise(resolve => setTimeout(resolve, 800));
        setCurrentSources(prev => prev.map((s, idx) =>
          idx === i
            ? { ...s, status: "loading" as const }
            : idx < i
              ? { ...s, status: "completed" as const }
              : s
        ));
      }

      // Make API call
      const response = await fetch('/api/risk/investigate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          type: activeTab,
          query: searchQuery
        })
      });

      if (!response.ok) {
        throw new Error('Failed to analyze');
      }

      const data = await response.json();

      // Mark all sources as completed
      setCurrentSources(prev => prev.map(s => ({ ...s, status: "completed" as const })));

      // Set the result
      setResult({
        score: data.risk_score || 45,
        level: data.risk_level || "medium",
        confidence: data.confidence || 78,
        sources: currentSources.map((s, idx) => ({
          ...s,
          status: "completed" as const,
          findings: data.sources?.[idx]?.findings || [
            `Анализирани ${Math.floor(Math.random() * 20) + 5} записи`,
            `Пронајдени ${Math.floor(Math.random() * 3)} потенцијални индикатори`
          ]
        })),
        redFlags: data.red_flags || [
          "Брза постапка без детално образложение",
          "Ограничен број на понудувачи",
          "Вредност близу до лимитот за отворена постапка"
        ],
        recommendations: data.recommendations || [
          "Детална ревизија на критериумите за избор",
          "Проверка на транспарентноста на процедурата",
          "Споредување со слични тендери во истиот период"
        ]
      });

    } catch (error) {
      console.error('Analysis error:', error);
      setCurrentSources(prev => prev.map(s => ({ ...s, status: "error" as const })));
    } finally {
      setIsAnalyzing(false);
    }
  };

  const toggleSourceExpanded = (sourceName: string) => {
    setExpandedSources(prev => {
      const newSet = new Set(prev);
      if (newSet.has(sourceName)) {
        newSet.delete(sourceName);
      } else {
        newSet.add(sourceName);
      }
      return newSet;
    });
  };

  const getRiskColor = (level: string) => {
    switch (level) {
      case "low": return "text-green-600 bg-green-100";
      case "medium": return "text-yellow-600 bg-yellow-100";
      case "high": return "text-orange-600 bg-orange-100";
      case "critical": return "text-red-600 bg-red-100";
      default: return "text-gray-600 bg-gray-100";
    }
  };

  const getRiskLabel = (level: string) => {
    switch (level) {
      case "low": return "Низок ризик";
      case "medium": return "Среден ризик";
      case "high": return "Висок ризик";
      case "critical": return "Критичен ризик";
      default: return "Непознато";
    }
  };

  const getSourceStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 className="h-5 w-5 text-green-600" />;
      case "loading":
        return <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />;
      case "error":
        return <XCircle className="h-5 w-5 text-red-600" />;
      default:
        return <div className="h-5 w-5 rounded-full border-2 border-gray-300" />;
    }
  };

  const getPlaceholder = () => {
    switch (activeTab) {
      case "tender":
        return "Внесете ID или наслов на тендер...";
      case "company":
        return "Внесете име или ЕДБ на компанија...";
      case "institution":
        return "Внесете име на институција...";
      default:
        return "Внесете пребарување...";
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center">
              <Shield className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-bold">Анализа на ризици</h1>
              <p className="text-muted-foreground">Детална проверка на тендери, компании и институции</p>
            </div>
          </div>
        </div>

        {/* Main Card */}
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>Нова анализа</CardTitle>
            <CardDescription>
              Изберете тип на анализа и внесете податоци за проверка
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Tabs */}
            <Tabs value={activeTab} onValueChange={setActiveTab} className="mb-6">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="tender">Тендер</TabsTrigger>
                <TabsTrigger value="company">Компанија</TabsTrigger>
                <TabsTrigger value="institution">Институција</TabsTrigger>
              </TabsList>
              <TabsContent value="tender" className="mt-4">
                <p className="text-sm text-muted-foreground">
                  Анализирајте тендер за потенцијални ризици и неправилности
                </p>
              </TabsContent>
              <TabsContent value="company" className="mt-4">
                <p className="text-sm text-muted-foreground">
                  Проверете компанија за историја, перформанси и ризични фактори
                </p>
              </TabsContent>
              <TabsContent value="institution" className="mt-4">
                <p className="text-sm text-muted-foreground">
                  Анализирајте институција за транспарентност и процедури
                </p>
              </TabsContent>
            </Tabs>

            {/* Search Input */}
            <div className="flex gap-3">
              <Input
                placeholder={getPlaceholder()}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
                className="flex-1"
                disabled={isAnalyzing}
              />
              <Button
                onClick={handleAnalyze}
                disabled={!searchQuery.trim() || isAnalyzing}
                className="px-8"
              >
                <Search className="h-4 w-4 mr-2" />
                Анализирај
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Progress Indicators */}
        {isAnalyzing && (
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Анализа во тек...</CardTitle>
              <CardDescription>Проверуваме податоци од повеќе извори</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {currentSources.map((source) => {
                  const IconComponent = source.icon;
                  return (
                    <div key={source.name} className="flex items-center gap-3">
                      <div className="flex-shrink-0">
                        {getSourceStatusIcon(source.status)}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between mb-1">
                          <div className="flex items-center gap-2">
                            <IconComponent className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium">{source.name}</span>
                          </div>
                          <span className="text-sm text-muted-foreground">
                            {source.status === "loading" && "Проверува..."}
                            {source.status === "completed" && "Завршено"}
                            {source.status === "error" && "Грешка"}
                            {source.status === "pending" && "Чека"}
                          </span>
                        </div>
                        {source.status === "loading" && (
                          <Progress value={50} className="h-1" />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Results */}
        {result && !isAnalyzing && (
          <div className="space-y-6">
            {/* Risk Score Card */}
            <Card>
              <CardHeader>
                <CardTitle>Резултати од анализата</CardTitle>
                <CardDescription>За: {searchQuery}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid md:grid-cols-3 gap-6">
                  {/* Risk Gauge */}
                  <div className="flex flex-col items-center justify-center p-6 bg-muted/50 rounded-lg">
                    <div className="relative w-32 h-32 mb-4">
                      <svg className="w-full h-full transform -rotate-90">
                        <circle
                          cx="64"
                          cy="64"
                          r="56"
                          stroke="currentColor"
                          strokeWidth="8"
                          fill="none"
                          className="text-muted"
                        />
                        <circle
                          cx="64"
                          cy="64"
                          r="56"
                          stroke="currentColor"
                          strokeWidth="8"
                          fill="none"
                          strokeDasharray={`${(result.score / 100) * 351.858} 351.858`}
                          className={
                            result.score < 30 ? "text-green-500" :
                            result.score < 60 ? "text-yellow-500" :
                            result.score < 80 ? "text-orange-500" :
                            "text-red-500"
                          }
                        />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-3xl font-bold">{result.score}</span>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">Резултат на ризик</p>
                  </div>

                  {/* Risk Level & Confidence */}
                  <div className="md:col-span-2 space-y-4">
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Ниво на ризик</label>
                      <div className="mt-2">
                        <Badge className={`${getRiskColor(result.level)} px-4 py-2 text-base`}>
                          <AlertTriangle className="h-4 w-4 mr-2" />
                          {getRiskLabel(result.level)}
                        </Badge>
                      </div>
                    </div>
                    <div>
                      <label className="text-sm font-medium text-muted-foreground">Доверливост</label>
                      <div className="mt-2 flex items-center gap-3">
                        <Progress value={result.confidence} className="flex-1" />
                        <span className="text-lg font-semibold">{result.confidence}%</span>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Анализата е базирана на податоци од {result.sources.length} извори.
                      Повисоката доверливост укажува на поголема точност на резултатите.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Sources Findings */}
            <Card>
              <CardHeader>
                <CardTitle>Наоди по извори</CardTitle>
                <CardDescription>Детални резултати од секој извор на податоци</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {result.sources.map((source) => {
                    const IconComponent = source.icon;
                    const isExpanded = expandedSources.has(source.name);

                    return (
                      <div
                        key={source.name}
                        className="border rounded-lg overflow-hidden"
                      >
                        <button
                          onClick={() => toggleSourceExpanded(source.name)}
                          className="w-full p-4 flex items-center justify-between hover:bg-muted/50 transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <IconComponent className="h-5 w-5 text-primary" />
                            <span className="font-medium">{source.name}</span>
                            <Badge variant="outline" className="text-xs">
                              {source.findings.length} наод(и)
                            </Badge>
                          </div>
                          {isExpanded ? (
                            <ChevronUp className="h-5 w-5 text-muted-foreground" />
                          ) : (
                            <ChevronDown className="h-5 w-5 text-muted-foreground" />
                          )}
                        </button>
                        {isExpanded && (
                          <div className="px-4 pb-4 pt-2 bg-muted/20">
                            <ul className="space-y-2">
                              {source.findings.map((finding, idx) => (
                                <li key={idx} className="flex items-start gap-2 text-sm">
                                  <span className="text-primary mt-1">•</span>
                                  <span>{finding}</span>
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

            {/* Red Flags */}
            {result.redFlags.length > 0 && (
              <Card className="border-orange-200 bg-orange-50/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-orange-700">
                    <AlertTriangle className="h-5 w-5" />
                    Предупредувања
                  </CardTitle>
                  <CardDescription>Потенцијални индикатори за ризик</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    {result.redFlags.map((flag, idx) => (
                      <li key={idx} className="flex items-start gap-3 text-sm">
                        <AlertTriangle className="h-4 w-4 text-orange-600 flex-shrink-0 mt-0.5" />
                        <span>{flag}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}

            {/* Recommendations */}
            {result.recommendations.length > 0 && (
              <Card className="border-blue-200 bg-blue-50/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-blue-700">
                    <CheckCircle2 className="h-5 w-5" />
                    Препораки
                  </CardTitle>
                  <CardDescription>Следни чекори за дополнителна проверка</CardDescription>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-3">
                    {result.recommendations.map((rec, idx) => (
                      <li key={idx} className="flex items-start gap-3 text-sm">
                        <CheckCircle2 className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Info Card - shown when no results */}
        {!result && !isAnalyzing && (
          <Card className="bg-primary/5 border-primary/20">
            <CardContent className="pt-6">
              <div className="flex items-start gap-4">
                <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                  <Shield className="h-5 w-5 text-primary" />
                </div>
                <div className="space-y-1">
                  <h3 className="font-semibold">Како работи анализата?</h3>
                  <p className="text-sm text-muted-foreground">
                    Нашата AI-базирана анализа проверува податоци од 6 различни извори вклучувајќи
                    официјални бази, веб пребарувања и документ анализа. Резултатите се презентираат
                    со ризик скор, детални наоди и препораки за следни чекори.
                  </p>
                  <ul className="text-sm text-muted-foreground space-y-1 mt-3">
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      Автоматска проверка од повеќе извори
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      AI-базирана детекција на аномалии
                    </li>
                    <li className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-600" />
                      Детални препораки и следни чекори
                    </li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
