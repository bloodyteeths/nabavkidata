import { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check, X, ArrowRight, Zap, Search, Bell, BarChart3, FileText, Brain } from "lucide-react";

export const metadata: Metadata = {
  title: "NabavkiData vs ЕСЈН (е-Набавки) — Споредба | NabavkiData",
  description: "Споредете ги NabavkiData и ЕСЈН (е-Набавки). NabavkiData нуди AI анализа, аларми, ценовна интелигенција и анализа на конкуренти — сè што ЕСЈН го нема.",
  openGraph: {
    title: "NabavkiData vs ЕСЈН — Споредба на платформи за јавни набавки",
    description: "Зошто компаниите го избираат NabavkiData наместо само ЕСЈН за следење на тендери.",
  },
  alternates: {
    canonical: "https://nabavkidata.com/alternative/esjn",
  },
};

const FEATURES = [
  { name: "Пребарување тендери", nabavki: true, esjn: true, icon: Search },
  { name: "AI анализа на тендери", nabavki: true, esjn: false, icon: Brain },
  { name: "Аларми за нови тендери", nabavki: true, esjn: false, icon: Bell },
  { name: "Ценовна интелигенција", nabavki: true, esjn: false, icon: BarChart3 },
  { name: "Анализа на конкуренти", nabavki: true, esjn: false, icon: BarChart3 },
  { name: "AI извлекување на документи", nabavki: true, esjn: false, icon: FileText },
  { name: "Анализа на ризик", nabavki: true, esjn: false, icon: Zap },
  { name: "Профили на добавувачи", nabavki: true, esjn: false, icon: BarChart3 },
  { name: "Профили на институции", nabavki: true, esjn: true, icon: BarChart3 },
  { name: "Историски податоци (2008+)", nabavki: true, esjn: true, icon: FileText },
  { name: "Билингвално пребарување (латиница/кирилица)", nabavki: true, esjn: false, icon: Search },
  { name: "API пристап", nabavki: true, esjn: false, icon: Zap },
];

export default function EsjnAlternativePage() {
  return (
    <div className="min-h-screen bg-background">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebPage",
            name: "NabavkiData vs ЕСЈН — Споредба",
            description: "Споредба на NabavkiData и ЕСЈН платформите за јавни набавки",
            url: "https://nabavkidata.com/alternative/esjn",
            breadcrumb: {
              "@type": "BreadcrumbList",
              itemListElement: [
                { "@type": "ListItem", position: 1, name: "Почетна", item: "https://nabavkidata.com" },
                { "@type": "ListItem", position: 2, name: "NabavkiData vs ЕСЈН" },
              ],
            },
          }),
        }}
      />

      <div className="container mx-auto px-4 py-12 max-w-5xl">
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">Споредба</Badge>
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            NabavkiData vs ЕСЈН
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            ЕСЈН (е-Набавки) е официјалната платформа. NabavkiData е интелигентен слој над неа —
            AI анализа, аларми и увиди кои ЕСЈН не ги нуди.
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
                    <th className="text-center p-4 font-semibold text-muted-foreground">ЕСЈН</th>
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
                        {f.esjn ? (
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
              <CardTitle>Зошто ЕСЈН не е доволен?</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              <p>ЕСЈН е задолжителна платформа за објавување тендери — но таа е направена за нарачатели, не за понудувачи.</p>
              <p>Нема аларми кога ќе се појави тендер во вашата област. Нема анализа на конкуренти. Нема AI што ќе ви каже дали да учествувате.</p>
              <p>NabavkiData ги собира сите тендери од ЕСЈН и додава интелигенција — за да не пропуштите можности и да победите почесто.</p>
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
