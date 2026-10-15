import { Metadata } from "next";
import dynamic from "next/dynamic";
import Navbar from "@/components/landing/Navbar";
import { ServiceFooter } from "@/components/service/ServiceCTA";

const ServicePricing = dynamic(() => import("@/components/service/ServicePricing"), {
  loading: () => <div className="min-h-[700px]" />,
});
const ServiceFAQ = dynamic(() => import("@/components/service/ServiceFAQ"), {
  loading: () => <div className="min-h-[600px]" />,
});
const ServiceCTA = dynamic(() => import("@/components/service/ServiceCTA"), {
  loading: () => <div className="min-h-[400px]" />,
});

export const metadata: Metadata = {
  title: "Цени за подготовка на понуди | NabavkiData",
  description:
    "Подготовка на понуда од 30.000 МКД без ДДВ, договорено однапред. 5% од вредноста за првата година само ако победите. Следењето на тендери и известувањата се вклучени за клиентите. Плаќање со картичка или со фактура, без претплата.",
  alternates: {
    canonical: "/pricing",
  },
  openGraph: {
    title: "Цени за подготовка на понуди | NabavkiData",
    description:
      "Подготовка на понуда: од 30.000 МКД без ДДВ, со вклучено следење на тендери и анализи. Надомест за успех: 5% од вредноста за првата година, само ако победите.",
    url: "https://www.nabavkidata.com/pricing",
  },
};

function PricingJsonLd() {
  const service = {
    "@context": "https://schema.org",
    "@type": "Service",
    name: "Подготовка на понуди за јавни набавки",
    serviceType: "Подготовка на тендерски понуди",
    areaServed: "MK",
    provider: {
      "@type": "Organization",
      name: "Фактурино ДООЕЛ",
      email: "hello@nabavkidata.com",
      telephone: "+389 70 253 467",
      address: {
        "@type": "PostalAddress",
        streetAddress: "ул. Сараевска 37",
        postalCode: "1400",
        addressLocality: "Велес",
        addressCountry: "MK",
      },
    },
    offers: [
      {
        "@type": "Offer",
        name: "Подготовка на понуда",
        priceCurrency: "MKD",
        priceSpecification: {
          "@type": "PriceSpecification",
          minPrice: "30000",
          priceCurrency: "MKD",
        },
      },
    ],
  };

  const breadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Почетна", item: "https://www.nabavkidata.com" },
      { "@type": "ListItem", position: 2, name: "Цени" },
    ],
  };

  return (
    <>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(service) }} />
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumb) }} />
    </>
  );
}

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-background text-foreground overflow-x-hidden">
      <PricingJsonLd />
      <Navbar />
      <div className="pt-20">
        <ServicePricing />
        <ServiceFAQ />
        <ServiceCTA />
      </div>
      <ServiceFooter />
    </main>
  );
}
