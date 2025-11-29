"use client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface Series {
  key: string;
  label: string;
  color?: string;
}

interface PriceHistoryChartProps {
  data: Array<Record<string, any>>;
  xKey?: string;
  series: Series[];
  title?: string;
}

export function PriceHistoryChart({
  data,
  xKey = "date",
  series,
  title = "Историја на цени",
}: PriceHistoryChartProps) {
  // Don't show chart if there's only 1 data point - it's meaningless
  if (!data || data.length < 2) {
    return null;
  }

  const formatValue = (val: number) => {
    if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `${(val / 1_000).toFixed(0)}K`;
    return val?.toFixed ? val.toFixed(0) : String(val);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <XAxis dataKey={xKey} />
            <YAxis tickFormatter={formatValue} />
            <Tooltip
              formatter={(val: number) => `${formatValue(val)} МКД`}
              labelFormatter={(label) => `${label}`}
            />
            <Legend />
            {series.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color || "#8884d8"}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
