"use client";

import { useState, useEffect, useCallback } from "react";
import { api, UserPreferences } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { billing, BillingPlan } from "@/lib/billing";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { X, Check, Sparkles, CreditCard, Zap, HelpCircle, Search, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

// Expanded sectors based on common procurement categories in Macedonia
const AVAILABLE_SECTORS = [
  { id: "it", label: "ИТ и Софтвер", description: "Информатичка технологија, софтвер, хардвер" },
  { id: "construction", label: "Градежништво", description: "Градежни работи, инфраструктура" },
  { id: "consulting", label: "Консултантски услуги", description: "Стручни консултации, анализи" },
  { id: "equipment", label: "Опрема и машини", description: "Канцелариска и индустриска опрема" },
  { id: "medical", label: "Медицина и здравство", description: "Медицинска опрема, лекови, услуги" },
  { id: "education", label: "Образование", description: "Образовни услуги и материјали" },
  { id: "transport", label: "Транспорт", description: "Возила, транспортни услуги" },
  { id: "food", label: "Храна и пијалоци", description: "Прехранбени производи" },
  { id: "cleaning", label: "Чистење и одржување", description: "Хигиенски услуги, одржување" },
  { id: "security", label: "Обезбедување", description: "Физичко и техничко обезбедување" },
  { id: "energy", label: "Енергетика", description: "Електрична енергија, гориво, греење" },
  { id: "printing", label: "Печатење", description: "Печатарски услуги, канцелариски материјал" },
];

// Common CPV codes with descriptions for guidance
const COMMON_CPV_CODES = [
  { code: "30200000", label: "Компјутерска опрема" },
  { code: "33100000", label: "Медицинска опрема" },
  { code: "45000000", label: "Градежни работи" },
  { code: "72000000", label: "ИТ услуги" },
  { code: "79000000", label: "Деловни услуги" },
  { code: "34000000", label: "Транспортна опрема" },
  { code: "15000000", label: "Храна и пијалоци" },
  { code: "39000000", label: "Мебел и опрема" },
  { code: "50000000", label: "Поправки и одржување" },
  { code: "60000000", label: "Транспортни услуги" },
  { code: "85000000", label: "Здравствени услуги" },
  { code: "90000000", label: "Чистење и отпад" },
];

// Budget presets in MKD
const BUDGET_PRESETS = [
  { label: "Мало (до 500K)", min: 0, max: 500000 },
  { label: "Средно (500K - 3M)", min: 500000, max: 3000000 },
  { label: "Големо (3M - 10M)", min: 3000000, max: 10000000 },
  { label: "Многу големо (над 10M)", min: 10000000, max: undefined },
];

const DEFAULT_PREFERENCES: UserPreferences = {
  sectors: [],
  cpv_codes: [],
  entities: [],
  min_budget: undefined,
  max_budget: undefined,
  exclude_keywords: [],
  competitor_companies: [],
  notification_frequency: "daily",
  email_enabled: true,
};

export default function SettingsPage() {
  const [preferences, setPreferences] = useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [cpvInput, setCpvInput] = useState("");
  const [entityInput, setEntityInput] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [competitorInput, setCompetitorInput] = useState("");
  const [plans, setPlans] = useState<BillingPlan[]>([]);
  const [currentTier, setCurrentTier] = useState<string>("free");
  const [interval, setInterval] = useState<'monthly' | 'yearly'>('monthly');
  const [upgrading, setUpgrading] = useState<string | null>(null);

  // Autocomplete suggestions
  const [entitySuggestions, setEntitySuggestions] = useState<string[]>([]);
  const [showEntitySuggestions, setShowEntitySuggestions] = useState(false);
  const [competitorSuggestions, setCompetitorSuggestions] = useState<string[]>([]);
  const [showCompetitorSuggestions, setShowCompetitorSuggestions] = useState(false);

  // Validation state
  const [budgetError, setBudgetError] = useState<string | null>(null);

  const { user } = useAuth();
  const userId = user?.user_id;

  useEffect(() => {
    const init = async () => {
      if (userId) {
        await loadPreferences();
      } else {
        setLoading(false);
      }
      await loadPlans();
    };
    init();
  }, [userId]);

  // Validate budget whenever it changes
  useEffect(() => {
    if (preferences.min_budget && preferences.max_budget) {
      if (preferences.min_budget > preferences.max_budget) {
        setBudgetError("Минималниот буџет не може да биде поголем од максималниот");
      } else {
        setBudgetError(null);
      }
    } else {
      setBudgetError(null);
    }
  }, [preferences.min_budget, preferences.max_budget]);

  const loadPreferences = async () => {
    try {
      if (!userId) {
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const prefs = await api.getPreferences(userId);
        setPreferences(prefs);
      } catch {
        console.log("No existing preferences, using defaults");
        setPreferences(DEFAULT_PREFERENCES);
      }
    } catch (error) {
      console.error("Грешка при вчитување на преференци:", error);
      setPreferences(DEFAULT_PREFERENCES);
    } finally {
      setLoading(false);
    }
  };

  const loadPlans = async () => {
    try {
      const hardcodedPlans: BillingPlan[] = [
        {
          tier: 'free',
          name: 'Free',
          price_monthly_eur: 0,
          price_yearly_eur: 0,
          price_monthly_id: '',
          price_yearly_id: '',
          daily_queries: 3,
          trial_days: 14,
          allow_vpn: false,
          features: ['3 AI queries per day', '14-day trial', 'Basic search', 'Email support']
        },
        {
          tier: 'starter',
          name: 'Starter',
          price_monthly_eur: 14.99,
          price_yearly_eur: 149.99,
          price_monthly_id: 'price_1SWeAsHkVI5icjTl9GZ8Ciui',
          price_yearly_id: 'price_1SWeAsHkVI5icjTlGRvOP17d',
          daily_queries: 5,
          trial_days: 14,
          allow_vpn: true,
          features: ['5 AI queries per day', '14-day trial', 'Advanced filters', 'CSV/PDF export', 'Priority support']
        },
        {
          tier: 'professional',
          name: 'Professional',
          price_monthly_eur: 39.99,
          price_yearly_eur: 399.99,
          price_monthly_id: 'price_1SWeAtHkVI5icjTl8UxSYNYX',
          price_yearly_id: 'price_1SWeAuHkVI5icjTlrbC5owFk',
          daily_queries: 20,
          trial_days: 14,
          allow_vpn: true,
          features: ['20 AI queries per day', '14-day trial', 'Analytics', 'Integrations', 'Dedicated support']
        },
        {
          tier: 'enterprise',
          name: 'Enterprise',
          price_monthly_eur: 99.99,
          price_yearly_eur: 999.99,
          price_monthly_id: 'price_1SWeAvHkVI5icjTlF8eFK8kh',
          price_yearly_id: 'price_1SWeAvHkVI5icjTlcKi7RFu7',
          daily_queries: -1,
          trial_days: 14,
          allow_vpn: true,
          features: ['Unlimited queries', '14-day trial', 'White-label', 'API access', '24/7 support']
        }
      ];
      setPlans(hardcodedPlans);

      try {
        const status = await billing.getSubscriptionStatus();
        setCurrentTier(status.tier);
      } catch {
        console.log('No subscription found, defaulting to free tier');
        setCurrentTier('free');
      }
    } catch (error) {
      console.error("Failed to load plans:", error);
      setCurrentTier('free');
    }
  };

  // Fetch entity suggestions (debounced)
  const fetchEntitySuggestions = useCallback(async (query: string) => {
    if (query.length < 2) {
      setEntitySuggestions([]);
      return;
    }
    try {
      // Search for entities in existing tenders
      const result = await api.searchTenders({
        query: query,
        page: 1,
        page_size: 20
      });
      // Extract unique procuring entities
      const entities = [...new Set(
        result.items
          .map(t => t.procuring_entity)
          .filter((e): e is string => !!e && e.toLowerCase().includes(query.toLowerCase()))
      )].slice(0, 8);
      setEntitySuggestions(entities);
    } catch {
      setEntitySuggestions([]);
    }
  }, []);

  // Fetch competitor suggestions (from e-Pazar suppliers)
  const fetchCompetitorSuggestions = useCallback(async (query: string) => {
    if (query.length < 2) {
      setCompetitorSuggestions([]);
      return;
    }
    try {
      const result = await api.getEPazarSuppliers({ search: query, page_size: 8 });
      const companies = result.items.map(s => s.company_name);
      setCompetitorSuggestions(companies);
    } catch {
      setCompetitorSuggestions([]);
    }
  }, []);

  const handleUpgrade = async (tier: string) => {
    if (tier === 'free') return;
    try {
      setUpgrading(tier);
      const session = await api.createCheckoutSession(tier, interval);
      window.location.href = session.checkout_url;
    } catch (error) {
      console.error("Failed to create checkout session:", error);
      toast.error("Грешка при креирање на сесија за плаќање. Ве молиме обидете се повторно.");
    } finally {
      setUpgrading(null);
    }
  };

  const handleManageBilling = async () => {
    try {
      const portal = await api.createPortalSession();
      window.location.href = portal.url;
    } catch (error) {
      console.error("Failed to open billing portal:", error);
      toast.error("Грешка при отворање на порталот за наплата.");
    }
  };

  const handleSave = async () => {
    // Validate before saving
    if (budgetError) {
      toast.error(budgetError);
      return;
    }

    try {
      if (!userId) return;
      setSaving(true);
      await api.savePreferences(userId, preferences);
      toast.success("Преференциите се успешно зачувани! Вашата персонализирана табла ќе се ажурира.");
    } catch (error) {
      console.error("Грешка при зачувување:", error);
      toast.error("Грешка при зачувување на преференците. Проверете ја интернет конекцијата.");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (window.confirm("Дали сте сигурни дека сакате да ги ресетирате сите преференци?")) {
      setPreferences(DEFAULT_PREFERENCES);
      toast.success("Преференциите се ресетирани на стандардни");
    }
  };

  const toggleSector = (sectorId: string) => {
    setPreferences((prev) => ({
      ...prev,
      sectors: prev.sectors.includes(sectorId)
        ? prev.sectors.filter((s) => s !== sectorId)
        : [...prev.sectors, sectorId]
    }));
  };

  const addCpvCode = (code: string) => {
    const cleanCode = code.trim().replace(/\D/g, ''); // Only digits
    if (cleanCode && cleanCode.length >= 2 && !preferences.cpv_codes.includes(cleanCode)) {
      setPreferences((prev) => ({ ...prev, cpv_codes: [...prev.cpv_codes, cleanCode] }));
      setCpvInput("");
    } else if (cleanCode.length < 2) {
      toast.error("CPV кодот мора да има најмалку 2 цифри");
    }
  };

  const addItem = (field: keyof UserPreferences, value: string, setter: (v: string) => void) => {
    if (value.trim() && !(preferences[field] as string[]).includes(value.trim())) {
      setPreferences((prev) => ({ ...prev, [field]: [...(prev[field] as string[]), value.trim()] }));
      setter("");
    }
  };

  const removeItem = (field: keyof UserPreferences, value: string) => {
    setPreferences((prev) => ({ ...prev, [field]: (prev[field] as string[]).filter((i) => i !== value) }));
  };

  const applyBudgetPreset = (preset: typeof BUDGET_PRESETS[0]) => {
    setPreferences((prev) => ({
      ...prev,
      min_budget: preset.min || undefined,
      max_budget: preset.max || undefined
    }));
  };

  const formatNumber = (num: number) => {
    return new Intl.NumberFormat('mk-MK').format(num);
  };

  if (loading) {
    return (
      <div className="container mx-auto py-8">
        <div className="text-center">Се вчитува...</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Поставки</h1>
        <p className="text-muted-foreground mt-2">
          Конфигурирајте ги вашите преференци за да добивате персонализирани препораки за тендери
        </p>
      </div>

      <div className="space-y-6">
        {/* Subscription Plans */}
        <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Претплата и цени
            </CardTitle>
            <CardDescription>Одберете го планот што најдобро одговара на вашите потреби</CardDescription>
          </CardHeader>
          <CardContent>
            {/* Monthly/Yearly Toggle */}
            <div className="flex justify-center mb-6">
              <div className="inline-flex rounded-lg border border-primary/20 p-1 bg-background/50">
                <button
                  onClick={() => setInterval('monthly')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${interval === 'monthly'
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                  Месечно
                </button>
                <button
                  onClick={() => setInterval('yearly')}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${interval === 'yearly'
                    ? 'bg-primary text-primary-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                    }`}
                >
                  Годишно
                  <Badge variant="secondary" className="ml-2 bg-green-500/10 text-green-400 border-green-500/20">
                    Заштеди 17%
                  </Badge>
                </button>
              </div>
            </div>

            {/* Plans Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {plans.map((plan) => {
                const isCurrentPlan = plan.tier === currentTier;
                const price = interval === 'monthly' ? plan.price_monthly_eur : plan.price_yearly_eur;
                const isFree = plan.tier === 'free';
                const isPopular = plan.tier === 'professional';

                return (
                  <div key={plan.tier} className="relative">
                    {isPopular && (
                      <div className="absolute -top-4 left-0 right-0 flex justify-center">
                        <Badge className="bg-primary text-primary-foreground">
                          Најпопуларно
                        </Badge>
                      </div>
                    )}
                    <Card className={`h-full ${isCurrentPlan ? 'border-primary shadow-lg shadow-primary/20' : ''} ${isPopular ? 'border-primary/50' : ''}`}>
                      <CardHeader>
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-xl">{plan.name}</CardTitle>
                          {isCurrentPlan && (
                            <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
                              Тековен
                            </Badge>
                          )}
                        </div>
                        <div className="mt-4">
                          <div className="flex items-baseline gap-1">
                            <span className="text-4xl font-bold">€{price.toFixed(2)}</span>
                            <span className="text-muted-foreground">
                              {isFree ? '/засекогаш' : `/${interval === 'monthly' ? 'мес' : 'год'}`}
                            </span>
                          </div>
                          {!isFree && interval === 'yearly' && (
                            <p className="text-sm text-muted-foreground mt-1">
                              €{(price / 12).toFixed(2)} месечно
                            </p>
                          )}
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="flex items-center gap-2 text-sm">
                          <Zap className="h-4 w-4 text-primary" />
                          <span className="font-medium">
                            {plan.daily_queries === -1 ? 'Неограничени' : plan.daily_queries} AI пребарувања дневно
                          </span>
                        </div>
                        {plan.trial_days > 0 && (
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Check className="h-4 w-4" />
                            <span>{plan.trial_days}-дневен пробен период</span>
                          </div>
                        )}
                        <div className="space-y-2 pt-2 border-t">
                          {plan.features.map((feature, idx) => (
                            <div key={idx} className="flex items-start gap-2 text-sm">
                              <Check className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                              <span className="text-muted-foreground">{feature}</span>
                            </div>
                          ))}
                        </div>
                        <div className="pt-4">
                          {isCurrentPlan ? (
                            <Button variant="outline" className="w-full" onClick={handleManageBilling}>
                              <CreditCard className="mr-2 h-4 w-4" />
                              Управувај претплата
                            </Button>
                          ) : isFree ? (
                            <Button variant="outline" className="w-full" disabled>
                              Тековен план
                            </Button>
                          ) : (
                            <Button
                              className={`w-full ${isPopular ? 'bg-primary hover:bg-primary/90' : ''}`}
                              onClick={() => handleUpgrade(plan.tier)}
                              disabled={upgrading === plan.tier}
                            >
                              {upgrading === plan.tier ? 'Се обработува...' : 'Надогради'}
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  </div>
                );
              })}
            </div>

            {currentTier === 'free' && (
              <div className="mt-6 p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
                <p className="text-sm text-orange-400">
                  <strong>Важно:</strong> Бесплатниот план е ограничен на 14 дена. По истекот на пробниот период, ќе треба да надоградите за да продолжите да ја користите платформата.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sectors - Improved with descriptions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Сектори на интерес
              <span className="text-xs font-normal text-muted-foreground bg-primary/10 px-2 py-1 rounded">
                {preferences.sectors.length} избрани
              </span>
            </CardTitle>
            <CardDescription>
              Одберете ги секторите за кои сакате да добивате препораки. Можете да изберете повеќе сектори.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {AVAILABLE_SECTORS.map((sector) => (
                <div
                  key={sector.id}
                  onClick={() => toggleSector(sector.id)}
                  className={`cursor-pointer p-3 rounded-lg border transition-all ${
                    preferences.sectors.includes(sector.id)
                      ? 'border-primary bg-primary/10 shadow-sm'
                      : 'border-border hover:border-primary/50 hover:bg-accent/50'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{sector.label}</span>
                    {preferences.sectors.includes(sector.id) && (
                      <Check className="h-4 w-4 text-primary" />
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{sector.description}</p>
                </div>
              ))}
            </div>
            {preferences.sectors.length === 0 && (
              <p className="text-sm text-muted-foreground mt-3 flex items-center gap-2">
                <HelpCircle className="h-4 w-4" />
                Изберете барем еден сектор за подобри препораки
              </p>
            )}
          </CardContent>
        </Card>

        {/* CPV Codes - Improved with suggestions */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              CPV Кодови
              <span className="text-xs font-normal text-muted-foreground bg-primary/10 px-2 py-1 rounded">
                {preferences.cpv_codes.length} додадени
              </span>
            </CardTitle>
            <CardDescription>
              CPV (Common Procurement Vocabulary) кодовите се стандардизирани кодови за категоризација на набавки.
              Додадете кодови за попрецизни препораки.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {/* Quick add common CPV codes */}
            <div className="mb-4">
              <p className="text-sm font-medium mb-2">Брзо додавање (кликнете за да додадете):</p>
              <div className="flex flex-wrap gap-2">
                {COMMON_CPV_CODES.filter(c => !preferences.cpv_codes.includes(c.code)).slice(0, 6).map((cpv) => (
                  <Badge
                    key={cpv.code}
                    variant="outline"
                    className="cursor-pointer hover:bg-primary/10 hover:border-primary transition-colors"
                    onClick={() => addCpvCode(cpv.code)}
                  >
                    {cpv.code} - {cpv.label}
                  </Badge>
                ))}
              </div>
            </div>

            <div className="flex gap-2 mb-3">
              <div className="flex-1 relative">
                <Input
                  placeholder="Внесете CPV код (пр. 30200000)"
                  value={cpvInput}
                  onChange={(e) => setCpvInput(e.target.value.replace(/\D/g, ''))}
                  onKeyPress={(e) => e.key === "Enter" && addCpvCode(cpvInput)}
                  maxLength={8}
                />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                  {cpvInput.length}/8 цифри
                </span>
              </div>
              <Button onClick={() => addCpvCode(cpvInput)} disabled={cpvInput.length < 2}>Додади</Button>
            </div>

            <div className="flex flex-wrap gap-2">
              {preferences.cpv_codes.length === 0 ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <HelpCircle className="h-4 w-4" />
                  Нема додадени CPV кодови. Користете ги предлозите погоре или внесете свој код.
                </p>
              ) : (
                preferences.cpv_codes.map((code) => {
                  const cpvInfo = COMMON_CPV_CODES.find(c => code.startsWith(c.code.slice(0, 2)));
                  return (
                    <Badge key={code} variant="secondary" className="gap-1 py-1.5">
                      {code}
                      {cpvInfo && <span className="text-xs opacity-70">({cpvInfo.label})</span>}
                      <X className="h-3 w-3 cursor-pointer hover:text-destructive" onClick={() => removeItem("cpv_codes", code)} />
                    </Badge>
                  );
                })
              )}
            </div>
          </CardContent>
        </Card>

        {/* Entities - With autocomplete */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Набавувачки организации
              <span className="text-xs font-normal text-muted-foreground bg-primary/10 px-2 py-1 rounded">
                {preferences.entities.length} следени
              </span>
            </CardTitle>
            <CardDescription>
              Додадете имиња на институции/организации чии тендери сакате да ги следите (министерства, општини, јавни претпријатија и сл.)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3 relative">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Пребарај организации (пр. Министерство за здравство)"
                  value={entityInput}
                  onChange={(e) => {
                    setEntityInput(e.target.value);
                    fetchEntitySuggestions(e.target.value);
                    setShowEntitySuggestions(true);
                  }}
                  onFocus={() => setShowEntitySuggestions(true)}
                  onBlur={() => setTimeout(() => setShowEntitySuggestions(false), 200)}
                  onKeyPress={(e) => e.key === "Enter" && addItem("entities", entityInput, setEntityInput)}
                  className="pl-10"
                />
                {/* Autocomplete dropdown */}
                {showEntitySuggestions && entitySuggestions.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-md shadow-lg z-50 max-h-48 overflow-auto">
                    {entitySuggestions.map((entity, idx) => (
                      <div
                        key={idx}
                        className="px-3 py-2 hover:bg-accent cursor-pointer text-sm"
                        onClick={() => {
                          addItem("entities", entity, setEntityInput);
                          setShowEntitySuggestions(false);
                        }}
                      >
                        {entity}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <Button onClick={() => addItem("entities", entityInput, setEntityInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.entities.length === 0 ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <HelpCircle className="h-4 w-4" />
                  Почнете да пишувате за да добиете предлози од базата на тендери
                </p>
              ) : (
                preferences.entities.map((entity) => (
                  <Badge key={entity} variant="secondary" className="gap-1">
                    {entity}
                    <X className="h-3 w-3 cursor-pointer hover:text-destructive" onClick={() => removeItem("entities", entity)} />
                  </Badge>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Budget - With presets and validation */}
        <Card>
          <CardHeader>
            <CardTitle>Буџетски опсег</CardTitle>
            <CardDescription>Дефинирајте минимален и максимален буџет за тендерите што ве интересираат (во МКД)</CardDescription>
          </CardHeader>
          <CardContent>
            {/* Budget presets */}
            <div className="mb-4">
              <p className="text-sm font-medium mb-2">Брзи опции:</p>
              <div className="flex flex-wrap gap-2">
                {BUDGET_PRESETS.map((preset, idx) => (
                  <Button
                    key={idx}
                    variant="outline"
                    size="sm"
                    onClick={() => applyBudgetPreset(preset)}
                    className="text-xs"
                  >
                    {preset.label}
                  </Button>
                ))}
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPreferences(prev => ({ ...prev, min_budget: undefined, max_budget: undefined }))}
                  className="text-xs"
                >
                  Без ограничување
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Минимален буџет (МКД)</label>
                <Input
                  type="text"
                  placeholder="0"
                  value={preferences.min_budget ? formatNumber(preferences.min_budget) : ""}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '');
                    setPreferences((prev) => ({ ...prev, min_budget: value ? Number(value) : undefined }));
                  }}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Максимален буџет (МКД)</label>
                <Input
                  type="text"
                  placeholder="Без лимит"
                  value={preferences.max_budget ? formatNumber(preferences.max_budget) : ""}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '');
                    setPreferences((prev) => ({ ...prev, max_budget: value ? Number(value) : undefined }));
                  }}
                />
              </div>
            </div>

            {budgetError && (
              <div className="mt-3 flex items-center gap-2 text-destructive text-sm">
                <AlertTriangle className="h-4 w-4" />
                {budgetError}
              </div>
            )}

            {(preferences.min_budget || preferences.max_budget) && !budgetError && (
              <p className="text-sm text-muted-foreground mt-3">
                Ќе прикажуваме тендери со вредност: {preferences.min_budget ? formatNumber(preferences.min_budget) + ' МКД' : '0 МКД'}
                {' - '}
                {preferences.max_budget ? formatNumber(preferences.max_budget) + ' МКД' : 'без лимит'}
              </p>
            )}
          </CardContent>
        </Card>

        {/* Exclude Keywords */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Исклучени клучни зборови
              <span className="text-xs font-normal text-destructive/70 bg-destructive/10 px-2 py-1 rounded">
                {preferences.exclude_keywords.length} исклучени
              </span>
            </CardTitle>
            <CardDescription>
              Тендери што содржат овие зборови во насловот нема да се прикажуваат во вашите препораки
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input
                placeholder="Внесете збор за исклучување (пр. санација, ремонт)"
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && addItem("exclude_keywords", keywordInput, setKeywordInput)}
              />
              <Button variant="destructive" onClick={() => addItem("exclude_keywords", keywordInput, setKeywordInput)}>
                Исклучи
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.exclude_keywords.length === 0 ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <HelpCircle className="h-4 w-4" />
                  Нема исклучени зборови. Додадете зборови за да ги филтрирате нерелевантните тендери.
                </p>
              ) : (
                preferences.exclude_keywords.map((keyword) => (
                  <Badge key={keyword} variant="destructive" className="gap-1">
                    {keyword}
                    <X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("exclude_keywords", keyword)} />
                  </Badge>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Competitor Companies - With autocomplete */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              Конкурентски компании
              <span className="text-xs font-normal text-orange-400 bg-orange-500/10 px-2 py-1 rounded">
                {preferences.competitor_companies.length} следени
              </span>
            </CardTitle>
            <CardDescription>
              Следете ги активностите на конкурентските компании - ќе добиете известувања кога тие добиваат тендери
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3 relative">
              <div className="flex-1 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Пребарај компании (пр. Неоком, Сеавус)"
                  value={competitorInput}
                  onChange={(e) => {
                    setCompetitorInput(e.target.value);
                    fetchCompetitorSuggestions(e.target.value);
                    setShowCompetitorSuggestions(true);
                  }}
                  onFocus={() => setShowCompetitorSuggestions(true)}
                  onBlur={() => setTimeout(() => setShowCompetitorSuggestions(false), 200)}
                  onKeyPress={(e) => e.key === "Enter" && addItem("competitor_companies", competitorInput, setCompetitorInput)}
                  className="pl-10"
                />
                {/* Autocomplete dropdown */}
                {showCompetitorSuggestions && competitorSuggestions.length > 0 && (
                  <div className="absolute top-full left-0 right-0 mt-1 bg-background border rounded-md shadow-lg z-50 max-h-48 overflow-auto">
                    {competitorSuggestions.map((company, idx) => (
                      <div
                        key={idx}
                        className="px-3 py-2 hover:bg-accent cursor-pointer text-sm"
                        onClick={() => {
                          addItem("competitor_companies", company, setCompetitorInput);
                          setShowCompetitorSuggestions(false);
                        }}
                      >
                        {company}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <Button onClick={() => addItem("competitor_companies", competitorInput, setCompetitorInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.competitor_companies.length === 0 ? (
                <p className="text-sm text-muted-foreground flex items-center gap-2">
                  <HelpCircle className="h-4 w-4" />
                  Почнете да пишувате за да пребарате добавувачи од е-Пазар базата
                </p>
              ) : (
                preferences.competitor_companies.map((competitor) => (
                  <Badge key={competitor} className="gap-1 bg-orange-500/10 text-orange-400 border-orange-500/20">
                    {competitor}
                    <X className="h-3 w-3 cursor-pointer hover:text-destructive" onClick={() => removeItem("competitor_companies", competitor)} />
                  </Badge>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Notifications */}
        <Card>
          <CardHeader>
            <CardTitle>Нотификации</CardTitle>
            <CardDescription>Конфигурирајте како сакате да примате известувања за нови тендери и активности</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Фреквенција на email известувања</label>
                <Select value={preferences.notification_frequency} onValueChange={(value) => setPreferences((prev) => ({ ...prev, notification_frequency: value }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="instant">Моментално (веднаш по објава)</SelectItem>
                    <SelectItem value="daily">Дневен извештај (секое утро)</SelectItem>
                    <SelectItem value="weekly">Неделен извештај (секој понеделник)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-accent/50">
                <input
                  type="checkbox"
                  id="email-enabled"
                  checked={preferences.email_enabled}
                  onChange={(e) => setPreferences((prev) => ({ ...prev, email_enabled: e.target.checked }))}
                  className="w-5 h-5 cursor-pointer rounded border-primary"
                />
                <div>
                  <label htmlFor="email-enabled" className="text-sm font-medium cursor-pointer block">
                    Овозможи email нотификации
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Примајте известувања за нови тендери и конкурентски активности на вашиот email
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Save/Reset Buttons */}
        <div className="flex gap-3 justify-end sticky bottom-4 bg-background/80 backdrop-blur-sm p-4 rounded-lg border">
          <Button variant="outline" onClick={handleReset}>Ресетирај се</Button>
          <Button
            onClick={handleSave}
            disabled={saving || !!budgetError}
            className="min-w-32"
          >
            {saving ? "Се зачувува..." : "Зачувај преференци"}
          </Button>
        </div>
      </div>
    </div>
  );
}
