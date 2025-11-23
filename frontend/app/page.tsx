import { Metadata } from "next";
import Navbar from "@/components/landing/Navbar";
import HeroSection from "@/components/landing/HeroSection";
import FeaturesSection from "@/components/landing/FeaturesSection";
import TrustSection from "@/components/landing/TrustSection";
import ComparisonSection from "@/components/landing/ComparisonSection";
import PricingSection from "@/components/landing/PricingSection";

export const metadata: Metadata = {
    title: "Почетна",
    description: "Најсовремена платформа за анализа на јавни набавки во Македонија. AI-базирани препораки, следење на конкуренти и детални инсајти.",
};

export default function LandingPage() {
    return (
        <main className="min-h-screen bg-background text-foreground overflow-x-hidden">
            <Navbar />
            <HeroSection />
            <FeaturesSection />
            <TrustSection />
            <ComparisonSection />
            <PricingSection />

            {/* Footer */}
            <footer className="py-12 border-t border-white/10 bg-black/20">
                <div className="container px-4 md:px-6 text-center text-gray-400">
                    <p>&copy; 2024 Nabavkidata. Сите права се задржани.</p>
                </div>
            </footer>
        </main>
    );
}
