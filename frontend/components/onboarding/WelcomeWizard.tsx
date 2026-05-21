"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api, type Tender } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  Search,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Building2,
  Loader2,
  X,
  Check,
  MapPin,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const SECTORS = [
  { name: "ИТ и дигитални услуги", query: "ИТ услуги информатичка технологија софтвер" },
  { name: "Градежништво", query: "градежни работи градба реконструкција" },
  { name: "Медицинска опрема", query: "медицинска опрема здравство лекови" },
  { name: "Канцелариски материјали", query: "канцелариски материјали тонери" },
  { name: "Храна и пијалоци", query: "храна пијалоци прехранбени" },
  { name: "Транспорт и возила", query: "транспорт возила превоз" },
  { name: "Чистење и одржување", query: "чистење хигиена одржување" },
  { name: "Обезбедување", query: "обезбедување безбедност заштита" },
  { name: "Консултантски услуги", query: "консултантски услуги ревизија" },
  { name: "Опрема и машини", query: "опрема машини апарати" },
  { name: "Енергетика", query: "електрична енергија гориво греење" },
  { name: "Печатење и маркетинг", query: "печатење рекламен материјал" },
];

const REGIONS = [
  "Скопје",
  "Битола",
  "Куманово",
  "Прилеп",
  "Тетово",
  "Охрид",
  "Велес",
  "Штип",
  "Струмица",
  "Гостивар",
  "Кавадарци",
  "Национално",
];

const BUDGET_OPTIONS = [
  { value: "under_500k", label: "Под 500.000 МКД", description: "Мали набавки, локални услуги" },
  { value: "500k_2m", label: "500.000 - 2.000.000 МКД", description: "Средни набавки" },
  { value: "2m_10m", label: "2.000.000 - 10.000.000 МКД", description: "Големи набавки" },
  { value: "10m_50m", label: "10.000.000 - 50.000.000 МКД", description: "Капитални набавки" },
  { value: "over_50m", label: "Над 50.000.000 МКД", description: "Големи проекти, рамковни договори" },
];

const BUDGET_MAP: Record<string, { min?: number; max?: number }> = {
  under_500k: { max: 500000 },
  "500k_2m": { min: 500000, max: 2000000 },
  "2m_10m": { min: 2000000, max: 10000000 },
  "10m_50m": { min: 10000000, max: 50000000 },
  over_50m: { min: 50000000 },
};

interface WelcomeWizardProps {
  onComplete: () => void;
}

