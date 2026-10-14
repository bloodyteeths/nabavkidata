"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { ArrowRight, Mail, Phone } from "lucide-react";

export default function ServiceCTA() {
    return (
        <section className="py-20 relative overflow-hidden">
            <div className="container relative z-10 px-4 md:px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="max-w-4xl mx-auto text-center rounded-3xl border border-primary/30 bg-gradient-to-b from-primary/15 to-primary/5 backdrop-blur-sm p-8 md:p-12"
                >
                    <h2 className="text-3xl md:text-4xl font-bold mb-4">
                        <span className="text-foreground">Имате тендер на око? </span>
                        <span className="text-gradient">Ние ќе ја напишеме понудата.</span>
                    </h2>
                    <p className="text-muted-foreground text-lg max-w-2xl mx-auto mb-8">
                        Пополнете ја кратката проценка. Ќе ви кажеме дали ги исполнувате условите и
                        колку би чинела подготовката, пред да договориме било каква работа.
                    </p>
                    <Link href="/usluga">
                        <Button
                            size="lg"
                            className="h-14 px-10 text-lg bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_30px_rgba(124,58,237,0.5)] hover:shadow-[0_0_50px_rgba(124,58,237,0.7)] transition-all duration-300"
                        >
                            Бесплатна проценка <ArrowRight className="ml-2 h-5 w-5" />
                        </Button>
                    </Link>
                    <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-8 text-sm text-muted-foreground">
                        <a href="mailto:hello@nabavkidata.com" className="inline-flex items-center gap-2 hover:text-foreground transition-colors">
                            <Mail className="w-4 h-4" /> hello@nabavkidata.com
                        </a>
                        <a href="tel:+38970253467" className="inline-flex items-center gap-2 hover:text-foreground transition-colors notranslate">
                            <Phone className="w-4 h-4" /> +389 70 253 467
                        </a>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}

export function ServiceFooter() {
    return (
        <footer className="py-12 border-t border-border bg-background/20">
            <div className="container px-4 md:px-6">
                <div className="flex flex-col md:flex-row justify-between items-center gap-6 text-muted-foreground">
                    <div className="text-sm text-center md:text-left space-y-1">
                        <p>&copy; 2026 Фактурино ДООЕЛ. Сите права се задржани.</p>
                        <p className="text-xs text-muted-foreground/80">
                            ул. Сараевска 37, 1400 Велес · ЕДБ 4004026525934 · ЕМБС 7922400
                        </p>
                    </div>
                    <nav className="flex flex-wrap justify-center gap-6 text-sm">
                        <Link href="/privacy" className="hover:text-primary transition-colors">
                            Политика за приватност
                        </Link>
                        <Link href="/terms" className="hover:text-primary transition-colors">
                            Услови за користење
                        </Link>
                        <Link href="/contact" className="hover:text-primary transition-colors">
                            Контакт
                        </Link>
                    </nav>
                </div>
            </div>
        </footer>
    );
}
