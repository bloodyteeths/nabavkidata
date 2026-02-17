"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Check, Sparkles, Zap, Crown, Building2, ArrowRight } from "lucide-react";
import { motion } from "framer-motion";
import { api } from "@/lib/api";

type Currency = "mkd" | "eur";

const plans = [
    {
        name: "Бесплатно",
        id: "free",
        icon: Sparkles,
        price: {
            mkd: { monthly: 0, yearly: 0 },
            eur: { monthly: 0, yearly: 0 }
        },
        description: "Започнете без ризик. Идеално за истражување.",
        features: [
            "Преглед на сите тендери",
            "3 AI прашања дневно",
            "Основно пребарување",
            "1 зачувано известување"
        ],
        cta: "Започни бесплатно"
    },
    {
        name: "Стартуј",
        id: "starter",
        icon: Zap,
        price: {
            mkd: { monthly: 1990, yearly: 19900 },
            eur: { monthly: 39, yearly: 390 }
        },
        description: "За фриленсери и мали бизниси.",
        features: [
            "15 AI прашања дневно",
            "10 зачувани известувања",
            "CSV извоз",
            "5 известувања за конкуренти"
        ],
        cta: "Започни"
    },
    {
        name: "Про",
        id: "professional",
        icon: Crown,
        price: {
            mkd: { monthly: 5990, yearly: 59900 },
            eur: { monthly: 99, yearly: 990 }
        },
        popular: true,
        description: "За растечки компании кои сакаат конкурентска предност.",
        features: [
            "50 AI прашања дневно",
            "50 зачувани известувања",
            "CSV извоз",
            "Анализа на ризик",
            "20 известувања за конкуренти"
        ],
        cta: "Најпопуларен избор"
    },
    {
        name: "Претпријатие",
        id: "enterprise",
        icon: Building2,
        price: {
            mkd: { monthly: 12990, yearly: 129900 },
            eur: { monthly: 199, yearly: 1990 }
        },
        description: "За тимови и одделенија со напредни потреби.",
        features: [
            "Неограничени AI прашања",
            "Неограничени известувања",
            "API пристап",
            "До 10 членови на тим",
            "Неограничени конкуренти"
        ],
        cta: "Започни"
    }
];

