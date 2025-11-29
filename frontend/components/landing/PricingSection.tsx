"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import { motion } from "framer-motion";

const plans = [
    {
        name: "Старт",
        price: {
            monthly: "899",
            yearly: "8.990"
        },
        description: "За мали бизниси кои сакаат да започнат со тендери.",
        features: [
            "Пристап до сите тендери",
            "5 AI пребарувања дневно",
            "Дневни известувања",
            "CSV/PDF експорт",
            "Приоритетна поддршка"
        ]
    },
    {
        name: "Про",
        price: {
            monthly: "2.399",
            yearly: "23.990"
        },
        popular: true,
        description: "За растечки компании кои сакаат конкурентска предност.",
        features: [
            "Сè од Старт пакетот",
            "20 AI пребарувања дневно",
            "Аналитика",
            "Интеграции",
            "Дедицирана поддршка"
        ]
    },
    {
        name: "Ентерпрајз",
        price: {
            monthly: "5.999",
            yearly: "59.990"
        },
        description: "За големи организации со специфични потреби.",
        features: [
            "Сè од Про пакетот",
            "Неограничени AI пребарувања",
            "API пристап",
            "White-label",
            "24/7 поддршка"
        ]
    }
];

export default function PricingSection() {
    const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("monthly");
    const router = useRouter();

    return (
        <section id="pricing" className="py-24 relative">
            <div className="container px-4 md:px-6">
                <div className="text-center mb-10">
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        Едноставни <span className="text-gradient">Цени</span>
                    </h2>
                    <p className="text-gray-400 max-w-2xl mx-auto text-lg mb-8">
                        Изберете го планот кој најмногу одговара на вашите потреби. Без скриени трошоци.
                    </p>

                    {/* Billing Toggle */}
                    <div className="flex items-center justify-center gap-4">
                        <span className={`text-sm font-medium ${billingCycle === "monthly" ? "text-white" : "text-gray-400"}`}>
                            Месечно
                        </span>
                        <button
                            onClick={() => setBillingCycle(billingCycle === "monthly" ? "yearly" : "monthly")}
                            className="relative w-14 h-7 rounded-full bg-white/10 p-1 transition-colors hover:bg-white/20"
                        >
                            <motion.div
                                className="w-5 h-5 rounded-full bg-primary shadow-sm"
                                animate={{ x: billingCycle === "monthly" ? 0 : 28 }}
                                transition={{ type: "spring", stiffness: 500, damping: 30 }}
                            />
                        </button>
                        <span className={`text-sm font-medium ${billingCycle === "yearly" ? "text-white" : "text-gray-400"}`}>
                            Годишно <span className="text-primary text-xs ml-1">(Заштеди 20%)</span>
                        </span>
                    </div>
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
                                    <span className="text-4xl font-bold text-white">
                                        {billingCycle === "monthly" ? plan.price.monthly : plan.price.yearly}
                                    </span>
                                    <span className="text-gray-400">ден/{billingCycle === "monthly" ? "мес" : "год"}</span>
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
                                onClick={() => router.push('/auth/register')}
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
