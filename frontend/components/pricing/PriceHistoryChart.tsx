"use client";

import { useMemo } from "react";
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  TooltipProps,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export interface PriceDataPoint {
  period: string;
  tender_count: number;
  avg_estimated_mkd: number;
  avg_awarded_mkd: number;
  avg_discount_pct: number;
  avg_bidders: number;
}

export interface PriceHistoryChartProps {
  data: PriceDataPoint[];
  cpvCode: string;
  title?: string;
  showTrend?: boolean;
  trend?: "increasing" | "decreasing" | "stable";
  trendPct?: number;
}

/**
 * PriceHistoryChart - Advanced price history visualization component
 *
 * Features:
 * - Line chart showing estimated vs actual/winning values over time
 * - Area fill showing savings between lines
 * - Trend indicator with percentage change
 * - Responsive design with Macedonian labels
 * - Tooltip with detailed period information
 */
export function PriceHistoryChart({
  data,
  cpvCode,
  title = "Историја на цени",
  showTrend = true,
  trend,
  trendPct,
}: PriceHistoryChartProps) {
  // Don't show chart if there's insufficient data
  if (!data || data.length < 2) {
    return null;
  }

  // Calculate trend if not provided
  const calculatedTrend = useMemo(() => {
    if (trend && trendPct !== undefined) {
      return { direction: trend, percentage: trendPct };
    }

    // Calculate trend from first to last data point
    const firstPoint = data[0];
    const lastPoint = data[data.length - 1];

    if (!firstPoint.avg_estimated_mkd || !lastPoint.avg_estimated_mkd) {
      return { direction: "stable" as const, percentage: 0 };
    }

    const change = ((lastPoint.avg_estimated_mkd - firstPoint.avg_estimated_mkd) / firstPoint.avg_estimated_mkd) * 100;

    let direction: "increasing" | "decreasing" | "stable";
    if (Math.abs(change) < 5) {
      direction = "stable";
    } else if (change > 0) {
      direction = "increasing";
    } else {
      direction = "decreasing";
    }

    return { direction, percentage: Math.abs(change) };
  }, [data, trend, trendPct]);

  // Format currency values for display
  const formatCurrency = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return "N/A";

    if (value >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(1)}M`;
    }
    if (value >= 1_000) {
      return `${(value / 1_000).toFixed(0)}K`;
    }
    return value.toFixed(0);
  };

  // Format full currency with thousands separators
  const formatFullCurrency = (value: number | null | undefined): string => {
    if (value === null || value === undefined) return "N/A";
    return new Intl.NumberFormat("mk-MK", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  // Custom tooltip component
  const CustomTooltip = ({ active, payload, label }: TooltipProps<number, string>) => {
    if (!active || !payload || payload.length === 0) return null;

    const data = payload[0].payload as PriceDataPoint;

    return (
      <div className="bg-background border border-border rounded-lg shadow-lg p-4">
        <p className="font-semibold text-sm mb-2">{label}</p>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Проценета вредност:</span>
            <span className="font-medium text-primary">
              {formatFullCurrency(data.avg_estimated_mkd)} МКД
            </span>
          </div>
          {data.avg_awarded_mkd && (
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Добиена понуда:</span>
              <span className="font-medium text-green-600">
                {formatFullCurrency(data.avg_awarded_mkd)} МКД
              </span>
            </div>
          )}
          {data.avg_awarded_mkd && data.avg_estimated_mkd && (
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Заштеда:</span>
              <span className="font-medium text-primary">
                {((1 - data.avg_awarded_mkd / data.avg_estimated_mkd) * 100).toFixed(1)}%
              </span>
            </div>
          )}
          <div className="flex justify-between gap-4 pt-1 border-t">
            <span className="text-muted-foreground">Број на тендери:</span>
            <span className="font-medium">{data.tender_count}</span>
          </div>
          {data.avg_bidders && (
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">Просечен број понуди:</span>
              <span className="font-medium">{data.avg_bidders.toFixed(1)}</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  // Trend icon based on direction
  const TrendIcon = () => {
    if (calculatedTrend.direction === "increasing") {
      return <TrendingUp className="h-4 w-4 text-red-500" />;
    } else if (calculatedTrend.direction === "decreasing") {
      return <TrendingDown className="h-4 w-4 text-green-500" />;
    }
    return <Minus className="h-4 w-4 text-muted-foreground" />;
  };

  // Trend label
  const getTrendLabel = () => {
    if (calculatedTrend.direction === "increasing") {
      return `Растечки (+${calculatedTrend.percentage.toFixed(1)}%)`;
    } else if (calculatedTrend.direction === "decreasing") {
      return `Опаѓачки (-${calculatedTrend.percentage.toFixed(1)}%)`;
    }
    return `Стабилен (~${calculatedTrend.percentage.toFixed(1)}%)`;
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <span>{title}</span>
              {cpvCode && (
                <span className="text-sm font-normal text-muted-foreground">
                  CPV {cpvCode}
                </span>
              )}
            </CardTitle>
            {showTrend && (
              <CardDescription className="flex items-center gap-2 mt-2">
                <TrendIcon />
                <span>Тренд: {getTrendLabel()}</span>
              </CardDescription>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <AreaChart
            data={data}
            margin={{
              top: 10,
              right: 10,
              left: 0,
              bottom: 0,
            }}
          >
            <defs>
              <linearGradient id="savingsGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="period"
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--border))" }}
            />
            <YAxis
              tickFormatter={formatCurrency}
              tick={{ fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "hsl(var(--border))" }}
              label={{
                value: "МКД",
                angle: -90,
                position: "insideLeft",
                style: { fontSize: 12 },
              }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: "14px", paddingTop: "10px" }}
              iconType="line"
            />

            {/* Area showing savings between estimated and actual */}
            <Area
              type="monotone"
              dataKey="avg_awarded_mkd"
              fill="url(#savingsGradient)"
              stroke="none"
              fillOpacity={1}
              name="Заштеда"
              isAnimationActive={true}
            />

            {/* Estimated value line */}
            <Line
              type="monotone"
              dataKey="avg_estimated_mkd"
              stroke="hsl(var(--primary))"
              strokeWidth={2.5}
              dot={{ fill: "hsl(var(--primary))", r: 4 }}
              activeDot={{ r: 6 }}
              name="Проценета вредност"
              isAnimationActive={true}
            />

            {/* Actual/Winning value line */}
            <Line
              type="monotone"
              dataKey="avg_awarded_mkd"
              stroke="#22c55e"
              strokeWidth={2.5}
              dot={{ fill: "#22c55e", r: 4 }}
              activeDot={{ r: 6 }}
              name="Добиена понуда"
              isAnimationActive={true}
            />
          </AreaChart>
        </ResponsiveContainer>

        {/* Summary stats below chart */}
        <div className="grid grid-cols-3 gap-4 mt-6 pt-4 border-t">
          <div className="text-center">
            <p className="text-xs text-muted-foreground mb-1">Вкупно тендери</p>
            <p className="text-lg font-semibold">
              {data.reduce((sum, d) => sum + d.tender_count, 0)}
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground mb-1">Просечна проценета</p>
            <p className="text-lg font-semibold text-primary">
              {formatCurrency(
                data.reduce((sum, d) => sum + (d.avg_estimated_mkd || 0), 0) / data.length
              )} МКД
            </p>
          </div>
          <div className="text-center">
            <p className="text-xs text-muted-foreground mb-1">Просечна добиена</p>
            <p className="text-lg font-semibold text-green-600">
              {formatCurrency(
                data.reduce((sum, d) => sum + (d.avg_awarded_mkd || 0), 0) /
                  data.filter((d) => d.avg_awarded_mkd).length
              )} МКД
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
