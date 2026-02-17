"use client";

import { useState, useEffect, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Clock,
  DollarSign,
  Building,
  Calendar,
  Search,
  TrendingUp,
  Target,
  Lightbulb,
  Loader2,
  Lock
} from "lucide-react";
import {
  UpcomingOpportunities,
  ActiveBuyers,
  PriceBenchmarks,
  SeasonalPatterns,
} from "@/components/insights";
import { api } from "@/lib/api";
import Link from "next/link";

export default function InsightsPage() {
  const [tier, setTier] = useState<string>("free");
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [cpvFilter, setCpvFilter] = useState("");
  const [appliedCpv, setAppliedCpv] = useState<string | undefined>(undefined);

  // CPV autocomplete state
  const [cpvOptions, setCpvOptions] = useState<Array<{ code: string; name: string; name_mk: string }>>([]);
  const [cpvLoading, setCpvLoading] = useState(false);
  const [showCpvDropdown, setShowCpvDropdown] = useState(false);

  // Check subscription tier
  useEffect(() => {
    async function checkAuth() {
      try {
        const status = await api.getSubscriptionStatus();
        setTier(status.tier || "free");
        setIsLoggedIn(true);
      } catch {
        setTier("free");
        setIsLoggedIn(false);
      } finally {
        setAuthChecked(true);
      }
    }
    checkAuth();
  }, []);

  // CPV search with debounce
  const searchCPV = useCallback(async (search: string) => {
    if (search.length < 2) {
      setCpvOptions([]);
      return;
    }
    setCpvLoading(true);
    try {
      const response = await api.searchCPVCodes(search, 15);
      setCpvOptions(response.results || []);
    } catch (error) {
      console.error("CPV search failed:", error);
      setCpvOptions([]);
    } finally {
      setCpvLoading(false);
    }
  }, []);

  // Debounced CPV search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (cpvFilter) searchCPV(cpvFilter);
    }, 300);
    return () => clearTimeout(timer);
  }, [cpvFilter, searchCPV]);

  const handleApplyFilter = () => {
    setAppliedCpv(cpvFilter.trim() || undefined);
    setShowCpvDropdown(false);
  };

  const handleClearFilter = () => {
    setCpvFilter("");
    setAppliedCpv(undefined);
    setCpvOptions([]);
  };

  // Tier gate: Insights/Trends requires Start+
  if (!authChecked) {
    return (
      <div className="p-6 flex justify-center items-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isLoggedIn || tier === "free") {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <TrendingUp className="h-6 w-6 text-primary" />
            Бизнис Анализа
          </h1>
          <p className="text-sm text-muted-foreground">
            Корисни информации за да ги добиете тендерите
          </p>
        </div>
        <Card className="border-2 border-dashed">
          <CardContent className="py-12 flex flex-col items-center text-center space-y-4">
            <div className="p-4 bg-muted rounded-full">
              <Lock className="h-8 w-8 text-muted-foreground" />
            </div>
            <div>
              <h2 className="text-xl font-semibold">Премиум функција</h2>
              <p className="text-muted-foreground mt-1 max-w-md">
                Увидите и трендовите се достапни за корисници со Стартуј план или повисок.
                {!isLoggedIn && " Најавете се за да продолжите."}
              </p>
            </div>
            <div className="flex gap-3">
              {!isLoggedIn ? (
                <>
                  <Link href="/auth/login">
                    <Button>Најава</Button>
                  </Link>
                  <Link href="/auth/register">
                    <Button variant="outline">Регистрација</Button>
                  </Link>
                </>
              ) : (
                <Link href="/settings">
                  <Button>Надоградете план</Button>
                </Link>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

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
                onChange={(e) => {
                  setCpvFilter(e.target.value);
                  setShowCpvDropdown(true);
                }}
                onFocus={() => setShowCpvDropdown(true)}
                onBlur={() => setTimeout(() => setShowCpvDropdown(false), 200)}
                className="pl-9"
                onKeyDown={(e) => e.key === 'Enter' && handleApplyFilter()}
              />
              {cpvLoading && (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground absolute right-3 top-1/2 -translate-y-1/2" />
              )}

              {/* CPV Dropdown */}
              {showCpvDropdown && cpvOptions.length > 0 && (
                <div className="absolute z-50 w-full mt-1 max-h-48 overflow-auto border rounded-md bg-background shadow-lg">
                  {cpvOptions.map((opt) => (
                    <button
                      key={opt.code}
                      type="button"
                      className="w-full text-left text-sm hover:bg-accent px-3 py-2 border-b last:border-b-0"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        setCpvFilter(opt.code);
                        setAppliedCpv(opt.code);
                        setShowCpvDropdown(false);
                      }}
                    >
                      <span className="font-mono text-xs text-primary mr-2">{opt.code}</span>
                      <span className="text-muted-foreground">{opt.name_mk || opt.name}</span>
                    </button>
                  ))}
                </div>
              )}
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
        <TabsList className="grid w-full grid-cols-2 lg:grid-cols-4 h-auto gap-1">
          <TabsTrigger value="opportunities" className="flex items-center gap-1.5 py-2 px-2 text-xs sm:text-sm">
            <Clock className="h-4 w-4" />
            <span className="hidden sm:inline">Можности</span>
            <span className="sm:hidden">Итни</span>
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
