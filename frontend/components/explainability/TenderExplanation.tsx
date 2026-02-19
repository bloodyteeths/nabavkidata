'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Lightbulb,
  RefreshCw,
  Info,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';

interface FeatureFactor {
  name: string;
  display_name: string;
  value: number;
  contribution: number;
  direction: 'increases_risk' | 'decreases_risk';
  importance_rank: number;
  description?: string;
  category?: string;
}

interface TenderExplanationData {
  tender_id: string;
  risk: { probability: number; level: string; color: string };
  method: string;
  factors: FeatureFactor[];
  summary: string;
  recommendations?: string[];
  counterfactuals?: string[];
  model_fidelity?: number;
  cached: boolean;
  generated_at: string;
}

interface CounterfactualChange {
  feature: string;
  from: number;
  to: number;
  description_en: string;
  description_mk: string;
  direction: string;
  feasibility: number;
}

interface DiCECounterfactual {
  counterfactual_score: number;
  changes: CounterfactualChange[];
  num_changes: number;
  feasibility_score: number;
  distance: number;
}

interface DiCECounterfactualResponse {
  tender_id: string;
  original_score: number;
  counterfactuals: DiCECounterfactual[];
  generated_at: string;
}

interface TenderExplanationProps {
  tenderId: string;
  method?: 'shap' | 'lime' | 'combined';
  compact?: boolean;
  showRecommendations?: boolean;
}

const API_URL = (typeof window !== 'undefined')
  ? (window.location.hostname === 'localhost' ? 'http://localhost:8000' : 'https://api.nabavkidata.com')
  : 'https://api.nabavkidata.com';

const RISK_COLORS: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
  minimal: 'bg-green-500',
};

const RISK_TEXT_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#3b82f6',
  minimal: '#22c55e',
};

const RISK_LABELS: Record<string, string> = {
  critical: 'Критичен',
  high: 'Висок',
  medium: 'Среден',
  low: 'Низок',
  minimal: 'Минимален',
};

