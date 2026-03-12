"use client";

import { useState, useEffect } from "react";
import { api, type Tender } from "@/lib/api";
import { formatCurrency, tenderUrl } from "@/lib/utils";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  Search,
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Sparkles,
  Package,
  Building2,
  Stethoscope,
  Wrench,
  UtensilsCrossed,
  Truck,
  Loader2,
  Bell,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Link from "next/link";

const CATEGORIES = [
  { label: "Канцелариски материјали", icon: Package, query: "канцелариски материјали" },
  { label: "Медицинска опрема", icon: Stethoscope, query: "медицинска опрема" },
  { label: "ИТ услуги", icon: Search, query: "ИТ услуги" },
  { label: "Градежни работи", icon: Wrench, query: "градежни работи" },
  { label: "Храна и пијалоци", icon: UtensilsCrossed, query: "храна и пијалоци" },
  { label: "Транспорт", icon: Truck, query: "транспорт" },
];

interface WelcomeWizardProps {
  onComplete: () => void;
}

export function WelcomeWizard({ onComplete }: WelcomeWizardProps) {
  const [step, setStep] = useState(1);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [customQuery, setCustomQuery] = useState("");
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [totalTenders, setTotalTenders] = useState(0);
  const [loading, setLoading] = useState(false);
  const [alertCreated, setAlertCreated] = useState(false);
  const [searchError, setSearchError] = useState(false);
  const { user } = useAuth();
  const router = useRouter();

  const searchQuery = customQuery.trim() || selectedCategory;

  async function handleContinueToStep2() {
    if (!searchQuery) return;
    setStep(2);
    setLoading(true);
    setSearchError(false);

    try {
      // Fetch matching tenders
      const result = await api.getTenders({
        search: searchQuery,
        limit: 5,
      });
      setTenders(result.items || []);
      setTotalTenders(result.total || 0);

      // Save preferences in background
      if (user?.user_id) {
        api.savePreferences(user.user_id, {
          sectors: [searchQuery],
          notification_frequency: "daily",
          email_enabled: true,
        }).catch(() => {}); // Don't block on failure
      }

      // Auto-create alert in background
      api.createAlert({
        name: `${searchQuery} - автоматски алерт`,
        alert_type: "keyword",
        criteria: { keywords: [searchQuery] },
        notification_channels: ["email", "in_app"],
      }).then(() => setAlertCreated(true)).catch(() => {});

    } catch (err) {
      console.error("Failed to load preview tenders:", err);
      setSearchError(true);
    } finally {
      setLoading(false);
    }
  }

  function handleComplete() {
    localStorage.setItem("wizard_completed", "true");
    onComplete();
    router.push(`/tenders?search=${encodeURIComponent(searchQuery)}`);
  }

  function handleSkip() {
    localStorage.setItem("wizard_completed", "true");
    onComplete();
  }

  return (
    <div className="fixed inset-0 z-50 bg-background/95 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        {/* Skip button */}
        <div className="flex justify-end mb-2">
          <button
            onClick={handleSkip}
            className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
          >
            Прескокни <X className="h-3 w-3" />
          </button>
        </div>

        <div className="bg-card border rounded-2xl shadow-2xl overflow-hidden">
          {/* Progress bar */}
          <div className="h-1 bg-muted">
            <div
              className="h-full bg-primary transition-all duration-500"
              style={{ width: step === 1 ? "50%" : "100%" }}
            />
          </div>

          {step === 1 ? (
            /* ========== STEP 1: Category Selection ========== */
            <div className="p-6 md:p-8">
              <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-12 h-12 bg-primary/10 rounded-full mb-3">
                  <Sparkles className="h-6 w-6 text-primary" />
                </div>
                <h2 className="text-xl md:text-2xl font-bold text-foreground">
                  Добредојдовте во NabavkiData!
                </h2>
                <p className="text-sm text-muted-foreground mt-2">
                  Кажете ни што продавате и ќе ви покажеме тендери за вас
                </p>
              </div>

              {/* Category chips */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mb-4">
                {CATEGORIES.map((cat) => {
                  const Icon = cat.icon;
                  const isSelected = selectedCategory === cat.query;
                  return (
                    <button
                      key={cat.query}
                      onClick={() => {
                        setSelectedCategory(isSelected ? "" : cat.query);
                        setCustomQuery("");
                      }}
                      className={`flex items-center gap-2 p-3 rounded-xl border text-sm font-medium transition-all ${
                        isSelected
                          ? "bg-primary text-white border-primary shadow-lg"
                          : "bg-background hover:bg-foreground/5 border-border hover:border-primary/40 text-foreground"
                      }`}
                    >
                      <Icon className="h-4 w-4 flex-shrink-0" />
                      <span className="text-left text-xs">{cat.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* Or type custom */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Или напишете што продавате..."
                  value={customQuery}
                  onChange={(e) => {
                    setCustomQuery(e.target.value);
                    setSelectedCategory("");
                  }}
                  className="pl-10 h-11"
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && searchQuery) {
                      handleContinueToStep2();
                    }
                  }}
                />
              </div>

              <Button
                onClick={handleContinueToStep2}
                disabled={!searchQuery}
                className="w-full mt-4 h-11 text-base"
              >
                Покажи ми тендери
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          ) : (
            /* ========== STEP 2: Results Preview ========== */
            <div className="p-6 md:p-8">
              <div className="text-center mb-5">
                <h2 className="text-lg md:text-xl font-bold text-foreground">
                  Еве што пропуштате на e-nabavki.gov.mk
                </h2>
                <p className="text-sm text-muted-foreground mt-1">
                  Најдовме <span className="text-primary font-semibold">{totalTenders.toLocaleString()}</span> тендери
                  за &quot;{searchQuery}&quot;
                </p>
              </div>

              {loading ? (
                <div className="flex flex-col items-center justify-center py-12">
                  <Loader2 className="h-8 w-8 text-primary animate-spin mb-3" />
                  <p className="text-sm text-muted-foreground">Пребаруваме 282,000+ тендери...</p>
                </div>
              ) : (
                <>
                  {/* Tender preview list */}
                  <div className="space-y-2 mb-4 max-h-[300px] overflow-y-auto">
                    {searchError ? (
                      <div className="text-center py-6">
                        <AlertCircle className="h-8 w-8 text-destructive mx-auto mb-2" />
                        <p className="text-sm text-muted-foreground">
                          Грешка при пребарување. Обидете се повторно.
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3"
                          onClick={() => { setStep(1); setSearchError(false); }}
                        >
                          Назад
                        </Button>
                      </div>
                    ) : tenders.length === 0 ? (
                      <div className="text-center py-6 text-sm text-muted-foreground">
                        Нема тендери за овој период. Пробајте со друг термин.
                      </div>
                    ) : (
                      tenders.slice(0, 5).map((tender) => (
                        <div
                          key={tender.tender_id}
                          className="p-3 rounded-lg border bg-background/50 hover:bg-foreground/5 transition-colors"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1 min-w-0">
                              <h4 className="text-sm font-medium line-clamp-1 text-foreground">
                                {tender.title}
                              </h4>
                              <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1">
                                <Building2 className="h-3 w-3 flex-shrink-0" />
                                <span className="line-clamp-1">{tender.procuring_entity}</span>
                              </p>
                            </div>
                            {tender.estimated_value_mkd && (
                              <span className="text-xs font-semibold text-primary whitespace-nowrap">
                                {formatCurrency(tender.estimated_value_mkd)}
                              </span>
                            )}
                          </div>
                          {tender.closing_date && (
                            <p className="text-[10px] text-orange-400 mt-1 flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              Краен рок: {new Date(tender.closing_date).toLocaleDateString("mk-MK")}
                            </p>
                          )}
                        </div>
                      ))
                    )}
                  </div>

                  {/* Value callouts */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mb-4">
                    <div className="flex items-center gap-2 p-2.5 rounded-lg bg-primary/5 border border-primary/10">
                      <Search className="h-4 w-4 text-primary flex-shrink-0" />
                      <span className="text-[11px] text-foreground">AI пребарување на <b>70K</b> документи</span>
                    </div>
                    <div className="flex items-center gap-2 p-2.5 rounded-lg bg-green-500/5 border border-green-500/10">
                      <Package className="h-4 w-4 text-green-500 flex-shrink-0" />
                      <span className="text-[11px] text-foreground"><b>3.2M</b> производи со цени</span>
                    </div>
                    <div className="flex items-center gap-2 p-2.5 rounded-lg bg-orange-500/5 border border-orange-500/10">
                      <Bell className="h-4 w-4 text-orange-500 flex-shrink-0" />
                      <span className="text-[11px] text-foreground">
                        {alertCreated ? (
                          <span className="flex items-center gap-1">
                            <CheckCircle2 className="h-3 w-3 text-green-500" /> Алерт креиран!
                          </span>
                        ) : (
                          "Автоматски алерти"
                        )}
                      </span>
                    </div>
                  </div>

                  {/* Comparison callout */}
                  <div className="text-center text-xs text-muted-foreground mb-4 px-4">
                    На <span className="font-medium">e-nabavki.gov.mk</span> ова би ви одземало часови рачно пребарување.
                    Ние го правиме за <span className="text-primary font-semibold">секунди</span>.
                  </div>

                  <Button onClick={handleComplete} className="w-full h-11 text-base">
                    Продолжи кон тендерите
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
