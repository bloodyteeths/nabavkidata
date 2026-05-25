import { Metadata } from "next";
import Link from "next/link";
import {
  Monitor,
  HardHat,
  Stethoscope,
  Printer,
  UtensilsCrossed,
  Truck,
  SprayCan,
  Shield,
  Briefcase,
  Cog,
  Zap,
  FileText,
  ArrowRight,
} from "lucide-react";

export const metadata: Metadata = {
  title: "Сектори — тендери по дејност | NabavkiData",
  description:
    "Пребарувајте тендери по сектор: ИТ, градежништво, медицина, транспорт, енергетика, чистење, обезбедување и повеќе.",
  openGraph: {
    title: "Сектори — тендери по дејност",
    description: "12 сектори со јавни набавки во Македонија.",
    url: "https://www.nabavkidata.com/sectors",
  },
};

const SECTORS = [
  { slug: "it-digitalni-uslugi", name: "ИТ и дигитални услуги", icon: Monitor },
  { slug: "gradeznistvo", name: "Градежништво", icon: HardHat },
  { slug: "medicinska-oprema", name: "Медицинска опрема", icon: Stethoscope },
  { slug: "kancelariski-materijali", name: "Канцелариски материјали", icon: Printer },
  { slug: "hrana-pijaloci", name: "Храна и пијалоци", icon: UtensilsCrossed },
  { slug: "transport-vozila", name: "Транспорт и возила", icon: Truck },
  { slug: "cistenje-odrzuvanje", name: "Чистење и одржување", icon: SprayCan },
  { slug: "obezbeduvawe", name: "Обезбедување", icon: Shield },
  { slug: "konsultantski-uslugi", name: "Консултантски услуги", icon: Briefcase },
  { slug: "oprema-masini", name: "Опрема и машини", icon: Cog },
  { slug: "energetika", name: "Енергетика", icon: Zap },
  { slug: "pecatenje-marketing", name: "Печатење и маркетинг", icon: FileText },
];

export default function SectorsPage() {
  return (
    <div className="container mx-auto py-12 px-4">
      <div className="text-center mb-10">
        <h1 className="text-4xl font-bold mb-3">Тендери по сектор</h1>
        <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
          Изберете го секторот на вашата дејност и видете ги последните јавни
          набавки.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
        {SECTORS.map((s) => {
          const Icon = s.icon;
          return (
            <Link
              key={s.slug}
              href={`/sectors/${s.slug}`}
              className="group flex items-center gap-4 p-5 rounded-xl border border-border hover:border-primary/40 hover:bg-primary/5 transition-all"
            >
              <div className="p-3 rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
                <Icon className="h-6 w-6 text-primary" />
              </div>
              <div className="flex-1">
                <h2 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                  {s.name}
                </h2>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" />
            </Link>
          );
        })}
      </div>

      <div className="sr-only" aria-hidden="true">
        <h2>Тендери по сектор и регион</h2>
        {SECTORS.map((s) => (
          <div key={s.slug}>
            <h3>{s.name}</h3>
            <ul>
              <li><a href={`/sectors/${s.slug}/skopje`}>{s.name} — Скопје</a></li>
              <li><a href={`/sectors/${s.slug}/bitola`}>{s.name} — Битола</a></li>
              <li><a href={`/sectors/${s.slug}/kumanovo`}>{s.name} — Куманово</a></li>
              <li><a href={`/sectors/${s.slug}/prilep`}>{s.name} — Прилеп</a></li>
              <li><a href={`/sectors/${s.slug}/tetovo`}>{s.name} — Тетово</a></li>
              <li><a href={`/sectors/${s.slug}/ohrid`}>{s.name} — Охрид</a></li>
              <li><a href={`/sectors/${s.slug}/veles`}>{s.name} — Велес</a></li>
              <li><a href={`/sectors/${s.slug}/stip`}>{s.name} — Штип</a></li>
              <li><a href={`/sectors/${s.slug}/strumica`}>{s.name} — Струмица</a></li>
              <li><a href={`/sectors/${s.slug}/gostivar`}>{s.name} — Гостивар</a></li>
              <li><a href={`/sectors/${s.slug}/kavadarci`}>{s.name} — Кавадарци</a></li>
              <li><a href={`/sectors/${s.slug}/kocani`}>{s.name} — Кочани</a></li>
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
