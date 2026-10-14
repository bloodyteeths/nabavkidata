import { Metadata } from "next";
import dynamic from "next/dynamic";
import Navbar from "@/components/landing/Navbar";
import ServiceHero from "@/components/service/ServiceHero";
import { ServiceFooter } from "@/components/service/ServiceCTA";

// Lazy load below-the-fold sections for better performance
const ServiceHowItWorks = dynamic(() => import("@/components/service/ServiceHowItWorks"), {
    loading: () => <div className="min-h-[500px]" />,
});
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
    title: "Ние ја пишуваме вашата понуда за тендер | NabavkiData",
    description:
        "Подготовка на понуди за јавни набавки на е-набавки. Бесплатна проценка, подготовка на понуда од 30.000 МКД и 5% надомест за успех само ако победите. Следењето на тендери и известувањата се вклучени за клиентите.",
    alternates: {
        canonical: "/",
    },
    openGraph: {
        title: "Ние ја пишуваме вашата понуда за тендер | NabavkiData",
        description:
            "Нашиот тим ги следи тендерите и ја подготвува целата понуда. Вие ја прегледувате, потпишувате и поднесувате на е-набавки.",
        url: "https://www.nabavkidata.com",
    },
};

export default function LandingPage() {
    return (
        <main className="min-h-screen bg-background text-foreground overflow-x-hidden">
            <Navbar />
            <ServiceHero />
            <ServiceHowItWorks />
            <ServicePricing />
            <ServiceFAQ />
            <ServiceCTA />
            <ServiceFooter />
        </main>
    );
}
