"use client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

interface PriceHistoryChartProps {
  data: Array<{
    period: string;
    avg_estimated: number;
    avg_awarded: number;
    count: number;
  }>;
  title?: string;
}

export function PriceHistoryChart({ data, title = "Историја на цени" }: PriceHistoryChartProps) {
  const formatValue = (val: number) => {
    if (val >= 1000000) return `${(val / 1000000).toFixed(1)}M`;
    if (val >= 1000) return `${(val / 1000).toFixed(0)}K`;
    return val.toFixed(0);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <XAxis dataKey="period" />
            <YAxis tickFormatter={formatValue} />
            <Tooltip
              formatter={(val: number) => `${formatValue(val)} МКД`}
              labelFormatter={(label) => `Период: ${label}`}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="avg_estimated"
              name="Просечна проценета"
              stroke="#8884d8"
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="avg_awarded"
              name="Просечна доделена"
              stroke="#82ca9d"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
