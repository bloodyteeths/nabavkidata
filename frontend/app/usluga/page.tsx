import { Suspense } from "react";
import { Metadata } from "next";
import Link from "next/link";
import Navbar from "@/components/landing/Navbar";
import QualifyForm from "@/components/service/QualifyForm";
import { CheckCircle2, FileText, Bell, ShieldCheck, Search, PenLine, Send } from "lucide-react";

export const metadata: Metadata = {
  title: "Ние ја пишуваме вашата тендерска понуда | NabavkiData",
  description:
    "Ги следиме тендерите на е-набавки за вас и ја подготвуваме целата тендерска документација. Вие ја прегледувате, потпишувате и поднесувате. Од 30.000 МКД по понуда без ДДВ.",
  alternates: {
    canonical: "https://www.nabavkidata.com/usluga",
  },
  openGraph: {
    title: "Ние ја пишуваме вашата тендерска понуда | NabavkiData",
    description:
      "Следење на тендери и подготовка на понуди за македонски компании. Нарачајте понуда.",
    url: "https://www.nabavkidata.com/usluga",
  },
};

type SearchParams = { [key: string]: string | string[] | undefined };

function firstParam(value: string | string[] | undefined): string | undefined {
  const v = Array.isArray(value) ? value[0] : value;
  const trimmed = v?.trim();
  return trimmed ? trimmed : undefined;
}

/** Keep the source tag short and boring so it is safe to store as-is. */
function cleanSource(value: string | undefined): string {
  if (!value) return "usluga";
  const cleaned = value.replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 40);
  return cleaned || "usluga";
}

/** Tender ids look like "12345/2025"; anything else is dropped. */
function cleanTenderId(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const cleaned = value.slice(0, 64);
  return /^[0-9A-Za-zЀ-ӿ/:._-]+$/.test(cleaned) ? cleaned : undefined;
}

const bullets = [
  {
    icon: Bell,
    title: "Ги следиме тендерите за вас",
    text: "Секој нов тендер на е-набавки го споредуваме со вашата дејност и ви јавуваме кога има нешто што можете да добиете. Следењето на тендери, известувањата и AI асистентот за прашања се вклучени за клиентите.",
  },
  {
    icon: FileText,
    title: "Ја пишуваме целата понуда",
    text: "Ја читаме тендерската документација, ги проверуваме условите за способност и ги подготвуваме сите изјави, техничката и финансиската понуда.",
  },
  {
    icon: ShieldCheck,
    title: "Вие одлучувате и поднесувате",
    text: "Понудата ја прегледувате, ја потпишувате со вашиот сертификат и ја поднесувате самите на е-набавки. Ништо не се поднесува без вас.",
  },
];

const steps = [
  { icon: Search, title: "Барање за понуда", text: "Кажете ни кој тендер или каква работа сакате да добиете. Во рок од еден работен ден ви одговараме кои тендери се соодветни за вас и колку чини подготовката." },
  { icon: PenLine, title: "Договор и подготовка", text: "За секоја понуда се договараме однапред. Потоа ја подготвуваме целата документација." },
  { icon: Send, title: "Преглед и поднесување", text: "Ја добивате готовата понуда, ја проверувате и ја поднесувате на е-набавки пред рокот." },
];

