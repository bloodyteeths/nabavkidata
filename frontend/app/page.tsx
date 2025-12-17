import { Metadata } from "next";
import Navbar from "@/components/landing/Navbar";
import HeroSection from "@/components/landing/HeroSection";
import ValuePropositionSection from "@/components/landing/ValuePropositionSection";
import HowItWorksSection from "@/components/landing/HowItWorksSection";
import FeaturesSection from "@/components/landing/FeaturesSection";
import TrustSection from "@/components/landing/TrustSection";
import ComparisonSection from "@/components/landing/ComparisonSection";
import PricingSection from "@/components/landing/PricingSection";
import SocialProofNotifications from "@/components/landing/SocialProofNotifications";

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
