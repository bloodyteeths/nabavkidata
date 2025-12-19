"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { api } from "@/lib/api"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Building, TrendingUp, TrendingDown, MapPin } from "lucide-react"
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts"

interface ActiveBuyer {
  entity_name: string
  tender_count: number
  total_value: number | null
  categories_breakdown: Record<string, number> // e.g., {"Стоки": 5, "Услуги": 3}
  trend?: number // percentage change from previous period
}

interface ActiveBuyersResponse {
  buyers: ActiveBuyer[]
}

interface ActiveBuyersProps {
  category?: string
}

const CATEGORY_COLORS: Record<string, string> = {
  "Стоки": "#3b82f6",      // blue
  "Услуги": "#10b981",     // green
  "Работи": "#f59e0b",     // amber
  "Други": "#8b5cf6",      // purple
}

// Format number to MKD currency
const formatMKD = (value: number): string => {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M MKD`
  } else if (value >= 1_000) {
    return `${(value / 1_000).toFixed(0)}K MKD`
  }
  return `${value.toLocaleString()} MKD`
}

export default function ActiveBuyers({ category }: ActiveBuyersProps) {
  const router = useRouter()
  const [buyers, setBuyers] = useState<ActiveBuyer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchActiveBuyers = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await api.getActiveBuyers(category)
        setBuyers(response.buyers)
      } catch (err) {
        console.error("Error fetching active buyers:", err)
        setError("Failed to load active buyers. Please try again later.")
      } finally {
        setLoading(false)
      }
    }

    fetchActiveBuyers()
  }, [category])

  const handleBuyerClick = (entityName: string) => {
    // Navigate to tenders page with entity filter
    router.push(`/tenders?entity=${encodeURIComponent(entityName)}`)
  }

  const renderCategoryBreakdown = (categories: Record<string, number>) => {
    // Calculate total
    const total = Object.values(categories).reduce((sum, count) => sum + count, 0)

    // If no categories, return null
    if (total === 0) return null

    // Prepare data for pie chart
    const chartData = Object.entries(categories).map(([category, count]) => ({
      name: category,
      value: count,
      percentage: ((count / total) * 100).toFixed(0),
    }))

    return (
      <div className="flex items-center gap-3">
        {/* Mini Pie Chart */}
        <div className="w-16 h-16 flex-shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                innerRadius={12}
                outerRadius={28}
                paddingAngle={2}
                dataKey="value"
              >
                {chartData.map((entry, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={CATEGORY_COLORS[entry.name] || "#9ca3af"}
                  />
                ))}
              </Pie>
              <Tooltip
                formatter={(value: number) => [`${value} тендери`, "Број"]}
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "6px",
                  fontSize: "12px",
                }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Category Badges */}
        <div className="flex flex-wrap gap-1.5">
          {chartData.map((item) => (
            <Badge
              key={item.name}
              variant="outline"
              className="text-xs"
              style={{
                borderColor: CATEGORY_COLORS[item.name] || "#9ca3af",
                color: CATEGORY_COLORS[item.name] || "#9ca3af",
              }}
            >
              {item.name}: {item.percentage}%
            </Badge>
          ))}
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {[...Array(8)].map((_, i) => (
          <Card key={i} className="animate-pulse">
            <CardHeader>
              <div className="h-4 bg-muted rounded w-3/4"></div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="h-8 bg-muted rounded w-1/2"></div>
                <div className="h-4 bg-muted rounded w-full"></div>
                <div className="h-16 bg-muted rounded w-full"></div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <Card className="p-6">
        <div className="text-center text-muted-foreground">
          <p>{error}</p>
        </div>
      </Card>
    )
  }

  if (buyers.length === 0) {
    return (
      <Card className="p-6">
        <div className="text-center text-muted-foreground">
          <Building className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>Не се пронајдени активни набавувачи за избраниот период.</p>
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Активни набавувачи</h2>
          <p className="text-sm text-muted-foreground">
            Топ 20 институции со најмногу објавени тендери во последните 90 дена
          </p>
        </div>
        <Badge variant="secondary" className="text-sm">
          {buyers.length} институции
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {buyers.map((buyer, index) => (
          <Card
            key={buyer.entity_name}
            className="hover:shadow-lg transition-all cursor-pointer hover:border-primary/50"
            onClick={() => handleBuyerClick(buyer.entity_name)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Building className="w-4 h-4 text-primary flex-shrink-0" />
                    <span className="text-xs text-muted-foreground">#{index + 1}</span>
                  </div>
                  <CardTitle className="text-sm leading-tight line-clamp-2">
                    {buyer.entity_name}
                  </CardTitle>
                </div>
                {buyer.trend !== undefined && buyer.trend !== 0 && (
                  <div
                    className={`flex items-center gap-0.5 text-xs flex-shrink-0 ${
                      buyer.trend > 0 ? "text-green-600" : "text-red-600"
                    }`}
                  >
                    {buyer.trend > 0 ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : (
                      <TrendingDown className="w-3 h-3" />
                    )}
                    <span className="font-medium">{Math.abs(buyer.trend)}%</span>
                  </div>
                )}
              </div>
            </CardHeader>

            <CardContent className="space-y-3">
              {/* Tender Count - Big Number */}
              <div>
                <div className="text-3xl font-bold text-primary">
                  {buyer.tender_count}
                </div>
                <div className="text-xs text-muted-foreground">
                  активни тендери
                </div>
              </div>

              {/* Total Value */}
              <div>
                <div className="text-sm font-semibold text-foreground">
                  {buyer.total_value ? formatMKD(buyer.total_value) : "Н/Д"}
                </div>
                <div className="text-xs text-muted-foreground">
                  вкупна проценета вредност
                </div>
              </div>

              {/* Category Breakdown */}
              {renderCategoryBreakdown(buyer.categories_breakdown || {})}

              {/* Click indicator */}
              <div className="pt-2 border-t">
                <div className="text-xs text-muted-foreground flex items-center gap-1">
                  <MapPin className="w-3 h-3" />
                  Кликни за сите тендери
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
