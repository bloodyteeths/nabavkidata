import { Metadata } from "next";
import Link from "next/link";

export function generateMetadata(): Metadata {
  return {
    title: "Тендери за ИТ услуги — Јавни набавки за софтвер, хардвер и дигитализација | NabavkiData",
    description: "Следете тендери за ИТ услуги во Македонија. Софтверски решенија, хардвер, мрежна опрема, одржување на системи, дигитализација и консултантски услуги.",
    openGraph: {
      title: "Тендери за ИТ услуги | NabavkiData",
      description: "Најдете тендери за софтвер, хардвер, ИТ услуги и дигитализација во Македонија.",
      url: "https://nabavkidata.com/it-uslugi",
    },
    alternates: {
      canonical: "https://nabavkidata.com/it-uslugi",
    },
  };
}

export default function ITUslugiPage() {
  return (
    <div className="min-h-screen bg-background">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebPage",
            name: "Тендери за ИТ услуги — NabavkiData",
            description: "Следете тендери за ИТ услуги, софтвер, хардвер и дигитализација во Македонија.",
            url: "https://nabavkidata.com/it-uslugi",
            breadcrumb: {
              "@type": "BreadcrumbList",
              itemListElement: [
                { "@type": "ListItem", position: 1, name: "Почетна", item: "https://nabavkidata.com" },
                { "@type": "ListItem", position: 2, name: "ИТ услуги" },
              ],
            },
          }),
        }}
      />

      <div className="container mx-auto px-4 py-12 max-w-5xl">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <span className="inline-block px-3 py-1 rounded-full text-sm font-medium bg-indigo-100 text-indigo-800 dark:bg-indigo-900/30 dark:text-indigo-300 mb-4">
            ИТ услуги
          </span>
          <h1 className="text-4xl md:text-5xl font-bold mb-6 text-foreground">
            Тендери за ИТ услуги и дигитализација
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            Дигитализацијата на јавниот сектор создава растечки пазар за ИТ компании.
            NabavkiData ви помага да ги следите тендерите за софтвер, хардвер,
            мрежна опрема и ИТ консалтинг.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-16">
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">3,500+</div>
            <div className="text-sm text-muted-foreground">ИТ тендери</div>
          </div>
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">400+</div>
            <div className="text-sm text-muted-foreground">ИТ компании</div>
          </div>
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">5+ млрд</div>
            <div className="text-sm text-muted-foreground">МКД вкупна вредност</div>
          </div>
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">50+</div>
            <div className="text-sm text-muted-foreground">нарачатели годишно</div>
          </div>
        </div>

        {/* Sector Description */}
        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div>
            <h2 className="text-2xl font-bold mb-4 text-foreground">Зошто NabavkiData за ИТ компании?</h2>
            <div className="space-y-4 text-muted-foreground">
              <p>
                ИТ секторот во јавните набавки вклучува развој на софтверски решенија,
                набавка на хардвер и мрежна опрема, одржување на информациски системи,
                лиценци, cloud услуги, кибер безбедност и дигитална трансформација.
              </p>
              <p>
                Владата и јавните институции се значајни нарачатели на ИТ услуги —
                од е-влада проекти до дигитализација на здравствениот систем.
                NabavkiData ги следи сите овие тендери на едно место.
              </p>
              <p>
                Со AI анализа, дознајте кои ИТ компании најчесто победуваат,
                какви буџети се одобруваат за слични проекти и кои институции
                најчесто набавуваат ИТ услуги.
              </p>
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-bold mb-4 text-foreground">Клучни CPV категории</h2>
            <div className="space-y-3">
              {[
                { code: "72000000", name: "ИТ услуги: консултации, развој на софтвер, интернет и поддршка", desc: "Главна ИТ категорија" },
                { code: "72200000", name: "Програмирање на софтвер и консултации", desc: "Развој на апликации и системи" },
                { code: "72400000", name: "Интернет услуги", desc: "Хостинг, домени, cloud услуги" },
                { code: "48000000", name: "Софтверски пакети и информациски системи", desc: "Лиценци, ERP, CRM системи" },
                { code: "30200000", name: "Компјутерска опрема и материјали", desc: "Компјутери, сервери, периферија" },
                { code: "32400000", name: "Мрежна опрема", desc: "Рутери, свичеви, firewall-и" },
              ].map((cpv) => (
                <Link
                  key={cpv.code}
                  href={`/categories/${cpv.code}`}
                  className="block p-4 rounded-lg border hover:border-primary hover:bg-muted/50 transition-colors"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <span className="font-semibold text-foreground">{cpv.name}</span>
                      <p className="text-sm text-muted-foreground mt-1">{cpv.desc}</p>
                    </div>
                    <span className="text-xs font-mono text-muted-foreground bg-muted px-2 py-1 rounded">
                      {cpv.code}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Features */}
        <div className="mb-16">
          <h2 className="text-2xl font-bold text-center mb-8 text-foreground">Како NabavkiData помага</h2>
          <div className="grid md:grid-cols-3 gap-6">
            <div className="p-6 rounded-xl bg-card border">
              <div className="w-10 h-10 rounded-lg bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center mb-4">
                <svg className="w-5 h-5 text-indigo-600 dark:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-lg mb-2 text-foreground">Билингвално пребарување</h3>
              <p className="text-sm text-muted-foreground">
                Пишувајте &quot;software&quot; или &quot;софтвер&quot; — NabavkiData ги наоѓа
                и кирилските и латиничните тендери. Автоматска транслитерација.
              </p>
            </div>
            <div className="p-6 rounded-xl bg-card border">
              <div className="w-10 h-10 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center mb-4">
                <svg className="w-5 h-5 text-violet-600 dark:text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <h3 className="font-semibold text-lg mb-2 text-foreground">AI извлекување на документи</h3>
              <p className="text-sm text-muted-foreground">
                Автоматски извлекуваме технички спецификации, критериуми за избор
                и буџетски рамки од тендерската документација.
              </p>
            </div>
            <div className="p-6 rounded-xl bg-card border">
              <div className="w-10 h-10 rounded-lg bg-cyan-100 dark:bg-cyan-900/30 flex items-center justify-center mb-4">
                <svg className="w-5 h-5 text-cyan-600 dark:text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                </svg>
              </div>
              <h3 className="font-semibold text-lg mb-2 text-foreground">Трендови и анализа</h3>
              <p className="text-sm text-muted-foreground">
                Следете го растот на ИТ набавките, кои технологии се барани
                и кои институции најмногу инвестираат во дигитализација.
              </p>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center py-12 px-6 rounded-2xl bg-gradient-to-br from-indigo-50 to-violet-50 dark:from-indigo-950/20 dark:to-violet-950/20 border">
          <h2 className="text-2xl md:text-3xl font-bold mb-4 text-foreground">
            Не пропуштајте ИТ тендери
          </h2>
          <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
            Регистрацијата е бесплатна. Поставете аларми за софтвер, хардвер
            или ИТ консалтинг и добивајте известувања за секој нов тендер.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/auth/register"
              className="inline-flex items-center justify-center px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
            >
              Регистрирајте се бесплатно
              <svg className="ml-2 w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
              </svg>
            </Link>
            <Link
              href="/categories/72000000"
              className="inline-flex items-center justify-center px-6 py-3 rounded-lg border font-medium hover:bg-muted transition-colors text-foreground"
            >
              Прегледај ИТ тендери
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
