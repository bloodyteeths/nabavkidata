"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_URL =
  typeof window !== "undefined"
    ? window.location.hostname === "localhost"
      ? "http://localhost:8000"
      : "https://api.nabavkidata.com"
    : "https://api.nabavkidata.com";

interface FlaggedTender {
  tender_id: string;
  title: string;
  institution: string;
  risk_score: number;
  risk_level: string;
  value_mkd: number;
  flag_types: string[];
}

interface PublicStats {
  total_tenders: number;
  total_flags: number;
  total_tenders_flagged: number;
  total_value_at_risk_mkd: number;
  total_relationships: number;
  by_severity: Record<string, number>;
  by_type: Record<string, number>;
  top_flagged: FlaggedTender[];
}

const FLAG_TYPE_LABELS: Record<string, string> = {
  single_bidder: "Единствен понудувач",
  repeat_winner: "Повторлив победник",
  price_anomaly: "Ценовна аномалија",
  threshold_manipulation: "Манипулација со прагови",
  short_deadline: "Краток рок",
  identical_bids: "Идентични понуди",
  late_modification: "Доцна модификација",
  split_procurement: "Поделена набавка",
  unusual_criteria: "Невообичаени критериуми",
  conflict_of_interest: "Конфликт на интереси",
  geographic_concentration: "Географска концентрација",
  contract_amendment: "Измена на договор",
  emergency_procedure: "Итна постапка",
  bid_rotation: "Ротација на понуди",
  market_concentration: "Пазарна концентрација",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-600",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-blue-400",
  minimal: "bg-gray-300",
};

const SEVERITY_LABELS: Record<string, string> = {
  critical: "Критично",
  high: "Високо",
  medium: "Средно",
  low: "Ниско",
  minimal: "Минимално",
};

function formatNumber(n: number): string {
  return n.toLocaleString("mk-MK");
}

function formatMKD(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)} млрд. МКД`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)} мил. МКД`;
  return `${formatNumber(n)} МКД`;
}