export function TenderExplanation({
  tenderId,
  method = 'combined',
  compact = false,
  showRecommendations = true,
}: TenderExplanationProps) {
  const [data, setData] = useState<TenderExplanationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(!compact);
  const [diceData, setDiceData] = useState<DiCECounterfactualResponse | null>(null);
  const [diceLoading, setDiceLoading] = useState(false);

  const fetchExplanation = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.getTenderExplanation(tenderId, method);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load explanation');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExplanation();
  }, [tenderId, method]);

  // Fetch DiCE counterfactuals after explanation loads
  useEffect(() => {
    if (!data) return;
    const fetchDiCECounterfactuals = async () => {
      setDiceLoading(true);
      try {
        const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const encodedId = encodeURIComponent(tenderId);
        const response = await fetch(`${API_URL}/api/corruption/counterfactuals/${encodedId}/actionable`, { headers });
        if (response.ok) {
          const result: DiCECounterfactualResponse = await response.json();
          setDiceData(result);
        }
      } catch {
        // Silently fail — fall back to basic counterfactuals from data.counterfactuals
      } finally {
        setDiceLoading(false);
      }
    };
    fetchDiCECounterfactuals();
  }, [data, tenderId]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-16 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="border-red-200 bg-red-50">
        <CardContent className="pt-6">
          <div className="flex items-center gap-2 text-red-600">
            <AlertTriangle className="h-5 w-5" />
            <span>{error}</span>
          </div>
          <Button variant="outline" size="sm" className="mt-4" onClick={fetchExplanation}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Обиди се повторно
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!data) return null;

  const increasingFactors = data.factors.filter((f) => f.direction === 'increases_risk');
  const decreasingFactors = data.factors.filter((f) => f.direction === 'decreases_risk');

  // Calculate max contribution for scaling bars
  const maxContribution = Math.max(...data.factors.map((f) => f.contribution), 0.1);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              ML Анализа на Ризик
            </CardTitle>
            <CardDescription>
              {data.method === 'shap' && 'SHAP вредности'}
              {data.method === 'lime' && 'LIME објаснувања'}
              {data.method === 'combined' && 'Комбинирана анализа'}
              {data.method === 'flags' && 'Базирана на индикатори'}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge className={`${RISK_COLORS[data.risk.level]} text-white`}>
              {RISK_LABELS[data.risk.level] || data.risk.level}
            </Badge>
            <span className="text-2xl font-bold" style={{ color: data.risk.color || RISK_TEXT_COLORS[data.risk.level] || '#6b7280' }}>
              {(data.risk.probability * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Summary */}
        <div className="p-3 bg-muted rounded-lg">
          <p className="text-sm">{data.summary}</p>
        </div>

        {/* Toggle for compact mode */}
        {compact && (
          <Button
            variant="ghost"
            size="sm"
            className="w-full"
            onClick={() => setExpanded(!expanded)}
          >
            {expanded ? (
              <>
                <ChevronUp className="h-4 w-4 mr-2" /> Собери
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4 mr-2" /> Прикажи детали
              </>
            )}
          </Button>
        )}

        {expanded && (
          <>
            {/* Risk Increasing Factors */}
            {increasingFactors.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2 text-red-600">
                  <TrendingUp className="h-4 w-4" />
                  Фактори што го зголемуваат ризикот
                </h4>
                <div className="space-y-2">
                  {increasingFactors.slice(0, 7).map((factor) => (
                    <FactorBar
                      key={factor.name}
                      factor={factor}
                      maxContribution={maxContribution}
                      color="red"
                    />
                  ))}
                  {increasingFactors.length > 7 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Прикажани 7 од {increasingFactors.length} фактори
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Risk Decreasing Factors */}
            {decreasingFactors.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2 text-green-600">
                  <TrendingDown className="h-4 w-4" />
                  Фактори што го намалуваат ризикот
                </h4>
                <div className="space-y-2">
                  {decreasingFactors.slice(0, 5).map((factor) => (
                    <FactorBar
                      key={factor.name}
                      factor={factor}
                      maxContribution={maxContribution}
                      color="green"
                    />
                  ))}
                  {decreasingFactors.length > 5 && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Прикажани 5 од {decreasingFactors.length} фактори
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Recommendations */}
            {showRecommendations && data.recommendations && data.recommendations.length > 0 && (
              <div className="pt-2 border-t">
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-yellow-500" />
                  Препораки за истрага
                </h4>
                <ul className="space-y-1">
                  {data.recommendations.map((rec, i) => (
                    <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                      <span className="text-yellow-500">•</span>
                      {rec}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* DiCE Counterfactuals */}
            {(diceData && diceData.counterfactuals.length > 0) ? (
              <div className="pt-2 border-t">
                <h4 className="text-sm font-medium mb-3 flex items-center gap-2 text-emerald-700">
                  <Lightbulb className="h-4 w-4 text-emerald-500" />
                  Како да се намали ризикот?
                </h4>
                <div className="space-y-3">
                  {diceData.counterfactuals.slice(0, 3).map((cf, idx) => (
                    <div key={idx} className="rounded-lg border border-emerald-200 bg-gradient-to-r from-emerald-50/50 to-blue-50/50 p-3">
                      {/* Score transition */}
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-sm font-semibold text-red-600">
                          {diceData.original_score.toFixed(0)}
                        </span>
                        <ArrowRight className="h-4 w-4 text-emerald-500" />
                        <span className="text-sm font-semibold text-emerald-600">
                          {cf.counterfactual_score.toFixed(0)}
                        </span>
                        <span className="text-xs text-muted-foreground ml-1">ризик скор</span>
                        <Badge
                          variant="outline"
                          className={`ml-auto text-xs ${
                            cf.feasibility_score >= 0.7
                              ? 'border-emerald-300 text-emerald-700 bg-emerald-50'
                              : cf.feasibility_score >= 0.4
                              ? 'border-yellow-300 text-yellow-700 bg-yellow-50'
                              : 'border-red-300 text-red-700 bg-red-50'
                          }`}
                        >
                          {(cf.feasibility_score * 100).toFixed(0)}% изводливо
                        </Badge>
                      </div>
                      {/* Changes list */}
                      <div className="space-y-1.5">
                        {cf.changes.map((change, cIdx) => (
                          <div key={cIdx} className="flex items-start gap-2">
                            {change.feasibility >= 0.6 ? (
                              <CheckCircle2 className="h-4 w-4 text-emerald-500 mt-0.5 shrink-0" />
                            ) : (
                              <AlertTriangle className="h-4 w-4 text-yellow-500 mt-0.5 shrink-0" />
                            )}
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-foreground">{change.description_mk}</p>
                              <div className="flex items-center gap-2 mt-0.5">
                                <div className="h-1.5 flex-1 bg-gray-200 rounded-full overflow-hidden max-w-[120px]">
                                  <div
                                    className={`h-full rounded-full transition-all duration-500 ${
                                      change.feasibility >= 0.7 ? 'bg-emerald-500' : change.feasibility >= 0.4 ? 'bg-yellow-500' : 'bg-red-400'
                                    }`}
                                    style={{ width: `${change.feasibility * 100}%` }}
                                  />
                                </div>
                                <span className="text-xs text-muted-foreground">
                                  {(change.feasibility * 100).toFixed(0)}%
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : diceLoading ? (
              <div className="pt-2 border-t">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  Се вчитуваат контрафактуални објаснувања...
                </div>
              </div>
            ) : data.counterfactuals && data.counterfactuals.length > 0 ? (
              <div className="pt-2 border-t">
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <Info className="h-4 w-4 text-blue-500" />
                  Што би го променило ризикот?
                </h4>
                <ul className="space-y-1">
                  {data.counterfactuals.map((cf, i) => (
                    <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                      <span className="text-blue-500">•</span>
                      {cf}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* Model Fidelity */}
            {data.model_fidelity && (
              <div className="pt-2 border-t text-xs text-muted-foreground flex items-center justify-between">
                <span>Доверба на модел: {(data.model_fidelity * 100).toFixed(1)}%</span>
                <span>Генерирано: {new Date(data.generated_at).toLocaleString('mk-MK')}</span>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

interface FactorBarProps {
  factor: FeatureFactor;
  maxContribution: number;
  color: 'red' | 'green';
}

function FactorBar({ factor, maxContribution, color }: FactorBarProps) {
  const width = Math.min((factor.contribution / maxContribution) * 100, 100);
  const bgColor = color === 'red' ? 'bg-red-500' : 'bg-green-500';
  const bgColorLight = color === 'red' ? 'bg-red-100' : 'bg-green-100';

  return (
    <div className="group">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium truncate flex-1">{factor.display_name}</span>
        <span className="text-xs text-muted-foreground ml-2">
          {(factor.contribution * 100).toFixed(1)}%
        </span>
      </div>
      <div className={`h-2 ${bgColorLight} rounded-full overflow-hidden`}>
        <div
          className={`h-full ${bgColor} rounded-full transition-all duration-500`}
          style={{ width: `${width}%` }}
        />
      </div>
      {factor.description && (
        <p className="text-xs text-muted-foreground mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          {factor.description}
        </p>
      )}
    </div>
  );
}

export default TenderExplanation;
