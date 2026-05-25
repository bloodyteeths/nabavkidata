import { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check, X, ArrowRight, Zap, Search, Bell, BarChart3, Brain, Globe, Shield, Clock } from "lucide-react";

export const metadata: Metadata = {
  title: "NabavkiData vs TenderWatch и други алтернативи | NabavkiData",
  description: "Споредете ги NabavkiData со TenderWatch, TenderInfo и други платформи за следење тендери. NabavkiData е единствената MK-фокусирана платформа со AI анализа.",
  openGraph: {
    title: "NabavkiData vs TenderWatch — Споредба на платформи за тендери",
    description: "Зошто NabavkiData е подобар избор за македонскиот пазар на јавни набавки.",
  },
  alternates: {
    canonical: "https://www.nabavkidata.com/alternative/tenderwatch",
  },
};

const FEATURES = [
  { name: "Фокус на МК пазар", nabavki: true, other: false, icon: Globe },
  { name: "Македонски јазик", nabavki: true, other: false, icon: Globe },
  { name: "AI анализа на тендери", nabavki: true, other: false, icon: Brain },
  { name: "Билингвално пребарување", nabavki: true, other: false, icon: Search },
  { name: "Аларми за нови тендери", nabavki: true, other: true, icon: Bell },
  { name: "Анализа на конкуренти", nabavki: true, other: false, icon: BarChart3 },
  { name: "Ценовна интелигенција", nabavki: true, other: false, icon: BarChart3 },
  { name: "Детекција на корупција", nabavki: true, other: false, icon: Shield },
  { name: "Профили на добавувачи", nabavki: true, other: true, icon: BarChart3 },
  { name: "Историски податоци (2008+)", nabavki: true, other: false, icon: Clock },
  { name: "Бесплатен план", nabavki: true, other: false, icon: Zap },
  { name: "EU/Меѓународни тендери", nabavki: false, other: true, icon: Globe },
];

export default function TenderWatchAlternativePage() {
  return (
    <div className="min-h-screen bg-background">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebPage",
            name: "NabavkiData vs TenderWatch",
            description: "Споредба на NabavkiData со TenderWatch и други платформи за следење тендери",
            url: "https://www.nabavkidata.com/alternative/tenderwatch",
            breadcrumb: {
              "@type": "BreadcrumbList",
              itemListElement: [
                { "@type": "ListItem", position: 1, name: "Почетна", item: "https://www.nabavkidata.com" },
                { "@type": "ListItem", position: 2, name: "NabavkiData vs TenderWatch" },
              ],
            },
          }),
        }}
      />

      <div className="container mx-auto px-4 py-12 max-w-5xl">
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">Споредба</Badge>
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            NabavkiData vs TenderWatch
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Меѓународните платформи покриваат многу земји, но немаат длабочина за македонскиот пазар.
            NabavkiData е специјализирана за МК јавни набавки.
          </p>
        </div>

        <Card className="mb-8">
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-4 font-semibold">Функционалност</th>
                    <th className="text-center p-4 font-semibold text-primary">NabavkiData</th>
                    <th className="text-center p-4 font-semibold text-muted-foreground">TenderWatch / Други</th>
                  </tr>
                </thead>
                <tbody>
                  {FEATURES.map((f) => (
                    <tr key={f.name} className="border-b last:border-0 hover:bg-muted/50">
                      <td className="p-4 flex items-center gap-2">
                        <f.icon className="h-4 w-4 text-muted-foreground" />
                        {f.name}
                      </td>
                      <td className="p-4 text-center">
                        {f.nabavki ? (
                          <Check className="h-5 w-5 text-green-500 mx-auto" />
                        ) : (
                          <X className="h-5 w-5 text-red-400 mx-auto" />
                        )}
                      </td>
                      <td className="p-4 text-center">
                        {f.other ? (
                          <Check className="h-5 w-5 text-green-500 mx-auto" />
                        ) : (
                          <X className="h-5 w-5 text-red-400 mx-auto" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <div className="grid md:grid-cols-3 gap-6 mb-12">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Длабочина на податоци</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>290,000+ тендери, 18,900+ добавувачи, 3,000+ институции — сè од 2008 до денес. Меѓународните платформи обично имаат само дел од овие податоци.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">AI на македонски</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>AI анализа, резимеа и препораки на македонски јазик. Билингвално пребарување — пишувајте на латиница, наоѓајте на кирилица.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Достапна цена</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>Започнете бесплатно. Стартер план од 1,990 МКД/месец — значително поевтино од меѓународните платформи кои чинат 100-500€/месец.</p>
            </CardContent>
          </Card>
        </div>

        <div className="text-center">
          <h2 className="text-2xl font-bold mb-4">Пробајте бесплатно</h2>
          <p className="text-muted-foreground mb-6">Регистрацијата е бесплатна. Споредете сами.</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/auth/register">
              <Button size="lg" className="w-full sm:w-auto">
                Регистрирајте се бесплатно
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/tenders">
              <Button size="lg" variant="outline" className="w-full sm:w-auto">
                Прегледај тендери
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
