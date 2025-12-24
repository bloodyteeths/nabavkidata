import { Metadata } from "next";
import NavbarSr from "@/components/landing/sr/NavbarSr";
import HeroSectionSr from "@/components/landing/sr/HeroSectionSr";
import HowItWorksSectionSr from "@/components/landing/sr/HowItWorksSectionSr";
import FeaturesSectionSr from "@/components/landing/sr/FeaturesSectionSr";
import TrustSectionSr from "@/components/landing/sr/TrustSectionSr";
import ComparisonSectionSr from "@/components/landing/sr/ComparisonSectionSr";
import PricingSectionSr from "@/components/landing/sr/PricingSectionSr";
import SocialProofNotificationsSr from "@/components/landing/sr/SocialProofNotificationsSr";

export const metadata: Metadata = {
    title: "Početna | Nabavkidata - AI Platforma za Javne Nabavke",
    description: "Najsavremenija platforma za analizu javnih nabavki u Makedoniji. AI-bazirane preporuke, praćenje konkurencije i detaljni uvidi.",
};

export default function LandingPageSr() {
    return (
        <main className="min-h-screen bg-background text-foreground overflow-x-hidden">
            <NavbarSr />
            <HeroSectionSr />
            <HowItWorksSectionSr />
            <FeaturesSectionSr />
            <TrustSectionSr />
            <ComparisonSectionSr />
            <PricingSectionSr />
            <SocialProofNotificationsSr />

            {/* Footer */}
            <footer className="py-12 border-t border-white/10 bg-black/20">
                <div className="container px-4 md:px-6">
                    <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-gray-400">
                        <p className="text-sm">&copy; 2024 Nabavkidata. Sva prava zadržana.</p>
                        <nav className="flex gap-6 text-sm">
                            <a
                                href="/privacy"
                                className="hover:text-primary transition-colors"
                            >
                                Politika privatnosti
                            </a>
                            <a
                                href="/terms"
                                className="hover:text-primary transition-colors"
                            >
                                Uslovi korišćenja
                            </a>
                            <a
                                href="/contact"
                                className="hover:text-primary transition-colors"
                            >
                                Kontakt
                            </a>
                        </nav>
                    </div>
                </div>
            </footer>
        </main>
    );
}
