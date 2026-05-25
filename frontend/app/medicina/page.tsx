import { Metadata } from "next";
import Link from "next/link";

export function generateMetadata(): Metadata {
  return {
    title: "Тендери за Медицина и Здравство — Јавни набавки за здравствени установи | NabavkiData",
    description: "Следете тендери за медицинска опрема, лекови, лабораториски материјали и здравствени услуги во Македонија. AI анализа и аларми за фармацевтски и медицински компании.",
    openGraph: {
      title: "Тендери за Медицина и Здравство | NabavkiData",
      description: "Најдете тендери за медицинска опрема, лекови и здравствени услуги во Македонија.",
      url: "https://www.nabavkidata.com/medicina",
    },
    alternates: {
      canonical: "https://www.nabavkidata.com/medicina",
    },
  };
}

export default function MedicinaPage() {
  return (
    <div className="min-h-screen bg-background">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebPage",
            name: "Тендери за Медицина и Здравство — NabavkiData",
            description: "Следете тендери за медицинска опрема, лекови и здравствени услуги во Македонија.",
            url: "https://www.nabavkidata.com/medicina",
            breadcrumb: {
              "@type": "BreadcrumbList",
              itemListElement: [
                { "@type": "ListItem", position: 1, name: "Почетна", item: "https://www.nabavkidata.com" },
                { "@type": "ListItem", position: 2, name: "Медицина" },
              ],
            },
          }),
        }}
      />

      <div className="container mx-auto px-4 py-12 max-w-5xl">
        {/* Hero Section */}
        <div className="text-center mb-16">
          <span className="inline-block px-3 py-1 rounded-full text-sm font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300 mb-4">
            Медицина и Здравство
          </span>
          <h1 className="text-4xl md:text-5xl font-bold mb-6 text-foreground">
            Тендери за медицина и здравство
          </h1>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto leading-relaxed">
            Здравствениот сектор е еден од најрегулираните и највредните сектори во јавните набавки.
            NabavkiData ви помага да ги следите тендерите за лекови, медицинска опрема,
            лабораториски материјали и здравствени услуги.
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-16">
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">8,000+</div>
            <div className="text-sm text-muted-foreground">медицински тендери</div>
          </div>
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">500+</div>
            <div className="text-sm text-muted-foreground">здравствени установи</div>
          </div>
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">12+ млрд</div>
            <div className="text-sm text-muted-foreground">МКД вкупна вредност</div>
          </div>
          <div className="text-center p-6 rounded-xl bg-card border">
            <div className="text-3xl font-bold text-primary mb-1">800+</div>
            <div className="text-sm text-muted-foreground">добавувачи</div>
          </div>
        </div>

        {/* Sector Description */}
        <div className="grid md:grid-cols-2 gap-8 mb-16">
          <div>
            <h2 className="text-2xl font-bold mb-4 text-foreground">Зошто NabavkiData за медицински компании?</h2>
            <div className="space-y-4 text-muted-foreground">
              <p>
                Здравствениот сектор вклучува набавка на лекови, медицински средства,
                дијагностичка опрема, лабораториски реагенси, болнички мебел,
                стерилизациска опрема и многу повеќе. Болниците, клиниките и Фондот
                за здравствено осигурување се меѓу најголемите нарачатели.
              </p>
              <p>
                NabavkiData автоматски ги следи сите медицински тендери и ви дава
                увид во ценовните трендови. Дознајте по колку болниците купувале
                одреден лек или апарат во минатото — и калкулирајте конкурентна понуда.
              </p>
              <p>
                Со аларми по ATC код, генеричко име на лек или тип на опрема,
                никогаш нема да пропуштите тендер од вашата област.
              </p>
            </div>
          </div>
          <div>
            <h2 className="text-2xl font-bold mb-4 text-foreground">Клучни CPV категории</h2>
            <div className="space-y-3">
              {[
                { code: "33000000", name: "Медицински апарати, фармацевтски и производи за лична нега", desc: "Главна медицинска категорија" },
                { code: "33100000", name: "Медицински апарати", desc: "Дијагностичка и терапевтска опрема" },
                { code: "33600000", name: "Фармацевтски производи", desc: "Лекови, вакцини, инфузии" },
                { code: "33140000", name: "Медицински потрошен материјал", desc: "Ракавици, шприцови, завои, маски" },
                { code: "33190000", name: "Разни медицински апарати и производи", desc: "Специјализирана опрема" },
                { code: "33690000", name: "Разни медицински производи", desc: "Дезинфекциски средства, реагенси" },
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
              <div className="w-10 h-10 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center mb-4">
                <svg className="w-5 h-5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </div>
              <h3 className="font-semibold text-lg mb-2 text-foreground">Следење на лотови</h3>
              <p className="text-sm text-muted-foreground">
                Медицинските тендери често имаат десетици лотови. NabavkiData ги извлекува
                и анализира сите ставки од тендерската документација.
              </p>
            </div>
            <div className="p-6 rounded-xl bg-card border">
              <div className="w-10 h-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-4">
                <svg className="w-5 h-5 text-blue-600 dark:text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="font-semibold text-lg mb-2 text-foreground">Ценовна историја</h3>
              <p className="text-sm text-muted-foreground">
                Споредете цени на лекови и опрема низ различни тендери и години.
                Дознајте дали цената на одреден производ расте или паѓа.
              </p>
            </div>
            <div className="p-6 rounded-xl bg-card border">
              <div className="w-10 h-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
                <svg className="w-5 h-5 text-red-600 dark:text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <h3 className="font-semibold text-lg mb-2 text-foreground">Детекција на ризик</h3>
              <p className="text-sm text-muted-foreground">
                AI анализа за необично високи цени, единечни понудувачи
                или сомнителни модели во здравствените набавки.
              </p>
            </div>
          </div>
        </div>

        {/* CTA */}
        <div className="text-center py-12 px-6 rounded-2xl bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-950/20 dark:to-teal-950/20 border">
          <h2 className="text-2xl md:text-3xl font-bold mb-4 text-foreground">
            Не пропуштајте медицински тендери
          </h2>
          <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
            Регистрацијата е бесплатна. Поставете аларми за вашите производи
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
              href="/categories/33000000"
              className="inline-flex items-center justify-center px-6 py-3 rounded-lg border font-medium hover:bg-muted transition-colors text-foreground"
            >
              Прегледај медицински тендери
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
