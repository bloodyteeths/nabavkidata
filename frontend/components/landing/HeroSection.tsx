"use client";

import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";
import Link from "next/link";
import { ArrowRight, Sparkles } from "lucide-react";
import { useTypingEffect } from "@/hooks/useTypingEffect";
import LiveUserCounter from "./LiveUserCounter";
import StylizedMacedonianFlag from "./StylizedMacedonianFlag";

const phrases = [
    "Не губи тендери поради лошо пребарување",
    "Дознај ги цените на конкурентите",
    "Најди ги вистинските тендери веднаш",
    "Анализирајте конкуренција со AI",
    "Зголемете ги шансите за успех",
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
                    className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 mb-8"
                >
                    <Sparkles className="w-4 h-4 text-primary" />
                    <span className="text-sm text-gray-300">AI-Powered Tender Intelligence</span>
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
                    <span className="text-white">
                        {typedText}
                        <span className="inline-block w-1 h-12 md:h-16 bg-primary ml-1 animate-pulse" />
                    </span>
                </motion.h1>

                <motion.p
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto mb-10"
                >
                    Nabavkidata користи напредна AI технологија за да ви помогне да ги најдете вистинските тендери, да ја анализирате конкуренцијата и да победувате почесто.
                </motion.p>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: 0.3 }}
                    className="flex flex-col items-center justify-center gap-4"
                >
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                        <Link href="/auth/register" className="flex flex-col items-center">
                            <Button size="lg" className="h-12 px-8 text-lg bg-primary hover:bg-primary/90 text-white shadow-[0_0_30px_rgba(124,58,237,0.5)] hover:shadow-[0_0_50px_rgba(124,58,237,0.7)] transition-all duration-300">
                                Почни Бесплатно <ArrowRight className="ml-2 h-5 w-5" />
                            </Button>
                            <span className="text-xs text-gray-400 mt-2">Не е потребна картичка</span>
                        </Link>
                        <Link href="#how-it-works">
                            <Button size="lg" variant="outline" className="h-12 px-8 text-lg border-white/10 hover:bg-white/5 text-gray-300">
                                Како работи?
                            </Button>
                        </Link>
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
