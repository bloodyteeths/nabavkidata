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

interface TenderExplanationProps {
  tenderId: string;
  method?: 'shap' | 'lime' | 'combined';
  compact?: boolean;
  showRecommendations?: boolean;
}

const RISK_COLORS: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
  minimal: 'bg-green-500',
};

const RISK_LABELS: Record<string, string> = {
  critical: 'Kritichen',
  high: 'Visok',
  medium: 'Sreden',
  low: 'Nizok',
  minimal: 'Minimalen',
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
            Retry
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
              ML Analiza na Rizik
            </CardTitle>
            <CardDescription>
              {data.method === 'shap' && 'SHAP vrednosti'}
              {data.method === 'lime' && 'LIME objasnenija'}
              {data.method === 'combined' && 'Kombinirana analiza'}
              {data.method === 'flags' && 'Bazirana na indikatori'}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge className={`${RISK_COLORS[data.risk.level]} text-white`}>
              {RISK_LABELS[data.risk.level] || data.risk.level}
            </Badge>
            <span className="text-2xl font-bold" style={{ color: data.risk.color }}>
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
                <ChevronUp className="h-4 w-4 mr-2" /> Collapse
              </>
            ) : (
              <>
                <ChevronDown className="h-4 w-4 mr-2" /> Show Details
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
                  Faktori sto go zgolemuvaat rizikot
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
                </div>
              </div>
            )}

            {/* Risk Decreasing Factors */}
            {decreasingFactors.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2 text-green-600">
                  <TrendingDown className="h-4 w-4" />
                  Faktori sto go namaluvaat rizikot
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
                </div>
              </div>
            )}

            {/* Recommendations */}
            {showRecommendations && data.recommendations && data.recommendations.length > 0 && (
              <div className="pt-2 border-t">
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-yellow-500" />
                  Preporaki za istraga
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

            {/* Counterfactuals */}
            {data.counterfactuals && data.counterfactuals.length > 0 && (
              <div className="pt-2 border-t">
                <h4 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <Info className="h-4 w-4 text-blue-500" />
                  Sto bi go promenilo rizikot?
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
            )}

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
