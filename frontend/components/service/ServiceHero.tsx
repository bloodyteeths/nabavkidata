"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Search, FileText, Building2, History } from "lucide-react";

const stats = [
    { icon: FileText, value: "170.000+", label: "тендери" },
    { icon: Building2, value: "70.000+", label: "документи анализирани" },
    { icon: History, value: "од 2008", label: "историја на цени" },
];

export default function ServiceHero() {
    const [searchValue, setSearchValue] = useState("");

    const handleSearch = () => {
        const q = searchValue.trim();
        if (q) {
            window.location.href = `/tenders?search=${encodeURIComponent(q)}`;
        }
    };

    return (
        <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20">
            {/* Background */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/20 via-background to-background" />
            <div className="absolute top-0 left-0 w-full h-full bg-[url('/grid.svg')] bg-center [mask-image:linear-gradient(180deg,white,rgba(255,255,255,0))]" />

            <div className="container relative z-10 px-4 md:px-6 text-center">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-foreground/5 border border-border mb-8"
                >
                    <span className="text-sm text-muted-foreground">
                        Подготовка на понуди за јавни набавки на <strong className="text-foreground">е-набавки (e-nabavki.gov.mk)</strong>
                    </span>
                </motion.div>

                <motion.h1
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className="text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6"
                >
                    <span className="text-foreground">Ние ја пишуваме понудата.</span>
                    <br />
                    <span className="text-gradient">Вие го добивате тендерот.</span>
                </motion.h1>

                <motion.p
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10"
                >
                    Подготовката на понуда за јавна набавка одзема денови. Нашиот тим ги следи
                    тендерите наместо вас, ги наоѓа оние што одговараат на вашата фирма и ја
                    подготвува целата понуда според тендерската документација. Вие ја прегледувате,
                    потпишувате и поднесувате.
                </motion.p>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                    className="flex flex-col items-center justify-center gap-4"
                >
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link href="/usluga">
                            <Button
                                size="lg"
                                className="h-14 px-10 text-lg bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_30px_rgba(124,58,237,0.5)] hover:shadow-[0_0_50px_rgba(124,58,237,0.7)] transition-all duration-300"
                            >
                                Бесплатна проценка <ArrowRight className="ml-2 h-5 w-5" />
                            </Button>
                        </Link>
                        <Link href="/tenders">
                            <Button
                                size="lg"
                                variant="outline"
                                className="h-14 px-8 text-lg border-border text-foreground hover:bg-foreground/10"
                            >
                                Пребарајте тендери
                            </Button>
                        </Link>
                    </div>
                    <p className="text-sm text-muted-foreground">
                        Следењето на тендери е бесплатно. Надомест за успех плаќате само ако победите.
                    </p>

                    {/* Search hook */}
                    <div className="mt-6 w-full max-w-lg mx-auto">
                        <p className="text-sm text-muted-foreground mb-2">Пребарајте тендери:</p>
                        <form
                            className="flex gap-2"
                            onSubmit={(e) => {
                                e.preventDefault();
                                handleSearch();
                            }}
                        >
                            <input
                                type="text"
                                value={searchValue}
                                onChange={(e) => setSearchValue(e.target.value)}
                                placeholder="На пр. „медицинска опрема“ или „градежни работи“"
                                aria-label="Пребарајте јавни набавки"
                                className="flex-1 min-w-0 h-12 rounded-lg bg-foreground/5 border border-border px-4 text-foreground placeholder:text-gray-500 focus:outline-none focus:border-primary/50 transition-colors"
                            />
                            <Button
                                type="submit"
                                className="h-12 px-6 bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30"
                                aria-label="Пребарај"
                            >
                                <Search className="w-5 h-5" />
                            </Button>
                        </form>
                    </div>

                    {/* Real stats */}
                    <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.5 }}
                        className="flex flex-wrap items-center justify-center gap-6 md:gap-10 mt-8"
                    >
                        {stats.map((stat) => {
                            const Icon = stat.icon;
                            return (
                                <div key={stat.label} className="flex items-center gap-2">
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
