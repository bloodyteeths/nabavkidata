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
        "Ја подготвуваме целата понуда за јавни набавки од документацијата на е-набавки: услови за способност, техничка и финансиска понуда, изјави. Од 30.000 МКД по понуда без ДДВ и 5% од вредноста за првата година само ако победите. Следењето на тендери и анализите се вклучени за клиентите.",
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
