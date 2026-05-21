"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Search, FileText, Building2, PoundSterling } from "lucide-react";

const stats = [
    { icon: FileText, value: "170,000+", label: "тендери" },
    { icon: Building2, value: "70,000+", label: "документи анализирани" },
    { icon: PoundSterling, value: "17 години", label: "историја на цени" },
];

export default function HeroSection() {
    const [searchValue, setSearchValue] = useState("");

    const handleSearch = () => {
        if (searchValue.trim()) {
            window.location.href = `/tenders?search=${encodeURIComponent(searchValue)}`;
        }
    };

    return (
        <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20">
            {/* Background */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/20 via-background to-background" />
            <div className="absolute top-0 left-0 w-full h-full bg-[url('/grid.svg')] bg-center [mask-image:linear-gradient(180deg,white,rgba(255,255,255,0))]" />

            <div className="container relative z-10 px-4 md:px-6 text-center">
                {/* Authority badge */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-foreground/5 border border-border mb-8"
                >
                    <span className="text-sm text-muted-foreground">
                        Податоци од <strong className="text-foreground">е-набавки.гов.мк</strong> — официјален извор
                    </span>
                </motion.div>

                <motion.h1
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className="text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6"
                >
                    <span className="text-foreground">Видете ги </span>
                    <span className="text-gradient">победничките цени</span>
                    <br />
                    <span className="text-foreground">пред да понудите</span>
                </motion.h1>

                <motion.p
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10"
                >
                    Престанете да погодувате. AI анализира секој тендер — минати цени,
                    историја на конкуренти, барања — за да понудите правилно и да победите.
                    <span className="block mt-2 text-sm text-foreground/60">Работи за 2 минути. Нови тендери на секои 3 часа.</span>
                </motion.p>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                    className="flex flex-col items-center justify-center gap-4"
                >
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link href="/auth/register" className="flex flex-col items-center">
                            <Button size="lg" className="h-14 px-10 text-lg bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_30px_rgba(124,58,237,0.5)] hover:shadow-[0_0_50px_rgba(124,58,237,0.7)] transition-all duration-300" aria-label="Започни бесплатна регистрација">
                                Видете ги цените <ArrowRight className="ml-2 h-5 w-5" />
                            </Button>
                            <span className="text-xs text-muted-foreground mt-2">Бесплатен план — не е потребна картичка</span>
                        </Link>
                    </div>

                    {/* Search hook */}
                    <div className="mt-6 w-full max-w-lg mx-auto">
                        <p className="text-sm text-muted-foreground mb-2">Пребарајте тендери:</p>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                placeholder='Пробајте "медицинска опрема" или "градежни работи"'
                                aria-label="Пребарајте јавни набавки"
                                className="flex-1 h-12 rounded-lg bg-foreground/5 border border-border px-4 text-foreground placeholder:text-gray-500 focus:outline-none focus:border-primary/50 transition-colors"
                                value={searchValue}
                                onChange={(e) => setSearchValue(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") handleSearch();
                                }}
                            />
                            <Button
                                className="h-12 px-6 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30"
                                aria-label="Пребарај"
                                onClick={handleSearch}
                            >
                                <Search className="w-5 h-5" />
                            </Button>
                        </div>
                    </div>

                    {/* Real stats */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.5 }}
                        className="flex flex-wrap items-center justify-center gap-6 md:gap-10 mt-8"
                    >
                        {stats.map((stat, index) => {
                            const Icon = stat.icon;
                            return (
                                <div key={index} className="flex items-center gap-2">
                                    <Icon className="w-4 h-4 text-primary" />
                                    <div className="text-left">
                                        <span className="text-lg font-bold text-foreground notranslate">{stat.value}</span>
                                        <span className="text-xs text-muted-foreground ml-1">{stat.label}</span>
                                    </div>
                                </div>
                            );
                        })}
                    </motion.div>
                </motion.div>
            </div>
        </section>
    );
}