export default function UslugaPage({ searchParams }: { searchParams: SearchParams }) {
  const source = cleanSource(firstParam(searchParams.src));
  const tenderId = cleanTenderId(firstParam(searchParams.tender) ?? firstParam(searchParams.tender_id));

  return (
    <main className="min-h-screen bg-background text-foreground overflow-x-hidden">
      <Navbar />

      <section className="relative pt-28 pb-16 md:pt-32">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-primary/10 via-background to-background" />

        <div className="container relative z-10 px-4 md:px-6">
          <div className="grid gap-10 lg:grid-cols-[1.1fr_1fr] lg:gap-14 max-w-6xl mx-auto items-start">
            {/* Pitch */}
            <div>
              <span className="inline-block px-3 py-1 rounded-full text-sm font-medium bg-primary/10 text-primary mb-5">
                Подготовка на тендерски понуди
              </span>
              <h1 className="text-4xl md:text-5xl font-bold leading-tight mb-5">
                <span className="text-foreground">Ние ја пишуваме </span>
                <span className="text-gradient">вашата тендерска понуда</span>
              </h1>
              <p className="text-lg text-muted-foreground leading-relaxed mb-8">
                NabavkiData сега ги следи тендерите и ги подготвува понудите за вас. Вие продолжувате да ја водите
                фирмата, ние се грижиме за документацијата.
              </p>

              <ul className="space-y-5">
                {bullets.map(({ icon: Icon, title, text }) => (
                  <li key={title} className="flex gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-purple-600 text-white">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="font-semibold text-foreground">{title}</p>
                      <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{text}</p>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* Form */}
            <div className="glass rounded-2xl border border-border p-6 md:p-8 shadow-lg">
              <h2 className="text-xl font-semibold mb-1">
                {tenderId ? `Понуда за тендер ${tenderId}` : "Барање за понуда"}
              </h2>
              <p className="text-sm text-muted-foreground mb-6">
                {tenderId
                  ? "Оставете ни податоци и ќе ви кажеме дали и како можеме да ја подготвиме понудата пред рокот."
                  : "Кажете ни кои сте и што сакате да добиете. Ќе ви одговориме со предлог и цена за подготовка."}
              </p>
              <Suspense fallback={<div className="min-h-[420px]" />}>
                <QualifyForm tenderId={tenderId ?? null} source={source} />
              </Suspense>
            </div>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-16 border-t border-border">
        <div className="container px-4 md:px-6 max-w-5xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-center mb-10">Како работиме</h2>
          <div className="grid gap-6 md:grid-cols-3">
            {steps.map(({ icon: Icon, title, text }, i) => (
              <div key={title} className="relative h-full rounded-2xl border border-border bg-foreground/5 p-6">
                <div className="flex items-center gap-3 mb-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
                    {i + 1}
                  </span>
                  <Icon className="h-5 w-5 text-primary" />
                </div>
                <p className="font-semibold mb-1">{title}</p>
                <p className="text-sm text-muted-foreground leading-relaxed">{text}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Fees */}
      <section className="py-16 border-t border-border">
        <div className="container px-4 md:px-6 max-w-3xl mx-auto">
          <h2 className="text-2xl md:text-3xl font-bold text-center mb-8">Колку чини</h2>
          <div className="rounded-2xl border border-border bg-foreground/5 p-6 md:p-8">
            <ul className="space-y-4 text-sm md:text-base">
              <li className="flex gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                <span>
                  <strong>Вклучено за клиентите:</strong> следење на тендери, известувања, AI асистент за прашања, историја на победнички цени и анализа на конкуренти.
                </span>
              </li>
              <li className="flex gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                <span>
                  <strong>Подготовка на понуда:</strong> од 30.000 МКД по понуда, без ДДВ. Цената ја договараме пред да започнеме
                  со работа.
                </span>
              </li>
              <li className="flex gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                <span>
                  <strong>Надомест за успех:</strong> 5% од вредноста на договорот за првата година, само ако го добиете
                  тендерот. Платениот надомест за подготовка на таа понуда се одбива.
                </span>
              </li>
              <li className="flex gap-3">
                <CheckCircle2 className="h-5 w-5 text-green-600 shrink-0 mt-0.5" />
                <span>
                  <strong>Плаќање:</strong> со картичка преку Stripe или, на барање, со фактура на трансакциска сметка на
                  Фактурино ДООЕЛ. Без претплата. Зачуваната картичка се користи за надоместот за успех, најрано седум
                  дена по нашата писмена најава.
                </span>
              </li>
            </ul>
            <p className="text-xs text-muted-foreground mt-6">
              Деталните услови се договараат писмено пред секоја понуда. Видете и{" "}
              <Link href="/terms" className="underline hover:text-primary">
                Услови за користење
              </Link>
              .
            </p>
          </div>
        </div>
      </section>

      <footer className="py-10 border-t border-border bg-background/20">
        <div className="container px-4 md:px-6">
          <div className="flex flex-col md:flex-row justify-between gap-4 text-sm text-muted-foreground">
            <div className="space-y-1">
              <p className="font-medium text-foreground">Фактурино ДООЕЛ</p>
              <p>ул. Сараевска 37, 1400 Велес</p>
              <p>ЕДБ 4004026525934 · ЕМБС 7922400</p>
            </div>
            <div className="space-y-1 md:text-right">
              <p>
                <a href="mailto:hello@nabavkidata.com" className="hover:text-primary transition-colors">
                  hello@nabavkidata.com
                </a>
              </p>
              <p>
                <a href="tel:+38970253467" className="hover:text-primary transition-colors">
                  +389 70 253 467
                </a>
              </p>
              <nav className="flex gap-4 md:justify-end pt-1">
                <Link href="/privacy" className="hover:text-primary transition-colors">
                  Приватност
                </Link>
                <Link href="/terms" className="hover:text-primary transition-colors">
                  Услови
                </Link>
                <Link href="/contact" className="hover:text-primary transition-colors">
                  Контакт
                </Link>
              </nav>
            </div>
          </div>
        </div>
      </footer>
    </main>
  );
}
