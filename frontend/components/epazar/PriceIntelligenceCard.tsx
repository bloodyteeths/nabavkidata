'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { TrendingUp, TrendingDown, Minus, AlertCircle, DollarSign, Users } from 'lucide-react';
import { formatCurrency } from '@/lib/utils';

export interface PriceIntelligence {
  product_name: string;
  recommended_bid_min_mkd?: number;
  recommended_bid_max_mkd?: number;
  market_min_mkd?: number;
  market_max_mkd?: number;
  market_avg_mkd?: number;
  trend: 'up' | 'down' | 'stable';
  trend_percentage?: number;
  competition_level: 'low' | 'medium' | 'high';
  sample_size: number;
}

interface PriceIntelligenceCardProps {
  data: PriceIntelligence;
  showProductName?: boolean;
}

export function PriceIntelligenceCard({ data, showProductName = true }: PriceIntelligenceCardProps) {
  const getTrendIcon = () => {
    switch (data.trend) {
      case 'up':
        return <TrendingUp className="h-4 w-4 text-red-500" />;
      case 'down':
        return <TrendingDown className="h-4 w-4 text-green-500" />;
      case 'stable':
        return <Minus className="h-4 w-4 text-gray-500" />;
      default:
        return null;
    }
  };

  const getTrendLabel = () => {
    switch (data.trend) {
      case 'up':
        return 'Растат';
      case 'down':
        return 'Опаѓаат';
      case 'stable':
        return 'Стабилни';
      default:
        return 'Непознато';
    }
  };

  const getTrendColor = () => {
    switch (data.trend) {
      case 'up':
        return 'text-red-600';
      case 'down':
        return 'text-green-600';
      case 'stable':
        return 'text-gray-600';
      default:
        return 'text-gray-600';
    }
  };

  const getCompetitionBadge = () => {
    switch (data.competition_level) {
      case 'low':
        return <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">Ниска конкуренција</Badge>;
      case 'medium':
        return <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">Средна конкуренција</Badge>;
      case 'high':
        return <Badge variant="outline" className="bg-red-50 text-red-700 border-red-200">Висока конкуренција</Badge>;
      default:
        return null;
    }
  };

  return (
    <Card className="border-primary/30 bg-gradient-to-br from-blue-50/50 to-purple-50/50">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <CardTitle className="text-lg flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-blue-600" />
              Ценовна Интелигенција
            </CardTitle>
            {showProductName && (
              <CardDescription className="mt-1 font-medium">{data.product_name}</CardDescription>
            )}
          </div>
          {getCompetitionBadge()}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Recommended Bid Range */}
        <div className="bg-white/80 p-4 rounded-lg border border-blue-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-gray-600">Препорачан опсег на понуда</span>
            <AlertCircle className="h-4 w-4 text-blue-500" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-blue-600">
              {formatCurrency(data.recommended_bid_min_mkd)}
            </span>
            <span className="text-gray-400">-</span>
            <span className="text-2xl font-bold text-blue-600">
              {formatCurrency(data.recommended_bid_max_mkd)}
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            Базирано на {data.sample_size} слични тендери
          </p>
        </div>

        {/* Market Price Stats */}
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-white/60 p-3 rounded-lg border">
            <p className="text-xs text-gray-500 mb-1">Мин. цена</p>
            <p className="text-sm font-semibold text-green-600">
              {formatCurrency(data.market_min_mkd)}
            </p>
          </div>
          <div className="bg-white/60 p-3 rounded-lg border">
            <p className="text-xs text-gray-500 mb-1">Просечна</p>
            <p className="text-sm font-semibold text-blue-600">
              {formatCurrency(data.market_avg_mkd)}
            </p>
          </div>
          <div className="bg-white/60 p-3 rounded-lg border">
            <p className="text-xs text-gray-500 mb-1">Макс. цена</p>
            <p className="text-sm font-semibold text-red-600">
              {formatCurrency(data.market_max_mkd)}
            </p>
          </div>
        </div>

        {/* Trend Indicator */}
        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center gap-2">
            {getTrendIcon()}
            <span className="text-sm font-medium">Трендови на цените:</span>
            <span className={`text-sm font-semibold ${getTrendColor()}`}>
              {getTrendLabel()}
              {data.trend_percentage && (
                <span className="ml-1">({data.trend_percentage > 0 ? '+' : ''}{data.trend_percentage.toFixed(1)}%)</span>
              )}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