export default function PricingSection() {
    const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("monthly");
    const [currency, setCurrency] = useState<Currency>("mkd");
    const [loading, setLoading] = useState<string | null>(null);
    const router = useRouter();

    const formatPrice = (amount: number, curr: Currency) => {
        if (amount === 0) return "0";
        if (curr === "eur") {
            return `€${amount}`;
        }
        return amount.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    };

    const handleSelectPlan = async (planId: string) => {
        if (planId === "free") {
            router.push("/auth/register");
            return;
        }

        setLoading(planId);
        try {
            const response = await api.createCheckoutSession(planId, billingCycle, currency);
            if (response.checkout_url) {
                window.location.href = response.checkout_url;
            }
        } catch (error: any) {
            console.error("Checkout error:", error);
            // Check for unauthorized (not logged in) - redirect to register
            if (error.message?.includes("Unauthorized") || error.message?.includes("401") || error.status === 401) {
                router.push(`/auth/register?plan=${planId}&interval=${billingCycle}&currency=${currency}`);
            }
        } finally {
            setLoading(null);
        }
    };

    const handleStartTrial = () => {
        router.push("/auth/register?trial=true");
    };

    return (
        <section id="pricing" className="py-24 relative">
            {/* Background glow effect */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-primary/5 rounded-full blur-3xl" />
            </div>

            <div className="container px-4 md:px-6 relative">
                <div className="text-center mb-12">
                    <motion.h2
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="text-3xl md:text-5xl font-bold mb-4"
                    >
                        Едноставни <span className="text-gradient">Цени</span>
                    </motion.h2>
                    <motion.p
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.1 }}
                        className="text-gray-400 max-w-2xl mx-auto text-lg mb-8"
                    >
                        Изберете го планот кој најмногу одговара на вашите потреби. Без скриени трошоци.
                    </motion.p>

                    {/* Trial Banner */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.2 }}
                        className="inline-flex items-center gap-3 bg-gradient-to-r from-primary/20 to-purple-500/20 border border-primary/30 rounded-2xl px-6 py-4 mb-10"
                    >
                        <Sparkles className="w-5 h-5 text-primary" />
                        <div className="text-left">
                            <p className="text-white font-semibold">7-дневна бесплатна проба на Про план</p>
                            <p className="text-gray-400 text-sm">50 AI пораки • 15 екстракции • 5 извози</p>
                        </div>
                        <Button
                            onClick={handleStartTrial}
                            size="sm"
                            className="bg-primary hover:bg-primary/90 ml-2"
                        >
                            Пробај бесплатно
                            <ArrowRight className="w-4 h-4 ml-1" />
                        </Button>
                    </motion.div>

                    {/* Toggle Controls */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: 0.3 }}
                        className="flex flex-col sm:flex-row items-center justify-center gap-6"
                    >
                        {/* Currency Toggle */}
                        <div className="flex items-center gap-3 bg-white/5 rounded-full px-4 py-2 border border-white/10">
                            <span className={`text-sm font-medium transition-colors ${currency === "mkd" ? "text-white" : "text-gray-500"}`}>
                                МКД
                            </span>
                            <button
                                onClick={() => setCurrency(currency === "mkd" ? "eur" : "mkd")}
                                className="relative w-12 h-6 rounded-full bg-white/10 p-0.5 transition-colors hover:bg-white/20"
                            >
                                <motion.div
                                    className="w-5 h-5 rounded-full bg-primary shadow-lg"
                                    animate={{ x: currency === "mkd" ? 0 : 24 }}
                                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                                />
                            </button>
                            <span className={`text-sm font-medium transition-colors ${currency === "eur" ? "text-white" : "text-gray-500"}`}>
                                EUR
                            </span>
                        </div>

                        {/* Billing Toggle */}
                        <div className="flex items-center gap-3 bg-white/5 rounded-full px-4 py-2 border border-white/10">
                            <span className={`text-sm font-medium transition-colors ${billingCycle === "monthly" ? "text-white" : "text-gray-500"}`}>
                                Месечно
                            </span>
                            <button
                                onClick={() => setBillingCycle(billingCycle === "monthly" ? "yearly" : "monthly")}
                                className="relative w-12 h-6 rounded-full bg-white/10 p-0.5 transition-colors hover:bg-white/20"
                            >
                                <motion.div
                                    className="w-5 h-5 rounded-full bg-primary shadow-lg"
                                    animate={{ x: billingCycle === "monthly" ? 0 : 24 }}
                                    transition={{ type: "spring", stiffness: 500, damping: 30 }}
                                />
                            </button>
                            <span className={`text-sm font-medium transition-colors ${billingCycle === "yearly" ? "text-white" : "text-gray-500"}`}>
                                Годишно
                                <span className="ml-1 text-xs text-primary font-bold">-17%</span>
                            </span>
                        </div>
                    </motion.div>

                    {currency === "eur" && (
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            className="text-gray-500 text-sm mt-4"
                        >
                            Плаќање со картичка или SEPA директна дебитација
                        </motion.p>
                    )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 max-w-7xl mx-auto">
                    {plans.map((plan, index) => {
                        const Icon = plan.icon;
                        const price = plan.price[currency][billingCycle];
                        const monthlyEquivalent = billingCycle === "yearly" ? Math.round(price / 12) : price;

                        return (
                            <motion.div
                                key={plan.id}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: index * 0.1 }}
                                className={`relative p-6 rounded-2xl border backdrop-blur-sm transition-all duration-300 hover:scale-[1.02] flex flex-col h-full ${
                                    plan.popular
                                        ? "bg-gradient-to-b from-primary/20 to-primary/5 border-primary shadow-[0_0_40px_rgba(124,58,237,0.15)]"
                                        : "bg-white/5 border-white/10 hover:border-white/20"
                                }`}
                            >
                                {plan.popular && (
                                    <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 bg-gradient-to-r from-primary to-purple-500 text-white text-xs font-bold rounded-full shadow-lg">
                                        НАЈПОПУЛАРЕН
                                    </div>
                                )}

                                <div className="mb-6">
                                    <div className={`inline-flex p-2.5 rounded-xl mb-4 ${
                                        plan.popular ? "bg-primary/20" : "bg-white/10"
                                    }`}>
                                        <Icon className={`w-5 h-5 ${plan.popular ? "text-primary" : "text-gray-400"}`} />
                                    </div>
                                    <h3 className="text-xl font-bold mb-1 text-white">{plan.name}</h3>
                                    <p className="text-gray-400 text-sm">{plan.description}</p>
                                </div>

                                <div className="mb-6">
                                    <div className="flex items-baseline gap-1">
                                        <span className="text-4xl font-bold text-white">
                                            {formatPrice(monthlyEquivalent, currency)}
                                        </span>
                                        <span className="text-gray-400 text-sm">
                                            {currency === "mkd" ? "ден" : ""}/{billingCycle === "monthly" ? "мес" : "мес"}
                                        </span>
                                    </div>
                                    {billingCycle === "yearly" && price > 0 && (
                                        <p className="text-gray-500 text-xs mt-1">
                                            Наплата {formatPrice(price, currency)} {currency === "mkd" ? "ден" : ""} годишно
                                        </p>
                                    )}
                                </div>

                                <ul className="space-y-3 mb-6 flex-grow">
                                    {plan.features.map((feature, idx) => (
                                        <li key={idx} className="flex items-start gap-2.5 text-gray-300 text-sm">
                                            <Check className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                                                plan.popular ? "text-primary" : "text-green-500"
                                            }`} />
                                            {feature}
                                        </li>
                                    ))}
                                </ul>

                                <Button
                                    onClick={() => handleSelectPlan(plan.id)}
                                    disabled={loading === plan.id}
                                    className={`w-full transition-all mt-auto ${
                                        plan.popular
                                            ? "bg-primary hover:bg-primary/90 text-white shadow-lg shadow-primary/25"
                                            : "bg-white/10 hover:bg-white/20 text-white border border-white/10"
                                    }`}
                                >
                                    {loading === plan.id ? (
                                        <span className="flex items-center gap-2">
                                            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                            Се вчитува...
                                        </span>
                                    ) : (
                                        plan.cta
                                    )}
                                </Button>
                            </motion.div>
                        );
                    })}
                </div>

                {/* Bottom note */}
                <motion.p
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.5 }}
                    className="text-center text-gray-500 text-sm mt-10"
                >
                    Сите плаќања се безбедни и процесирани преку Stripe. Откажете во секое време.
                </motion.p>
            </div>
        </section>
    );
}
