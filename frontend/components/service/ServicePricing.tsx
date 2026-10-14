"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Check, Search, PenLine, Trophy, ArrowRight } from "lucide-react";

const tiers = [
    {
        id: "assessment",
        name: "Проценка",
        icon: Search,
        price: "Бесплатно",
        priceNote: "",
        description: "Кажете ни што нудите. Ние проверуваме кои тендери ви одговараат и дали вреди да се понуди.",
        features: [
            "Бесплатна проценка дали вреди да се понуди",
            "Тендери избрани според вашата дејност",
            "Список на соодветни тендери во вашиот портал",
            "Без трошок и без обврска",
        ],
        highlight: false,
    },
    {
        id: "preparation",
        name: "Подготовка на понуда",
        icon: PenLine,
        price: "од 30.000 МКД",
        priceNote: "по понуда",
        description: "Изберете тендер, а нашиот тим ја подготвува целата понуда од документацијата.",
        features: [
            "Цената се договара однапред, пред да почне работата",
            "Изјави, техничка и финансиска понуда",
            "Проверка на секој услов од тендерската документација",
            "Вклучено: следење на тендери, известувања и AI анализи",
            "Плаќање со картичка или со фактура",
        ],
        highlight: true,
    },
    {
        id: "success",
        name: "Надомест за успех",
        icon: Trophy,
        price: "5%",
        priceNote: "од вредноста за првата година",
        description: "Се плаќа само ако договорот ви биде доделен. Ако не победите, не плаќате надомест за успех.",
        features: [
            "Без победа, нема надомест за успех",
            "Се пресметува на вредноста на договорот за првата година",
            "Се одбива платениот надомест за подготовка на таа понуда",
            "Најава најмалку седум дена пред наплатата",
            "Ги делиме ризикот и успехот",
        ],
        highlight: false,
    },
];

export default function ServicePricing() {
    return (
        <section id="pricing" className="py-16 relative scroll-mt-20">
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] max-w-full bg-primary/5 rounded-full blur-3xl" />
            </div>

            <div className="container px-4 md:px-6 relative">
                <div className="text-center mb-12">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-3xl md:text-5xl font-bold mb-4"
                    >
                        <span className="text-foreground">Јасни цени, </span>
                        <span className="text-gradient">без претплата</span>
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 }}
                        className="text-muted-foreground max-w-2xl mx-auto text-lg"
                    >
                        Бесплатна проценка, договорен надомест за подготовка на секоја понуда
                        и надомест за успех само кога ќе победите. Следењето на тендери и известувањата
                        се вклучени за клиентите.
                    </motion.p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
                    {tiers.map((tier, index) => {
                        const Icon = tier.icon;
                        return (
                            <motion.div
                                key={tier.id}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: index * 0.1 }}
                                className={`relative p-6 rounded-2xl border backdrop-blur-sm transition-all duration-300 flex flex-col h-full ${
                                    tier.highlight
                                        ? "bg-gradient-to-b from-primary/20 to-primary/5 border-primary shadow-[0_0_40px_rgba(124,58,237,0.15)]"
                                        : "bg-foreground/5 border-border hover:border-foreground/20"
                                }`}
                            >
                                {tier.highlight && (
                                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 bg-primary text-primary-foreground text-xs font-bold rounded-full shadow-lg whitespace-nowrap">
                                        НИЕ ЈА ПИШУВАМЕ ПОНУДАТА
                                    </div>
                                )}

                                <div className="mb-6">
                                    <div className={`inline-flex p-2.5 rounded-xl mb-4 ${tier.highlight ? "bg-primary/20" : "bg-foreground/10"}`}>
                                        <Icon className={`w-5 h-5 ${tier.highlight ? "text-primary" : "text-muted-foreground"}`} />
                                    </div>
                                    <h3 className="text-xl font-bold mb-1 text-foreground">{tier.name}</h3>
                                    <p className="text-muted-foreground text-sm">{tier.description}</p>
                                </div>

                                <div className="mb-6">
                                    <div className="flex items-baseline gap-2 flex-wrap">
                                        <span className="text-3xl md:text-4xl font-bold text-foreground notranslate">{tier.price}</span>
                                        {tier.priceNote && <span className="text-muted-foreground text-sm">{tier.priceNote}</span>}
                                    </div>
                                </div>

                                <ul className="space-y-3 flex-grow">
                                    {tier.features.map((feature) => (
                                        <li key={feature} className="flex items-start gap-2.5 text-muted-foreground text-sm">
                                            <Check className={`w-4 h-4 mt-0.5 flex-shrink-0 ${tier.highlight ? "text-primary" : "text-green-500"}`} />
                                            {feature}
                                        </li>
                                    ))}
                                </ul>
                            </motion.div>
                        );
                    })}
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.3 }}
                    className="text-center mt-10"
                >
                    <Link href="/usluga">
                        <Button
                            size="lg"
                            className="h-14 px-10 text-lg bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_30px_rgba(124,58,237,0.5)] hover:shadow-[0_0_50px_rgba(124,58,237,0.7)] transition-all duration-300"
                        >
                            Побарајте бесплатна проценка
                            <ArrowRight className="w-5 h-5 ml-2" />
                        </Button>
                    </Link>
                    <p className="text-xs text-muted-foreground mt-3">Без трошок и без обврска</p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.4 }}
                    className="text-center text-sm mt-10 space-y-2 max-w-3xl mx-auto"
                >
                    <p className="text-muted-foreground">
                        Надоместот за подготовка се договара однапред за секоја понуда, пред да почне работата.
                        Плаќате со картичка преку Stripe или, на барање, со фактура од Фактурино ДООЕЛ. Нема претплата.
                        Следењето на тендери и известувањата се вклучени за клиентите. Проценката е бесплатна.
                    </p>
                    <p className="text-muted-foreground/80">
                        Понудата ја поднесувате вие, со ваш сертификат. Победа не можеме да гарантираме, но
                        најголемиот дел од нашиот надомест зависи од вашата победа.
                    </p>
                    <p className="text-muted-foreground/80">
                        Детални услови:{" "}
                        <Link href="/terms" className="underline underline-offset-4 hover:text-foreground">
                            Услови за користење
                        </Link>
                    </p>
                </motion.div>
            </div>
        </section>
    );
}
