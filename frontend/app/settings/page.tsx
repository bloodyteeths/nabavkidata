"use client";

import { useState, useEffect } from "react";
import { api, UserPreferences } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { billing, BillingPlan } from "@/lib/billing";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { X, Check, Sparkles, CreditCard, Zap } from "lucide-react";

const AVAILABLE_SECTORS = ["ИТ", "Градежништво", "Консултинг", "Опрема"];

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
  const { user, isAuthenticated } = useAuth();
  const userId = user?.id;

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

  const loadPreferences = async () => {
    try {
      if (!userId) {
        setLoading(false);
        // router.push('/auth/login'); // Optional: redirect
        return;
      }
      setLoading(true);
      // TODO: Re-enable when personalization API is implemented
      // const prefs = await api.getPreferences(userId);
      // setPreferences(prefs);

      // Use default preferences for now
      setPreferences(DEFAULT_PREFERENCES);
    } catch (error) {
      console.error("Грешка при вчитување на преференци:", error);
    } finally {
      setLoading(false);
    }
  };

  const loadPlans = async () => {
    try {
      // Use hardcoded plans for now - no API call needed
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

      // Try to get current subscription status using billing service
      try {
        const status = await billing.getSubscriptionStatus();
        setCurrentTier(status.tier);
      } catch (err) {
        // User not logged in or no subscription - default to free
        console.log('No subscription found, defaulting to free tier');
        setCurrentTier('free');
      }
    } catch (error) {
      console.error("Failed to load plans:", error);
      // Still set free tier as fallback
      setCurrentTier('free');
    }
  };

  const handleUpgrade = async (tier: string) => {
    if (tier === 'free') return;

    try {
      setUpgrading(tier);
      const session = await api.createCheckoutSession(tier, interval);

      // Redirect to Stripe checkout
      window.location.href = session.checkout_url;
    } catch (error) {
      console.error("Failed to create checkout session:", error);
      alert("Грешка при креирање на сесија за плаќање. Ве молиме обидете се повторно.");
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
      alert("Грешка при отворање на порталот за наплата.");
    }
  };

  const handleSave = async () => {
    try {
      if (!userId) return;
      setSaving(true);
      await api.updatePreferences(userId, preferences);
      console.log("Преференциите се успешно зачувани");
    } catch (error) {
      console.error("Грешка при зачувување:", error);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setPreferences(DEFAULT_PREFERENCES);
    console.log("Преференциите се ресетирани на стандардни");
  };

  const toggleSector = (sector: string) => {
    setPreferences((prev) => ({ ...prev, sectors: prev.sectors.includes(sector) ? prev.sectors.filter((s) => s !== sector) : [...prev.sectors, sector] }));
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
        <p className="text-muted-foreground mt-2">Управувајте со вашите преференци и претплата</p>
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
                        {/* Daily Queries */}
                        <div className="flex items-center gap-2 text-sm">
                          <Zap className="h-4 w-4 text-primary" />
                          <span className="font-medium">
                            {plan.daily_queries === -1 ? 'Неограничени' : plan.daily_queries} AI пребарувања дневно
                          </span>
                        </div>

                        {/* Trial Info */}
                        {plan.trial_days > 0 && (
                          <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <Check className="h-4 w-4" />
                            <span>{plan.trial_days}-дневен пробен период</span>
                          </div>
                        )}

                        {/* Features */}
                        <div className="space-y-2 pt-2 border-t">
                          {plan.features.map((feature, idx) => (
                            <div key={idx} className="flex items-start gap-2 text-sm">
                              <Check className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                              <span className="text-muted-foreground">{feature}</span>
                            </div>
                          ))}
                        </div>

                        {/* CTA Button */}
                        <div className="pt-4">
                          {isCurrentPlan ? (
                            <Button
                              variant="outline"
                              className="w-full"
                              onClick={handleManageBilling}
                            >
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

            {/* Trial Warning for Free Users */}
            {currentTier === 'free' && (
              <div className="mt-6 p-4 rounded-lg bg-orange-500/10 border border-orange-500/20">
                <p className="text-sm text-orange-400">
                  <strong>Важно:</strong> Бесплатниот план е ограничен на 14 дена. По истекот на пробниот период, ќе треба да надоградите за да продолжите да ја користите платформата.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Сектори</CardTitle>
            <CardDescription>Изберете ги секторите што ве интересираат</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {AVAILABLE_SECTORS.map((sector) => (
                <Badge key={sector} variant={preferences.sectors.includes(sector) ? "default" : "outline"} className="cursor-pointer" onClick={() => toggleSector(sector)}>{sector}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>CPV Кодови</CardTitle>
            <CardDescription>Додадете CPV кодови за специфични категории</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input placeholder="Внесете CPV код" value={cpvInput} onChange={(e) => setCpvInput(e.target.value)} onKeyPress={(e) => e.key === "Enter" && addItem("cpv_codes", cpvInput, setCpvInput)} />
              <Button onClick={() => addItem("cpv_codes", cpvInput, setCpvInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.cpv_codes.map((code) => (
                <Badge key={code} variant="secondary" className="gap-1">{code}<X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("cpv_codes", code)} /></Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Ентитети</CardTitle>
            <CardDescription>Додадете набавувачки организации што ве интересираат</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input placeholder="Внесете име на ентитет" value={entityInput} onChange={(e) => setEntityInput(e.target.value)} onKeyPress={(e) => e.key === "Enter" && addItem("entities", entityInput, setEntityInput)} />
              <Button onClick={() => addItem("entities", entityInput, setEntityInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.entities.map((entity) => (
                <Badge key={entity} variant="secondary" className="gap-1">{entity}<X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("entities", entity)} /></Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Буџет</CardTitle>
            <CardDescription>Дефинирајте минимален и максимален буџет (МКД)</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Минимален буџет</label>
                <Input type="number" placeholder="0" value={preferences.min_budget || ""} onChange={(e) => setPreferences((prev) => ({ ...prev, min_budget: e.target.value ? Number(e.target.value) : undefined }))} />
              </div>
              <div>
                <label className="text-sm font-medium mb-2 block">Максимален буџет</label>
                <Input type="number" placeholder="∞" value={preferences.max_budget || ""} onChange={(e) => setPreferences((prev) => ({ ...prev, max_budget: e.target.value ? Number(e.target.value) : undefined }))} />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Исклучени клучни зборови</CardTitle>
            <CardDescription>Тендери што содржат овие зборови нема да се прикажуваат</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input placeholder="Внесете клучен збор" value={keywordInput} onChange={(e) => setKeywordInput(e.target.value)} onKeyPress={(e) => e.key === "Enter" && addItem("exclude_keywords", keywordInput, setKeywordInput)} />
              <Button onClick={() => addItem("exclude_keywords", keywordInput, setKeywordInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.exclude_keywords.map((keyword) => (
                <Badge key={keyword} variant="destructive" className="gap-1">{keyword}<X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("exclude_keywords", keyword)} /></Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Конкурентски компании</CardTitle>
            <CardDescription>Следете ги активностите на конкурентските компании</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-3">
              <Input placeholder="Внесете име на компанија" value={competitorInput} onChange={(e) => setCompetitorInput(e.target.value)} onKeyPress={(e) => e.key === "Enter" && addItem("competitor_companies", competitorInput, setCompetitorInput)} />
              <Button onClick={() => addItem("competitor_companies", competitorInput, setCompetitorInput)}>Додади</Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {preferences.competitor_companies.map((competitor) => (
                <Badge key={competitor} variant="warning" className="gap-1">{competitor}<X className="h-3 w-3 cursor-pointer" onClick={() => removeItem("competitor_companies", competitor)} /></Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Нотификации</CardTitle>
            <CardDescription>Конфигурирајте како сакате да примате нотификации</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-2 block">Фреквенција на нотификации</label>
                <Select value={preferences.notification_frequency} onValueChange={(value) => setPreferences((prev) => ({ ...prev, notification_frequency: value }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="instant">Моментално</SelectItem>
                    <SelectItem value="daily">Дневно</SelectItem>
                    <SelectItem value="weekly">Неделно</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="email-enabled" checked={preferences.email_enabled} onChange={(e) => setPreferences((prev) => ({ ...prev, email_enabled: e.target.checked }))} className="w-4 h-4 cursor-pointer" />
                <label htmlFor="email-enabled" className="text-sm font-medium cursor-pointer">Овозможи email нотификации</label>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={handleReset}>Ресетирај</Button>
          <Button onClick={handleSave} disabled={saving}>{saving ? "Се зачувува..." : "Зачувај"}</Button>
        </div>
      </div>
    </div>
  );
}
