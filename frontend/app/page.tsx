import Navbar from "@/components/landing/Navbar";
import HeroSection from "@/components/landing/HeroSection";
import FeaturesSection from "@/components/landing/FeaturesSection";
import ComparisonSection from "@/components/landing/ComparisonSection";
import PricingSection from "@/components/landing/PricingSection";

export default function LandingPage() {
    return (
        <main className="min-h-screen bg-background text-foreground overflow-x-hidden">
            <Navbar />
            <HeroSection />
            <FeaturesSection />
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
