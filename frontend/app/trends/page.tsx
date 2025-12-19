"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Clock,
  Trophy,
  DollarSign,
  Building,
  Calendar,
  Search,
  TrendingUp,
  Target,
  Lightbulb
} from "lucide-react";
import {
  UpcomingOpportunities,
  ActiveBuyers,
  TopWinners,
  PriceBenchmarks,
  SeasonalPatterns,
} from "@/components/insights";

export default function InsightsPage() {
  const [cpvFilter, setCpvFilter] = useState("");
  const [appliedCpv, setAppliedCpv] = useState<string | undefined>(undefined);

  const handleApplyFilter = () => {
    setAppliedCpv(cpvFilter.trim() || undefined);
  };

  const handleClearFilter = () => {
    setCpvFilter("");
    setAppliedCpv(undefined);
  };

  return (
    <div className="p-3 md:p-6 lg:p-8 space-y-6">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-xl md:text-3xl font-bold flex items-center gap-2">
          <TrendingUp className="h-6 w-6 md:h-8 md:w-8 text-primary" />
          Бизнис Анализа
        </h1>
        <p className="text-sm md:text-base text-muted-foreground">
          Корисни информации за да ги добиете тендерите - следете ги можностите, конкуренцијата и цените
        </p>
      </div>

      {/* Quick Tips Card */}
      <Card className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 border-blue-200 dark:border-blue-800">
        <CardContent className="pt-4 pb-4">
          <div className="flex items-start gap-3">
            <Lightbulb className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5 flex-shrink-0" />
            <div className="text-sm">
              <p className="font-medium text-blue-900 dark:text-blue-100">Совет за успех</p>
              <p className="text-blue-700 dark:text-blue-300">
                Следете ги <span className="font-semibold">итните можности</span> за тендери што се затвораат наскоро,
                анализирајте ја <span className="font-semibold">конкуренцијата</span> за да ја разберете пазарната позиција,
                и користете ги <span className="font-semibold">цените</span> за подобри понуди.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* CPV Filter */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Target className="h-4 w-4" />
            Филтрирај по индустрија (CPV код)
          </CardTitle>
          <CardDescription>
            Внесете CPV код за да ги видите податоците за вашата специфична индустрија
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col sm:flex-row gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="пр. 33 (медицина), 45 (градежништво), 30 (канцелариска опрема)"
                value={cpvFilter}
                onChange={(e) => setCpvFilter(e.target.value)}
                className="pl-9"
                onKeyDown={(e) => e.key === 'Enter' && handleApplyFilter()}
              />
            </div>
            <Button onClick={handleApplyFilter} disabled={!cpvFilter.trim()}>
              Примени
            </Button>
            {appliedCpv && (
              <Button variant="outline" onClick={handleClearFilter}>
                Ресетирај
              </Button>
            )}
          </div>
          {appliedCpv && (
            <p className="text-sm text-muted-foreground mt-2">
              Филтрирано по CPV: <span className="font-mono font-medium">{appliedCpv}</span>
            </p>
          )}
        </CardContent>
      </Card>

      {/* Main Tabs */}
      <Tabs defaultValue="opportunities" className="space-y-4">
        <TabsList className="grid w-full grid-cols-2 lg:grid-cols-5 h-auto gap-1">
          <TabsTrigger value="opportunities" className="flex items-center gap-1.5 py-2 px-2 text-xs sm:text-sm">
            <Clock className="h-4 w-4" />
            <span className="hidden sm:inline">Можности</span>
            <span className="sm:hidden">Итни</span>
          </TabsTrigger>
          <TabsTrigger value="competition" className="flex items-center gap-1.5 py-2 px-2 text-xs sm:text-sm">
            <Trophy className="h-4 w-4" />
            <span className="hidden sm:inline">Конкуренција</span>
            <span className="sm:hidden">Топ</span>
          </TabsTrigger>
          <TabsTrigger value="pricing" className="flex items-center gap-1.5 py-2 px-2 text-xs sm:text-sm">
            <DollarSign className="h-4 w-4" />
            <span>Цени</span>
          </TabsTrigger>
          <TabsTrigger value="buyers" className="flex items-center gap-1.5 py-2 px-2 text-xs sm:text-sm">
            <Building className="h-4 w-4" />
            <span className="hidden sm:inline">Купувачи</span>
            <span className="sm:hidden">Инст.</span>
          </TabsTrigger>
          <TabsTrigger value="seasonal" className="flex items-center gap-1.5 py-2 px-2 text-xs sm:text-sm">
            <Calendar className="h-4 w-4" />
            <span className="hidden sm:inline">Сезонски</span>
            <span className="sm:hidden">Кога</span>
          </TabsTrigger>
        </TabsList>

        {/* Upcoming Opportunities */}
        <TabsContent value="opportunities" className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">Следни можности</h2>
              <p className="text-sm text-muted-foreground">
                Тендери што се затвораат наскоро - не пропуштајте ги роковите
              </p>
            </div>
          </div>
          <UpcomingOpportunities cpvCode={appliedCpv} />
        </TabsContent>

        {/* Competition Analysis */}
        <TabsContent value="competition" className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Топ победници</h2>
            <p className="text-sm text-muted-foreground">
              Кои компании најчесто добиваат тендери - запознајте ја конкуренцијата
            </p>
          </div>
          <TopWinners />
        </TabsContent>

        {/* Price Benchmarks */}
        <TabsContent value="pricing" className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Анализа на цени</h2>
            <p className="text-sm text-muted-foreground">
              Просечни вредности по категории и сектори - понудете конкурентно
            </p>
          </div>
          <PriceBenchmarks />
        </TabsContent>

        {/* Active Buyers */}
        <TabsContent value="buyers" className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Најактивни купувачи</h2>
            <p className="text-sm text-muted-foreground">
              Институции кои објавуваат најмногу тендери - фокусирајте се на вистинските клиенти
            </p>
          </div>
          <ActiveBuyers />
        </TabsContent>

        {/* Seasonal Patterns */}
        <TabsContent value="seasonal" className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold">Сезонски шеми</h2>
            <p className="text-sm text-muted-foreground">
              Кога се објавуваат најмногу тендери - планирајте ги вашите ресурси
            </p>
          </div>
          <SeasonalPatterns />
        </TabsContent>
      </Tabs>
    </div>
  );
}
