import { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Check, X, ArrowRight, Zap, Search, Bell, BarChart3, FileText, Brain, Shield, Database } from "lucide-react";

export const metadata: Metadata = {
  title: "NabavkiData vs Open Finance — Споредба | NabavkiData",
  description: "Споредете ги NabavkiData и Open Finance. Open Finance нуди отворени податоци, NabavkiData дава AI анализа на тендери, аларми, ценовна интелигенција и профили на добавувачи.",
  openGraph: {
    title: "NabavkiData vs Open Finance — Споредба на платформи за јавни податоци",
    description: "Open Finance е портал за отворени податоци. NabavkiData е специјализирана за тендерска интелигенција.",
  },
  alternates: {
    canonical: "https://www.nabavkidata.com/alternative/open-finance",
  },
};

const FEATURES = [
  { name: "Отворени буџетски податоци", nabavki: false, other: true, icon: Database },
  { name: "Детални податоци за тендери", nabavki: true, other: false, icon: FileText },
  { name: "AI анализа на тендери", nabavki: true, other: false, icon: Brain },
  { name: "Аларми за нови тендери", nabavki: true, other: false, icon: Bell },
  { name: "Ценовна интелигенција", nabavki: true, other: false, icon: BarChart3 },
  { name: "Анализа на конкуренти", nabavki: true, other: false, icon: BarChart3 },
  { name: "Профили на добавувачи", nabavki: true, other: false, icon: Search },
  { name: "Визуелизации и графикони", nabavki: true, other: true, icon: BarChart3 },
  { name: "Детекција на корупција", nabavki: true, other: false, icon: Shield },
  { name: "Извоз на податоци", nabavki: true, other: true, icon: Database },
  { name: "Историски тендерски податоци (2008+)", nabavki: true, other: false, icon: FileText },
  { name: "Билингвално пребарување", nabavki: true, other: false, icon: Search },
  { name: "API пристап", nabavki: true, other: true, icon: Zap },
];

export default function OpenFinanceAlternativePage() {
  return (
    <div className="min-h-screen bg-background">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "WebPage",
            name: "NabavkiData vs Open Finance — Споредба",
            description: "Споредба на NabavkiData и Open Finance платформите за јавни податоци",
            url: "https://www.nabavkidata.com/alternative/open-finance",
            breadcrumb: {
              "@type": "BreadcrumbList",
              itemListElement: [
                { "@type": "ListItem", position: 1, name: "Почетна", item: "https://www.nabavkidata.com" },
                { "@type": "ListItem", position: 2, name: "NabavkiData vs Open Finance" },
              ],
            },
          }),
        }}
      />

      <div className="container mx-auto px-4 py-12 max-w-5xl">
        <div className="text-center mb-12">
          <Badge variant="secondary" className="mb-4">Споредба</Badge>
          <h1 className="text-4xl md:text-5xl font-bold mb-4">
            NabavkiData vs Open Finance
          </h1>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
            Open Finance е портал за отворени финансиски податоци. NabavkiData е специјализирана
            платформа за тендерска интелигенција — AI анализа, аларми и профили на добавувачи.
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
                    <th className="text-center p-4 font-semibold text-muted-foreground">Open Finance</th>
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
              <CardTitle className="text-lg">Различен фокус</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>Open Finance е портал за општа финансиска транспарентност — буџети, расходи, приходи. NabavkiData е фокусирана исклучиво на јавни набавки и тендери, со длабока анализа на секој тендер.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Алатка за понудувачи</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>Ако сте компанија што учествува на тендери, NabavkiData ви дава конкурентска предност: AI аларми, ценовна анализа, профили на конкуренти и историски податоци за победнички понуди.</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Комплементарни платформи</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              <p>Двете платформи може да се користат заедно: Open Finance за општа буџетска слика, NabavkiData за детална тендерска интелигенција и активно учество на тендери.</p>
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
