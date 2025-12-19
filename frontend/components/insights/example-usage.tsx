/**
 * Example: How to use SeasonalPatterns component
 *
 * This file demonstrates different ways to use the SeasonalPatterns component.
 * You can copy these examples into your pages or components.
 */

'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import SeasonalPatterns from './SeasonalPatterns';

// Example 1: Basic Usage with Loading State
export function SeasonalPatternsExample() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSeasonalPatterns()
      .then((result) => setData(result))
      .catch((err) => {
        console.error('Failed to fetch seasonal patterns:', err);
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, []);

  if (error) {
    return (
      <div className="p-4 rounded-lg border border-red-200 bg-red-50">
        <p className="text-sm text-red-800">Failed to load seasonal patterns: {error}</p>
      </div>
    );
  }

  return <SeasonalPatterns data={data} loading={loading} />;
}

// Example 2: Server Component (Next.js App Router)
// File: app/insights/page.tsx
/*
import { api } from '@/lib/api';
import SeasonalPatterns from '@/components/insights/SeasonalPatterns';

export default async function InsightsPage() {
  const data = await api.getSeasonalPatterns();

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Seasonal Insights</h1>
        <p className="text-muted-foreground">
          Understand tender patterns and plan your bidding strategy
        </p>
      </div>

      <SeasonalPatterns data={data} />
    </div>
  );
}
*/

// Example 3: With Error Boundary and Suspense
/*
import { Suspense } from 'react';
import { api } from '@/lib/api';
import SeasonalPatterns from '@/components/insights/SeasonalPatterns';
import { Card, CardContent } from '@/components/ui/card';

async function SeasonalPatternsData() {
  const data = await api.getSeasonalPatterns();
  return <SeasonalPatterns data={data} />;
}

export default function InsightsPage() {
  return (
    <div className="container mx-auto p-6">
      <Suspense fallback={<SeasonalPatterns data={null} loading={true} />}>
        <SeasonalPatternsData />
      </Suspense>
    </div>
  );
}
*/

// Example 4: Integration in a Dashboard
/*
'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import SeasonalPatterns from '@/components/insights/SeasonalPatterns';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function DashboardInsights() {
  const [seasonalData, setSeasonalData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.getSeasonalPatterns(),
      // Add other insight endpoints here
    ])
      .then(([seasonal]) => {
        setSeasonalData(seasonal);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <Tabs defaultValue="seasonal" className="w-full">
      <TabsList>
        <TabsTrigger value="seasonal">Seasonal Patterns</TabsTrigger>
        <TabsTrigger value="buyers">Active Buyers</TabsTrigger>
        <TabsTrigger value="winners">Top Winners</TabsTrigger>
      </TabsList>

      <TabsContent value="seasonal">
        <SeasonalPatterns data={seasonalData} loading={loading} />
      </TabsContent>

      <TabsContent value="buyers">
        <p>Add other insight components here</p>
      </TabsContent>

      <TabsContent value="winners">
        <p>Add other insight components here</p>
      </TabsContent>
    </Tabs>
  );
}
*/

// Mock data for testing/development
export const MOCK_SEASONAL_DATA = {
  monthly_data: [
    {
      month: "2024-01",
      month_name: "Јануари",
      total_count: 145,
      total_value: 125000000,
      by_category: { "Стоки": 65, "Услуги": 50, "Работи": 30 }
    },
    {
      month: "2024-02",
      month_name: "Февруари",
      total_count: 132,
      total_value: 98000000,
      by_category: { "Стоки": 58, "Услуги": 45, "Работи": 29 }
    },
    {
      month: "2024-03",
      month_name: "Март",
      total_count: 189,
      total_value: 156000000,
      by_category: { "Стоки": 92, "Услуги": 62, "Работи": 35 }
    },
    {
      month: "2024-04",
      month_name: "Април",
      total_count: 176,
      total_value: 142000000,
      by_category: { "Стоки": 85, "Услуги": 58, "Работи": 33 }
    },
    {
      month: "2024-05",
      month_name: "Мај",
      total_count: 163,
      total_value: 135000000,
      by_category: { "Стоки": 72, "Услуги": 61, "Работи": 30 }
    },
    {
      month: "2024-06",
      month_name: "Јуни",
      total_count: 154,
      total_value: 128000000,
      by_category: { "Стоки": 68, "Услуги": 56, "Работи": 30 }
    },
    {
      month: "2024-07",
      month_name: "Јули",
      total_count: 98,
      total_value: 76000000,
      by_category: { "Стоки": 42, "Услуги": 38, "Работи": 18 }
    },
    {
      month: "2024-08",
      month_name: "Август",
      total_count: 67,
      total_value: 52000000,
      by_category: { "Стоки": 28, "Услуги": 25, "Работи": 14 }
    },
    {
      month: "2024-09",
      month_name: "Септември",
      total_count: 182,
      total_value: 148000000,
      by_category: { "Стоки": 78, "Услуги": 64, "Работи": 40 }
    },
    {
      month: "2024-10",
      month_name: "Октомври",
      total_count: 195,
      total_value: 162000000,
      by_category: { "Стоки": 82, "Услуги": 68, "Работи": 45 }
    },
    {
      month: "2024-11",
      month_name: "Ноември",
      total_count: 171,
      total_value: 138000000,
      by_category: { "Стоки": 74, "Услуги": 60, "Работи": 37 }
    },
    {
      month: "2024-12",
      month_name: "Декември",
      total_count: 125,
      total_value: 102000000,
      by_category: { "Стоки": 56, "Услуги": 45, "Работи": 24 }
    }
  ],
  best_months: {
    "Стоки": ["Март", "Април"],
    "Услуги": ["Мај", "Октомври"],
    "Работи": ["Септември", "Октомври"]
  }
};

// Example 5: Using mock data for development
export function SeasonalPatternsWithMockData() {
  return <SeasonalPatterns data={MOCK_SEASONAL_DATA} loading={false} />;
}
