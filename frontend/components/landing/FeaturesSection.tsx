"use client";

import { motion } from "framer-motion";
import { Brain, Search, Zap, Shield, BarChart3, Bell } from "lucide-react";

const features = [
    {
        icon: Brain,
        title: "Разговарај со Тендери",
        description: "Поставете прашање и добијте одговор веднаш од 40,000+ документи. AI го чита содржината, не општи претпоставки."
    },
    {
        icon: Search,
        title: "Паметно Пребарување",
        description: "Природен јазик на македонски и англиски. AI разбира контекст, синоними и индустриска терминологија."
    },
    {
        icon: BarChart3,
        title: "Ценовна Интелигенција",
        description: "Историски цени за 7,597 производи. Просечни, минимални и максимални цени со трендови по година и институција."
    },
    {
        icon: Shield,
        title: "Анализа на Конкуренти",
        description: "Win rate, market share по CPV код, head-to-head споредби. Дознајте кој доминира во вашиот сектор."
    },
    {
        icon: Zap,
        title: "Документна Интелигенција",
        description: "Пребарувајте во 40,000+ PDF документи. AI ги извлекува клучните барања и спецификации за секунди."
    },
    {
        icon: Bell,
        title: "AI Препораки",
        description: "Персонализирани стратегии за наддавање, оптимални цени и тајминг базирани на 17 години историски податоци."
    },
    {
        icon: Brain,
        title: "Контекстуални Разговори",
        description: "AI памети контекст. Поставувајте follow-up прашања природно без да повторувате информации."
    },
    {
        icon: Search,
        title: "Специјализирана за Македонија",
        description: "Податоци за 1,873 компании и 1,013 институции. Не општи одговори, туку локални инсајти."
    }
];

export default function FeaturesSection() {
    return (
        <section id="features" className="py-24 relative overflow-hidden">
            <div className="container px-4 md:px-6">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        <span className="text-gradient">AI Магија</span> во ваша служба
                    </h2>
                    <p className="text-muted-foreground max-w-2xl mx-auto text-lg">
                        Повеќе од обичен пребарувач. Nabavkidata е вашиот паметен асистент за јавни набавки.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                    {features.map((feature, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                            className="p-6 rounded-2xl bg-foreground/5 border border-border hover:bg-foreground/10 transition-colors group"
                        >
                            <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                                <feature.icon className="w-6 h-6 text-primary" />
                            </div>
                            <h3 className="text-xl font-bold mb-2 text-foreground">{feature.title}</h3>
                            <p className="text-muted-foreground">{feature.description}</p>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
