"use client";

import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import { motion } from "framer-motion";

const plans = [
    {
        name: "Старт",
        price: "2,999",
        description: "За мали бизниси кои сакаат да започнат со тендери.",
        features: [
            "Пристап до сите тендери",
            "Основно пребарување",
            "Дневни известувања",
            "До 3 корисници",
            "Основна поддршка"
        ]
    },
    {
        name: "Про",
        price: "5,999",
        popular: true,
        description: "За растечки компании кои сакаат конкурентска предност.",
        features: [
            "Сè од Старт пакетот",
            "AI Анализа на тендери",
            "Проценка на ризик",
            "Анализа на конкуренција",
            "Неограничени корисници",
            "Приоритетна поддршка"
        ]
    },
    {
        name: "Ентерпрајз",
        price: "Контакт",
        description: "За големи организации со специфични потреби.",
        features: [
            "Сè од Про пакетот",
            "API пристап",
            "Custom интеграции",
            "Дедициран менаџер",
            "SLA гаранција",
            "Обука за тимот"
        ]
    }
];

export default function PricingSection() {
    return (
        <section id="pricing" className="py-24 relative">
            <div className="container px-4 md:px-6">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        Едноставни <span className="text-gradient">Цени</span>
                    </h2>
                    <p className="text-gray-400 max-w-2xl mx-auto text-lg">
                        Изберете го планот кој најмногу одговара на вашите потреби. Без скриени трошоци.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
                    {plans.map((plan, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                            className={`relative p-8 rounded-2xl border ${plan.popular
                                    ? "bg-primary/10 border-primary shadow-[0_0_30px_rgba(124,58,237,0.2)]"
                                    : "bg-white/5 border-white/10"
                                }`}
                        >
                            {plan.popular && (
                                <div className="absolute -top-4 left-1/2 -translate-x-1/2 px-4 py-1 bg-primary text-white text-sm font-bold rounded-full">
                                    НАЈПОПУЛАРЕН
                                </div>
                            )}

                            <div className="mb-8">
                                <h3 className="text-2xl font-bold mb-2 text-white">{plan.name}</h3>
                                <p className="text-gray-400 text-sm mb-6">{plan.description}</p>
                                <div className="flex items-baseline gap-1">
                                    <span className="text-4xl font-bold text-white">{plan.price}</span>
                                    {plan.price !== "Контакт" && <span className="text-gray-400">МКД/мес</span>}
                                </div>
                            </div>

                            <ul className="space-y-4 mb-8">
                                {plan.features.map((feature, idx) => (
                                    <li key={idx} className="flex items-center gap-3 text-gray-300">
                                        <Check className="w-5 h-5 text-primary" />
                                        {feature}
                                    </li>
                                ))}
                            </ul>

                            <Button
                                className={`w-full ${plan.popular
                                        ? "bg-primary hover:bg-primary/90 text-white"
                                        : "bg-white/10 hover:bg-white/20 text-white"
                                    }`}
                            >
                                Избери План
                            </Button>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
