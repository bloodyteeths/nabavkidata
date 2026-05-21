import { Metadata } from "next";
import dynamic from "next/dynamic";
import Navbar from "@/components/landing/Navbar";
import Link from "next/link";

const PricingSection = dynamic(() => import("@/components/landing/PricingSection"), {
  loading: () => <div className="min-h-[700px]" />,
});
const FAQSection = dynamic(() => import("@/components/landing/FAQSection"), {
  loading: () => <div className="min-h-[600px]" />,
});

export const metadata: Metadata = {
  title: "Цени и планови | NabavkiData",
  description:
    "Изберете го вистинскиот план за вашиот бизнис. Од бесплатен преглед до Enterprise — AI анализа на тендери, известувања, историски цени и конкурентска анализа.",
  openGraph: {
    title: "Цени и планови | NabavkiData",
    description:
      "Бесплатен план, Стартер (1,990 ден/мес), Про (5,990 ден/мес), Претпријатие (12,990 ден/мес). AI тендерска интелигенција за Македонија.",
    url: "https://nabavkidata.com/pricing",
  },
};

function PricingJsonLd() {
  const product = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: "NabavkiData - AI тендерска платформа",
    description: "AI-базирана платформа за анализа на јавни набавки во Македонија",
    offers: [
      { "@type": "Offer", name: "Бесплатен", price: "0", priceCurrency: "MKD" },
      { "@type": "Offer", name: "Стартер", price: "1990", priceCurrency: "MKD", billingIncrement: "P1M" },
      { "@type": "Offer", name: "Про", price: "5990", priceCurrency: "MKD", billingIncrement: "P1M" },
      { "@type": "Offer", name: "Претпријатие", price: "12990", priceCurrency: "MKD", billingIncrement: "P1M" },
    ],
  };

  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Почетна", item: "https://nabavkidata.com" },
      { "@type": "ListItem", position: 2, name: "Цени" },
    ],
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(product) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumb) }}
      />
    </>
  );
}

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-background text-foreground overflow-x-hidden">
      <PricingJsonLd />
      <Navbar />
      <div className="pt-20">
        <PricingSection />
        <FAQSection />
      </div>

      <footer className="py-12 border-t border-border bg-background/20">
        <div className="container px-4 md:px-6">
          <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-muted-foreground">
            <p className="text-sm">&copy; 2024 Nabavkidata. Сите права се задржани.</p>
            <nav className="flex gap-6 text-sm">
              <Link href="/privacy" className="hover:text-primary transition-colors">
                Политика за приватност
              </Link>
              <Link href="/terms" className="hover:text-primary transition-colors">
                Услови за користење
              </Link>
              <Link href="/contact" className="hover:text-primary transition-colors">
                Контакт
              </Link>
            </nav>
          </div>
        </div>
      </footer>
    </main>
  );
}
