"use client"

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { formatDate } from "@/lib/utils"

interface TimelineData {
  date: string
  count: number
}

interface TenderTimelineProps {
  data: TimelineData[]
}

const formatTickDate = (dateString: string): string =>
  formatDate(dateString, { day: "numeric", month: "short" })

const formatTooltipDate = (dateString: string): string =>
  formatDate(dateString, { day: "numeric", month: "long", year: "numeric" })

export default function TenderTimeline({ data }: TenderTimelineProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Тендери низ време</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={350}>
          <LineChart
            data={data}
            margin={{
              top: 5,
              right: 30,
              left: 20,
              bottom: 5,
            }}
          >
            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
            <XAxis
              dataKey="date"
              tickFormatter={formatTickDate}
              tick={{ fontSize: 12 }}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 12 }}
              label={{
                value: "Број на тендери",
                angle: -90,
                position: "insideLeft",
                style: { fontSize: 12 },
              }}
            />
            <Tooltip
              labelFormatter={formatTooltipDate}
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
              }}
              labelStyle={{ color: "hsl(var(--foreground))", marginBottom: "8px" }}
              formatter={(value: number) => [value, "Тендери"]}
            />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={{ fill: "#3b82f6", r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}
