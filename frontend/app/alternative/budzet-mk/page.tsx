import { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check, X, ArrowRight, Zap, Search, Bell, BarChart3, FileText, Brain, Shield, Globe } from "lucide-react";

export const metadata: Metadata = {
  title: "NabavkiData vs Буџет.мк — Споредба | NabavkiData",
  description: "Споредете ги NabavkiData и Буџет.мк. Буџет.мк покажува буџетски расходи, NabavkiData дава длабока анализа на тендери со AI, аларми и ценовна интелигенција.",
  openGraph: {
    title: "NabavkiData vs Буџет.мк — Споредба на платформи за јавни финансии",
    description: "Буџет.мк покажува каде одат парите. NabavkiData покажува како се трошат — преку тендери.",
  },
  alternates: {
    canonical: "https://www.nabavkidata.com/alternative/budzet-mk",
  },
};

const FEATURES = [
  { name: "Буџетски расходи по институции", nabavki: false, other: true, icon: BarChart3 },
  { name: "Детални податоци за тендери", nabavki: true, other: false, icon: FileText },
  { name: "AI анализа на тендери", nabavki: true, other: false, icon: Brain },
  { name: "Аларми за нови тендери", nabavki: true, other: false, icon: Bell },
  { name: "Ценовна интелигенција", nabavki: true, other: false, icon: BarChart3 },
  { name: "Анализа на конкуренти", nabavki: true, other: false, icon: BarChart3 },
  { name: "Профили на добавувачи", nabavki: true, other: false, icon: Search },
  { name: "Профили на институции", nabavki: true, other: true, icon: Globe },
  { name: "Детекција на корупција", nabavki: true, other: false, icon: Shield },
  { name: "Историски тендерски податоци (2008+)", nabavki: true, other: false, icon: FileText },
  { name: "Визуелизација на буџет", nabavki: false, other: true, icon: BarChart3 },
  { name: "Билингвално пребарување", nabavki: true, other: false, icon: Search },
  { name: "API пристап", nabavki: true, other: false, icon: Zap },
];

export default function BudzetMkAlternativePage() {
  return (
    <div className="min-h-screen bg-background">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebPage",
            name: "NabavkiData vs Буџет.мк — Споредба",
            description: "Споредба на NabavkiData и Буџет.мк платформите за јавни финансии и набавки",
            url: "https://www.nabavkidata.com/alternative/budzet-mk",
            breadcrumb: {
              "@type": "BreadcrumbList",
              itemListElement: [
                { "@type": "ListItem", position: 1, name: "Почетна", item: "https://www.nabavkidata.com" },
                { "@type": "ListItem", position: 2, name: "NabavkiData vs Буџет.мк" },
              ],
            },
          }),
        }}
      />

      <div className="container mx-auto px-4 py-12 max-w-5xl">
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">Споредба</Badge>
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            NabavkiData vs Буџет.мк
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Буџет.мк покажува каде одат јавните пари. NabavkiData покажува <strong>како</strong> се
            трошат — преку детална анализа на тендери, добавувачи и цени.
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
                    <th className="text-center p-4 font-semibold text-muted-foreground">Буџет.мк</th>
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

        <div className="grid md:grid-cols-2 gap-6 mb-12">
          <Card>
            <CardHeader>
              <CardTitle>Буџет.мк е за транспарентност</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>Буџет.мк е одличен проект за граѓани и новинари — покажува како се распределуваат буџетските средства по институции и категории.</p>
              <p>Но ако сте компанија што учествува на тендери, Буџет.мк не ви дава доволно: нема детални податоци за тендери, нема аларми, нема анализа на конкуренти.</p>
              <p>NabavkiData е направена за понудувачи — за да ги најдете тендерите, да ги анализирате и да победите.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>NabavkiData во бројки</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Тендери во база</span>
                <span className="font-bold text-lg">290,000+</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Добавувачи</span>
                <span className="font-bold text-lg">18,900+</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Институции</span>
                <span className="font-bold text-lg">3,000+</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">CPV категории</span>
                <span className="font-bold text-lg">5,275</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-muted-foreground">Историја од</span>
                <span className="font-bold text-lg">2008</span>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="text-center">
          <h2 className="text-2xl font-bold mb-4">Започнете бесплатно</h2>
          <p className="text-muted-foreground mb-6">Регистрацијата е бесплатна. Погледнете што NabavkiData може да направи за вашиот бизнис.</p>
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
