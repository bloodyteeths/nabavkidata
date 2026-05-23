import { Metadata } from "next";
import Link from "next/link";

export function generateMetadata(): Metadata {
  return {
    title: "Тендери за Градежништво — Јавни набавки за градежни компании | NabavkiData",
    description: "Следете тендери за градежништво во Македонија. Над 5,000 тендери за градба, реконструкција, патишта и инфраструктура. AI анализа, аларми и ценовна интелигенција.",
    openGraph: {
      title: "Тендери за Градежништво | NabavkiData",
      description: "Најдете и анализирајте тендери за градежништво во Македонија — градба, реконструкција, патишта, инфраструктура.",
      url: "https://nabavkidata.com/gradeznistvo",
    },
    alternates: {
      canonical: "https://nabavkidata.com/gradeznistvo",
    },
  };
}

export default function GradeznishtvoPage() {
  return (
    <div className="min-h-screen bg-background">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebPage",
            name: "Тендери за Градежништво — NabavkiData",
            description: "Следете тендери за градежништво во Македонија. AI анализа, аларми и ценовна интелигенција за градежни компании.",
            url: "https://nabavkidata.com/gradeznistvo",
            breadcrumb: {
              "@type": "BreadcrumbList",
              itemListElement: [
                { "@type": "ListItem", position: 1, name: "Почетна", item: "https://nabavkidata.com" },
                { "@type": "ListItem", position: 2, name: "Градежништво" },
              ],
            },
          }),
        }}
      />

      <div className="container mx-auto px-4 py-12 max-w-5xl">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <span className="inline-block px-3 py-1 rounded-full text-sm font-medium bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300 mb-4">
            Градежништво
          </span>
          <h1 className="text-4xl md:text-5xl font-bold mb-6 text-foreground">
            Тендери за градежништво во Македонија
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            Градежништвото е еден од најголемите сектори во јавните набавки.
            NabavkiData ви помага да ги најдете вистинските тендери, да ги анализирате конкурентите
            и да победите почесто.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-16">
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">5,000+</div>
            <div className="text-sm text-muted-foreground">тендери за градежништво</div>
          </div>
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">1,200+</div>
            <div className="text-sm text-muted-foreground">градежни компании</div>
          </div>
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">15+ млрд</div>
            <div className="text-sm text-muted-foreground">МКД вкупна вредност</div>
          </div>
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">2008+</div>
            <div className="text-sm text-muted-foreground">историски податоци</div>
          </div>
        </div>

        {/* Sector Description */}
        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div>
            <h2 className="text-2xl font-bold mb-4 text-foreground">Зошто NabavkiData за градежни компании?</h2>
            <div className="space-y-4 text-muted-foreground">
              <p>
                Градежниот сектор во јавните набавки вклучува изградба на згради, патишта,
                мостови, водоводи, канализации, реконструкции и инфраструктурни проекти.
                Секоја година се објавуваат стотици нови тендери со вредност од милиони денари.
              </p>
              <p>
                Наместо рачно да пребарувате на ЕСЈН, NabavkiData автоматски ги следи
                сите тендери, ве известува за нови можности и ви дава AI анализа
                на секој тендер — вклучувајќи ценовна проценка и анализа на конкуренти.
              </p>
              <p>
                Со нашите аларми, веднаш добивате известување кога ќе се објави тендер
                за вашата специјалност — било да е тоа армиранобетонски работи, асфалтирање,
                водоводна инсталација или електроинсталации.
              </p>
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-bold mb-4 text-foreground">Клучни CPV категории</h2>
            <div className="space-y-3">
              {[
                { code: "45000000", name: "Градежни работи", desc: "Главна категорија за сите градежни тендери" },
                { code: "45200000", name: "Работи на комплетни или делумни градежни конструкции", desc: "Нови објекти и реконструкции" },
                { code: "45230000", name: "Изградба на цевководи, комуникациски и електрични водови", desc: "Инфраструктура и мрежи" },
                { code: "45233000", name: "Изградба, поставување и одржување на патишта", desc: "Патна инфраструктура" },
                { code: "45300000", name: "Работи на инсталации во згради", desc: "Водоводни, електрични, грејни инсталации" },
                { code: "45400000", name: "Завршни градежни работи", desc: "Молерски, столарски, подни работи" },
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
              <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-4">
                <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
              </div>
              <h3 className="font-semibold text-lg mb-2 text-foreground">Аларми по клучни зборови</h3>
              <p className="text-sm text-muted-foreground">
                Поставете аларм за &quot;асфалтирање&quot;, &quot;реконструкција&quot; или &quot;водовод&quot; и добивајте
                известување веднаш кога ќе се објави релевантен тендер.
              </p>
            </div>
            <div className="p-6 rounded-xl bg-card border">
              <div className="w-10 h-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
                <svg className="w-5 h-5 text-green-600 dark:text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <h3 className="font-semibold text-lg mb-2 text-foreground">Анализа на конкуренти</h3>
              <p className="text-sm text-muted-foreground">
                Видете кои компании најчесто победуваат на градежни тендери, по колку
                понудуваат и во кои региони се активни.
              </p>
            </div>
            <div className="p-6 rounded-xl bg-card border">
              <div className="w-10 h-10 rounded-lg bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center mb-4">
                <svg className="w-5 h-5 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-lg mb-2 text-foreground">Ценовна интелигенција</h3>
              <p className="text-sm text-muted-foreground">
                Дознајте колку чинат слични проекти. AI анализира историски цени
                за да ви помогне да дадете конкурентна понуда.
              </p>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center py-12 px-6 rounded-2xl bg-gradient-to-br from-orange-50 to-amber-50 dark:from-orange-950/20 dark:to-amber-950/20 border">
          <h2 className="text-2xl md:text-3xl font-bold mb-4 text-foreground">
            Не пропуштајте градежни тендери
          </h2>
          <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
            Регистрацијата е бесплатна. Поставете аларми за вашата специјалност
            и добивајте известувања за секој нов тендер.
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
              href="/categories/45000000"
              className="inline-flex items-center justify-center px-6 py-3 rounded-lg border font-medium hover:bg-muted transition-colors text-foreground"
            >
              Прегледај градежни тендери
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