export function WelcomeWizard({ onComplete }: WelcomeWizardProps) {
  const router = useRouter();
  const { user } = useAuth();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);

  // Step 1: Sector
  const [sectorQuery, setSectorQuery] = useState("");
  const [selectedSector, setSelectedSector] = useState<typeof SECTORS[0] | null>(null);
  const [filteredSectors, setFilteredSectors] = useState(SECTORS);

  // Step 2: Region
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);

  // Step 3: Budget
  const [selectedBudget, setSelectedBudget] = useState<string | null>(null);

  useEffect(() => {
    if (!sectorQuery.trim()) {
      setFilteredSectors(SECTORS);
      return;
    }
    const q = sectorQuery.toLowerCase();
    setFilteredSectors(
      SECTORS.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.query.toLowerCase().includes(q)
      )
    );
  }, [sectorQuery]);

  const handleComplete = async () => {
    if (!selectedSector) return;
    setLoading(true);

    try {
      const budgetRange = selectedBudget ? BUDGET_MAP[selectedBudget] : {};

      if (user?.user_id) {
        await api.savePreferences(user.user_id, {
          sectors: [selectedSector.name],
          notification_frequency: "daily",
          email_enabled: true,
          min_budget: budgetRange.min,
          max_budget: budgetRange.max,
        });
      }

      // Auto-create alert
      api.createAlert({
        name: `${selectedSector.name} - автоматски алерт`,
        alert_type: "keyword",
        criteria: { keywords: selectedSector.query.split(" ").slice(0, 3) },
        notification_channels: ["email", "in_app"],
      }).catch(() => {});

      localStorage.setItem("wizard_completed", "true");
      localStorage.setItem("onboarding_completed", "true");
      api.completeOnboarding().catch(() => {});
      onComplete();
      router.push(`/tenders?search=${encodeURIComponent(selectedSector.query.split(" ")[0])}`);
    } catch {
      localStorage.setItem("wizard_completed", "true");
      onComplete();
    } finally {
      setLoading(false);
    }
  };

  const canProceed = () => {
    if (step === 1) return !!selectedSector;
    if (step === 2) return !!selectedRegion;
    if (step === 3) return !!selectedBudget;
    return false;
  };

  return (
    <div className="fixed inset-0 z-50 bg-background/98 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-lg my-4">
        {/* Skip */}
        <div className="flex justify-end mb-2">
          <button
            onClick={() => {
              localStorage.setItem("wizard_completed", "true");
              onComplete();
            }}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
          >
            Прескокни <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Progress Dots */}
        <div className="flex items-center justify-center gap-2 mb-6">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={`h-2.5 rounded-full transition-all duration-300 ${
                s === step
                  ? "w-8 bg-primary"
                  : s < step
                  ? "w-2.5 bg-primary/60"
                  : "w-2.5 bg-muted-foreground/20"
              }`}
            />
          ))}
        </div>

        <div className="bg-card border rounded-2xl shadow-2xl overflow-hidden">
          {/* Step 1: What does your company do? */}
          {step === 1 && (
            <div className="p-6 md:p-8">
              <h2 className="text-xl md:text-2xl font-bold text-foreground text-center mb-2">
                Со што се занимава вашата фирма?
              </h2>
              <p className="text-sm text-muted-foreground text-center mb-6">
                Ќе ги прилагодиме тендерите според вашата дејност
              </p>

              {/* Selected sector chip */}
              {selectedSector && (
                <div className="flex items-center justify-center mb-4">
                  <Badge
                    variant="secondary"
                    className="gap-2 py-2 px-4 text-sm bg-primary/10 border-primary/20"
                  >
                    <Check className="h-3.5 w-3.5 text-primary" />
                    {selectedSector.name}
                    <button
                      onClick={() => {
                        setSelectedSector(null);
                        setSectorQuery("");
                      }}
                      className="ml-1 p-0.5 rounded hover:bg-destructive/20 transition-colors"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                </div>
              )}

              {/* Search + sector list */}
              {!selectedSector && (
                <>
                  <div className="relative mb-4">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="пр. чистење, ИТ услуги, градежништво..."
                      value={sectorQuery}
                      onChange={(e) => setSectorQuery(e.target.value)}
                      className="pl-10 h-12 text-base"
                      autoFocus
                    />
                  </div>

                  <div className="space-y-2 max-h-[280px] overflow-y-auto">
                    {filteredSectors.map((sector) => (
                      <button
                        key={sector.name}
                        onClick={() => {
                          setSelectedSector(sector);
                          setSectorQuery("");
                        }}
                        className="w-full text-left p-3 rounded-xl border border-border hover:border-primary/40 hover:bg-primary/5 transition-all"
                      >
                        <h4 className="text-sm font-medium text-foreground">
                          {sector.name}
                        </h4>
                      </button>
                    ))}
                    {filteredSectors.length === 0 && sectorQuery.trim() && (
                      <button
                        onClick={() => {
                          setSelectedSector({ name: sectorQuery.trim(), query: sectorQuery.trim() });
                          setSectorQuery("");
                        }}
                        className="w-full text-left p-3 rounded-xl border border-dashed border-primary/40 bg-primary/5 transition-all"
                      >
                        <h4 className="text-sm font-medium text-primary">
                          Користи: &quot;{sectorQuery.trim()}&quot;
                        </h4>
                      </button>
                    )}
                  </div>
                </>
              )}

              <Button
                onClick={() => setStep(2)}
                disabled={!canProceed()}
                className="w-full mt-6 h-12 text-base"
              >
                Продолжи
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          )}

          {/* Step 2: Where are you based? */}
          {step === 2 && (
            <div className="p-6 md:p-8">
              <h2 className="text-xl md:text-2xl font-bold text-foreground text-center mb-2">
                Каде се наоѓате?
              </h2>
              <p className="text-sm text-muted-foreground text-center mb-6">
                Ќе ви прикажеме тендери од вашиот регион
              </p>

              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {REGIONS.map((region) => {
                  const isSelected = selectedRegion === region;
                  return (
                    <button
                      key={region}
                      onClick={() => setSelectedRegion(isSelected ? null : region)}
                      className={`p-3 rounded-xl border text-sm font-medium transition-all text-center ${
                        isSelected
                          ? "bg-primary text-primary-foreground border-primary shadow-lg"
                          : "bg-background hover:bg-foreground/5 border-border hover:border-primary/40 text-foreground"
                      }`}
                    >
                      {region === "Национално" ? (
                        region
                      ) : (
                        <span className="flex items-center justify-center gap-1">
                          <MapPin className="h-3 w-3" />
                          {region}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="flex gap-3 mt-6">
                <Button variant="outline" onClick={() => setStep(1)} className="h-12">
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <Button
                  onClick={() => setStep(3)}
                  disabled={!canProceed()}
                  className="flex-1 h-12 text-base"
                >
                  Продолжи
                  <ArrowRight className="ml-2 h-4 w-4" />
                </Button>
              </div>
            </div>
          )}

          {/* Step 3: What's your typical contract size? */}
          {step === 3 && (
            <div className="p-6 md:p-8">
              <h2 className="text-xl md:text-2xl font-bold text-foreground text-center mb-2">
                Колкав е вашиот типичен буџет?
              </h2>
              <p className="text-sm text-muted-foreground text-center mb-6">
                Ќе ви покажеме тендери во вашиот ценовен ранг
              </p>

              <div className="space-y-2">
                {BUDGET_OPTIONS.map((option) => {
                  const isSelected = selectedBudget === option.value;
                  return (
                    <button
                      key={option.value}
                      onClick={() => setSelectedBudget(isSelected ? null : option.value)}
                      className={`w-full p-4 rounded-xl border text-left transition-all ${
                        isSelected
                          ? "bg-primary text-primary-foreground border-primary shadow-lg"
                          : "bg-background hover:bg-foreground/5 border-border hover:border-primary/40"
                      }`}
                    >
                      <div className="text-base font-semibold">{option.label}</div>
                      <div
                        className={`text-xs mt-0.5 ${
                          isSelected ? "text-primary-foreground/80" : "text-muted-foreground"
                        }`}
                      >
                        {option.description}
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="flex gap-3 mt-6">
                <Button variant="outline" onClick={() => setStep(2)} className="h-12">
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <Button
                  onClick={handleComplete}
                  disabled={!canProceed() || loading}
                  className="flex-1 h-12 text-base"
                >
                  {loading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Се подготвува...
                    </>
                  ) : (
                    <>
                      Започни
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
