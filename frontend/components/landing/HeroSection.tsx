"use client";

import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Sparkles, Search } from "lucide-react";
import { useTypingEffect } from "@/hooks/useTypingEffect";
import LiveUserCounter from "./LiveUserCounter";
import StylizedMacedonianFlag from "./StylizedMacedonianFlag";

const phrases = [
    "Нефер Предност во Јавните Набавки",
    "Предвидете ги понудите на конкурентите",
    "Извадете барања за секунди",
    "Анализирајте 17 години историја",
    "Победувајте почесто со AI",
];

export default function HeroSection() {
    const typedText = useTypingEffect(phrases, 80, 40, 3000);

    return (
        <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20">
            {/* Background Elements */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/20 via-background to-background" />
            <div className="absolute top-0 left-0 w-full h-full bg-[url('/grid.svg')] bg-center [mask-image:linear-gradient(180deg,white,rgba(255,255,255,0))]" />

            <div className="container relative z-10 px-4 md:px-6 text-center">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5 }}
                    className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-foreground/5 border border-border mb-8"
                >
                    <Sparkles className="w-4 h-4 text-primary" />
                    <span className="text-sm text-muted-foreground">AI-Powered Tender Intelligence</span>
                </motion.div>

                {/* Stylized Flag - Absolute on Desktop, Flow on Mobile */}
                <div className="absolute top-0 right-4 md:right-10 hidden md:block">
                    <StylizedMacedonianFlag />
                </div>
                <div className="md:hidden flex justify-center mb-6">
                    <StylizedMacedonianFlag />
                </div>

                <motion.h1
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className="text-4xl md:text-6xl lg:text-7xl font-bold tracking-tight mb-6 min-h-[180px] md:min-h-[200px] flex items-center justify-center"
                >
                    <span className="text-foreground notranslate">
                        {typedText}
                        <span className="inline-block w-1 h-12 md:h-16 bg-primary ml-1 animate-pulse" />
                    </span>
                </motion.h1>

                <motion.p
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-10"
                >
                    Анализирајте 270,000+ тендери, 40,000+ документи и 17 години историја со AI. Предвидете цени, победете конкуренти.
                </motion.p>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                    className="flex flex-col items-center justify-center gap-4"
                >
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link href="/auth/register" className="flex flex-col items-center">
                            <Button size="lg" className="h-12 px-8 text-lg bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_30px_rgba(124,58,237,0.5)] hover:shadow-[0_0_50px_rgba(124,58,237,0.7)] transition-all duration-300" aria-label="Започни бесплатна регистрација">
                                Почни Бесплатно <ArrowRight className="ml-2 h-5 w-5" />
                            </Button>
                            <span className="text-xs text-muted-foreground mt-2">Не е потребна картичка</span>
                        </Link>
                        <Link href="#how-it-works">
                            <Button size="lg" variant="outline" className="h-12 px-8 text-lg border-border hover:bg-foreground/5 text-muted-foreground" aria-label="Дознајте како работи платформата">
                                Како работи?
                            </Button>
                        </Link>
                    </div>

                    {/* Try it now hook */}
                    <div className="mt-8 w-full max-w-md mx-auto">
                        <p className="text-sm text-muted-foreground mb-2">Или пробајте веднаш:</p>
                        <div className="flex gap-2">
                            <input
                                type="text"
                                placeholder="Внесете клучен збор (пр. Лаптопи)"
                                aria-label="Внесете клучен збор за пребарување на тендери"
                                className="flex-1 h-12 rounded-lg bg-foreground/5 border border-border px-4 text-foreground placeholder:text-gray-500 focus:outline-none focus:border-primary/50 transition-colors"
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                        const target = e.target as HTMLInputElement;
                                        if (target.value.trim()) {
                                            window.location.href = `/auth/register?keyword=${encodeURIComponent(target.value)}`;
                                        }
                                    }
                                }}
                            />
                            <Button
                                className="h-12 px-6 bg-foreground/10 hover:bg-foreground/20 text-foreground border border-border"
                                aria-label="Пребарај тендери"
                                onClick={(e) => {
                                    const input = e.currentTarget.previousElementSibling as HTMLInputElement;
                                    if (input.value.trim()) {
                                        window.location.href = `/auth/register?keyword=${encodeURIComponent(input.value)}`;
                                    }
                                }}
                            >
                                <Search className="w-5 h-5" />
                            </Button>
                        </div>
                    </div>

                    <LiveUserCounter />
                </motion.div>

                {/* Floating Elements Animation */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] opacity-30 pointer-events-none">
                    <motion.div
                        animate={{ rotate: 360 }}
                        transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                        className="w-full h-full rounded-full border border-primary/20 border-dashed"
                    />
                </div>
            </div>
        </section>
    );
}