export default function TransparencyPage() {
  const [stats, setStats] = useState<PublicStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/corruption/public-stats`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setStats)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Се вчитуваат податоци...</p>
        </div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-600 text-lg">Грешка при вчитување: {error}</p>
        </div>
      </div>
    );
  }

  const totalSeverity = Object.values(stats.by_severity).reduce((a, b) => a + b, 0) || 1;
  const sortedTypes = Object.entries(stats.by_type)
    .sort(([, a], [, b]) => b - a)
    .filter(([, count]) => count > 0);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-blue-700 to-blue-900 text-white">
        <div className="max-w-6xl mx-auto px-4 py-12 sm:py-16">
          <div className="flex items-center gap-3 mb-4">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
            <span className="text-lg font-medium opacity-80">NabavkiData</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-bold mb-3">
            Транспарентност на јавни набавки
          </h1>
          <p className="text-blue-100 text-lg max-w-2xl">
            AI систем за автоматска детекција на корупциски ризици во јавните набавки
            во Северна Македонија
          </p>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8 space-y-8">
        {/* Hero Stats */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <StatCard label="Тендери мониторирани" value={formatNumber(stats.total_tenders)} />
          <StatCard label="Корупциски знаменца" value={formatNumber(stats.total_flags)} accent />
          <StatCard label="Тендери со ризик" value={formatNumber(stats.total_tenders_flagged)} />
          <StatCard label="Вредност под ризик" value={formatMKD(stats.total_value_at_risk_mkd)} accent />
          <StatCard label="Поврзани компании" value={formatNumber(stats.total_relationships)} />
        </div>

        {/* Risk Distribution */}
        <section className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Дистрибуција по ниво на ризик</h2>
          <div className="flex rounded-lg overflow-hidden h-10 mb-4">
            {["critical", "high", "medium", "low", "minimal"].map((level) => {
              const count = stats.by_severity[level] || 0;
              const pct = (count / totalSeverity) * 100;
              if (pct < 0.5) return null;
              return (
                <div
                  key={level}
                  className={`${SEVERITY_COLORS[level]} relative group`}
                  style={{ width: `${pct}%` }}
                  title={`${SEVERITY_LABELS[level]}: ${formatNumber(count)}`}
                >
                  {pct > 8 && (
                    <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-white">
                      {pct.toFixed(0)}%
                    </span>
                  )}
                </div>
              );
            })}
          </div>
          <div className="flex flex-wrap gap-4 text-sm">
            {["critical", "high", "medium", "low", "minimal"].map((level) => (
              <div key={level} className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-sm ${SEVERITY_COLORS[level]}`} />
                <span className="text-gray-600">
                  {SEVERITY_LABELS[level]}: <strong>{formatNumber(stats.by_severity[level] || 0)}</strong>
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Flag Types */}
        <section className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Типови на детектирани индикатори</h2>
          <div className="space-y-3">
            {sortedTypes.map(([type, count]) => {
              const maxCount = sortedTypes[0]?.[1] || 1;
              const pct = (count / maxCount) * 100;
              return (
                <div key={type} className="flex items-center gap-3">
                  <div className="w-48 sm:w-64 text-sm text-gray-700 shrink-0">
                    {FLAG_TYPE_LABELS[type] || type}
                  </div>
                  <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
                    <div
                      className="bg-blue-600 h-full rounded-full transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <div className="w-20 text-right text-sm font-medium text-gray-900">
                    {formatNumber(count)}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* Top Flagged Tenders */}
        <section className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Најризични тендери</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="pb-3 pr-4">Тендер</th>
                  <th className="pb-3 pr-4">Институција</th>
                  <th className="pb-3 pr-4 text-center">Ризик</th>
                  <th className="pb-3 pr-4 text-right">Вредност</th>
                  <th className="pb-3">Индикатори</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {stats.top_flagged.map((t) => (
                  <tr key={t.tender_id} className="hover:bg-gray-50">
                    <td className="py-3 pr-4">
                      <div className="font-medium text-gray-900 line-clamp-2 max-w-xs">
                        {t.title}
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">{t.tender_id}</div>
                    </td>
                    <td className="py-3 pr-4 text-gray-600 max-w-[200px] truncate">
                      {t.institution}
                    </td>
                    <td className="py-3 pr-4 text-center">
                      <span
                        className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium text-white ${
                          t.risk_level === "critical" ? "bg-red-600" : "bg-orange-500"
                        }`}
                      >
                        {t.risk_score}
                      </span>
                    </td>
                    <td className="py-3 pr-4 text-right text-gray-700 whitespace-nowrap">
                      {t.value_mkd > 0 ? formatMKD(t.value_mkd) : "—"}
                    </td>
                    <td className="py-3">
                      <div className="flex flex-wrap gap-1">
                        {t.flag_types.slice(0, 3).map((ft) => (
                          <span
                            key={ft}
                            className="inline-block px-2 py-0.5 bg-red-50 text-red-700 rounded text-xs"
                          >
                            {FLAG_TYPE_LABELS[ft] || ft}
                          </span>
                        ))}
                        {t.flag_types.length > 3 && (
                          <span className="text-xs text-gray-400">+{t.flag_types.length - 3}</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* CTA */}
        <section className="bg-gradient-to-r from-blue-700 to-blue-900 rounded-xl p-8 text-white text-center">
          <h2 className="text-2xl font-bold mb-3">Заинтересирани за пилот проект?</h2>
          <p className="text-blue-100 mb-6 max-w-xl mx-auto">
            Нудиме бесплатен пилот (3 месеци) за институции и организации кои работат
            на транспарентност и борба против корупција.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <a
              href="mailto:hello@nabavkidata.com?subject=Пилот%20проект%20—%20транспарентност"
              className="inline-flex items-center justify-center px-6 py-3 bg-white text-blue-700 font-semibold rounded-lg hover:bg-blue-50 transition"
            >
              hello@nabavkidata.com
            </a>
            <a
              href="tel:+38970253467"
              className="inline-flex items-center justify-center px-6 py-3 border-2 border-white/40 text-white font-medium rounded-lg hover:bg-white/10 transition"
            >
              +389 70 253 467
            </a>
          </div>
        </section>

        {/* Disclaimer */}
        <p className="text-center text-xs text-gray-400 pb-8">
          Оваа анализа е базирана на јавно достапни податоци од е-набавки и е само за информативни цели.
          Детектираните индикатори не претставуваат доказ за корупција.
          &copy; {new Date().getFullYear()} Фактурино ДООЕЛ — nabavkidata.com
        </p>
      </main>
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className={`rounded-xl p-4 sm:p-5 shadow-sm border ${accent ? "bg-blue-50 border-blue-200" : "bg-white"}`}>
      <div className={`text-xl sm:text-2xl font-bold ${accent ? "text-blue-700" : "text-gray-900"}`}>
        {value}
      </div>
      <div className="text-xs sm:text-sm text-gray-500 mt-1">{label}</div>
    </div>
  );
}
