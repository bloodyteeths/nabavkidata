"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import { Shield, Lock, Zap, Award } from "lucide-react";

const partners = [
    {
        name: "Google Cloud",
        logo: "https://www.gstatic.com/images/branding/googlelogo/svg/googlelogo_clr_74x24px.svg",
        description: "AI & Cloud Infrastructure"
    },
    {
        name: "AWS",
        logo: "https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg",
        description: "Cloud Hosting"
    },
    {
        name: "Stripe",
        logo: "https://images.ctfassets.net/fzn2n1nzq965/3AGidihOJl4nH9D1vDjM84/9540155d584be52fc54c443b6efa4ae6/stripe.svg",
        description: "Secure Payments"
    },
    {
        name: "e-nabavki",
        logo: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 40'%3E%3Ctext x='10' y='28' font-family='Arial, sans-serif' font-size='20' font-weight='bold' fill='white'%3Ee-nabavki%3C/text%3E%3C/svg%3E",
        description: "Јавни набавки"
    },
    {
        name: "e-pazar",
        logo: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 40'%3E%3Ctext x='10' y='28' font-family='Arial, sans-serif' font-size='20' font-weight='bold' fill='white'%3Ee-pazar%3C/text%3E%3C/svg%3E",
        description: "Електронски пазар"
    }
];

const trustBadges = [
    {
        icon: Shield,
        title: "100% Сигурност",
        description: "Енкриптирани податоци"
    },
    {
        icon: Lock,
        title: "GDPR Усогласено",
        description: "Заштита на приватност"
    },
    {
        icon: Zap,
        title: "99.9% Uptime",
        description: "Секогаш достапно"
    },
    {
        icon: Award,
        title: "Сертифицирано",
        description: "ISO 27001 стандард"
    }
];

export default function TrustSection() {
    return (
        <section className="py-16 md:py-24 bg-foreground/5 border-y border-border">
            <div className="container px-4 md:px-6">
                {/* Trust Badges */}
                <div className="mb-16 md:mb-20">
                    <div className="text-center mb-10 md:mb-12">
                        <h2 className="text-2xl md:text-3xl font-bold mb-3 md:mb-4">
                            <span className="text-gradient">Доверба</span> и Сигурност
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto text-sm md:text-base px-4">
                            Вашите податоци се заштитени со највисоки безбедносни стандарди
                        </p>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6 max-w-4xl mx-auto">
                        {trustBadges.map((badge, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ delay: index * 0.1 }}
                                className="p-4 md:p-6 rounded-xl bg-foreground/5 border border-border text-center hover:bg-foreground/10 transition-colors"
                            >
                                <div className="w-10 h-10 md:w-12 md:h-12 rounded-lg bg-primary/20 flex items-center justify-center mx-auto mb-3 md:mb-4">
                                    <badge.icon className="w-5 h-5 md:w-6 md:h-6 text-primary" />
                                </div>
                                <h3 className="text-sm md:text-base font-bold mb-1 md:mb-2 text-foreground">{badge.title}</h3>
                                <p className="text-xs md:text-sm text-muted-foreground">{badge.description}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>

                {/* Partners */}
                <div>
                    <div className="text-center mb-8 md:mb-12">
                        <p className="text-xs md:text-sm text-muted-foreground uppercase tracking-wider mb-6 md:mb-8">
                            Технологии од светски лидери
                        </p>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6 md:gap-8 items-center max-w-5xl mx-auto">
                        {partners.map((partner, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, scale: 0.9 }}
                                whileInView={{ opacity: 1, scale: 1 }}
                                viewport={{ once: true }}
                                transition={{ delay: index * 0.1 }}
                                className="flex flex-col items-center gap-2 md:gap-3 p-4 md:p-6 rounded-xl hover:bg-foreground/5 transition-colors group"
                            >
                                <div className="relative w-20 h-12 md:w-24 md:h-14 flex items-center justify-center opacity-70 group-hover:opacity-100 transition-opacity">
                                    <Image
                                        src={partner.logo}
                                        alt={partner.name}
                                        width={96}
                                        height={56}
                                        className="max-w-full max-h-full object-contain"
                                        style={{ filter: 'brightness(0) invert(1)' }}
                                        loading="lazy"
                                        unoptimized={partner.logo.startsWith('data:')}
                                    />
                                </div>
                                <p className="text-xs text-gray-500 text-center">{partner.description}</p>
                            </motion.div>
                        ))}
                    </div>
                </div>

                {/* Additional Trust Indicators */}
                <div className="mt-12 md:mt-16 text-center">
                    <div className="inline-flex flex-wrap items-center justify-center gap-4 md:gap-6 text-xs md:text-sm text-muted-foreground">
                        <div className="flex items-center gap-2">
                            <Shield className="w-4 h-4 text-primary" />
                            <span>SSL Енкрипција</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Lock className="w-4 h-4 text-primary" />
                            <span>2FA Автентикација</span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Award className="w-4 h-4 text-primary" />
                            <span>Редовни Безбедносни Проверки</span>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
