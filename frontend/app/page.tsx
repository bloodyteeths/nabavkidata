import { Metadata } from "next";
import dynamic from "next/dynamic";
import Navbar from "@/components/landing/Navbar";
import HeroSection from "@/components/landing/HeroSection";

// Lazy load below-the-fold sections for better performance
const ValuePropositionSection = dynamic(() => import("@/components/landing/ValuePropositionSection"), {
    loading: () => <div className="min-h-[400px]" />
});
const HowItWorksSection = dynamic(() => import("@/components/landing/HowItWorksSection"), {
    loading: () => <div className="min-h-[600px]" />
});
const FeaturesSection = dynamic(() => import("@/components/landing/FeaturesSection"), {
    loading: () => <div className="min-h-[800px]" />
});
const TrustSection = dynamic(() => import("@/components/landing/TrustSection"), {
    loading: () => <div className="min-h-[500px]" />
});
const ComparisonSection = dynamic(() => import("@/components/landing/ComparisonSection"), {
    loading: () => <div className="min-h-[600px]" />
});
const PricingSection = dynamic(() => import("@/components/landing/PricingSection"), {
    loading: () => <div className="min-h-[700px]" />
});
const SocialProofNotifications = dynamic(() => import("@/components/landing/SocialProofNotifications"), {
    ssr: false
});
const FAQSection = dynamic(() => import("@/components/landing/FAQSection"), {
    loading: () => <div className="min-h-[600px]" />
});
const TestimonialsSection = dynamic(() => import("@/components/landing/TestimonialsSection"), {
    loading: () => <div className="min-h-[600px]" />
});

export const metadata: Metadata = {
    title: "Почетна",
    description: "Најсовремена платформа за анализа на јавни набавки во Македонија. AI-базирани препораки, следење на конкуренти и детални инсајти.",
};

export default function LandingPage() {
    return (
        <main className="min-h-screen bg-background text-foreground overflow-x-hidden">
            <Navbar />
            <HeroSection />
            <ValuePropositionSection />
            <HowItWorksSection />
            <FeaturesSection />
            <TrustSection />
            <ComparisonSection />
            <PricingSection />
            <TestimonialsSection />
            <FAQSection />
            <SocialProofNotifications />

            {/* Footer */}
            <footer className="py-12 border-t border-white/10 bg-black/20">
                <div className="container px-4 md:px-6">
                    <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-gray-400">
                        <p className="text-sm">&copy; 2024 Nabavkidata. Сите права се задржани.</p>
                        <nav className="flex gap-6 text-sm">
                            <a
                                href="/privacy"
                                className="hover:text-primary transition-colors"
                            >
                                Политика за приватност
                            </a>
                            <a
                                href="/terms"
                                className="hover:text-primary transition-colors"
                            >
                                Услови за користење
                            </a>
                            <a
                                href="mailto:support@nabavkidata.com"
                                className="hover:text-primary transition-colors"
                            >
                                Контакт
                            </a>
                        </nav>
                    </div>
                </div>
            </footer>
        </main>
    );
}
