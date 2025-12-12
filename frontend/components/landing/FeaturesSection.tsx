"use client";

import { motion } from "framer-motion";
import { Brain, Search, Zap, Shield, BarChart3, Bell } from "lucide-react";

const features = [
    {
        icon: Brain,
        title: "Разговарај со Тендери",
        description: "Поставете прашање и добијте одговор веднаш од документацијата, наместо да читате стотици страници."
    },
    {
        icon: Search,
        title: "Паметно Пребарување",
        description: "Заборавете на клучни зборови. Нашиот систем го разбира контекстот и ви наоѓа тендери кои навистина одговараат."
    },
    {
        icon: Zap,
        title: "Инстант Нотификации",
        description: "Бидете први што ќе дознаете. Добивајте известувања во реално време за нови тендери и промени."
    },
    {
        icon: Shield,
        title: "Автоматска Екстракција",
        description: "AI ги чита PDF документите и автоматски ги вади сите технички и финансиски барања, заштедувајќи ви часови работа."
    },
    {
        icon: BarChart3,
        title: "Win Factors & Анализа",
        description: "Откријте зошто конкурентите победуваат. Дали е цената или квалитетот? Нашата AI анализа ви ги открива нивните тајни."
    },
    {
        icon: Bell,
        title: "Автоматизација",
        description: "Автоматизирајте го процесот на следење и аплицирање. Заштедете време и ресурси."
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
                    <p className="text-gray-400 max-w-2xl mx-auto text-lg">
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
                            className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors group"
                        >
                            <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                                <feature.icon className="w-6 h-6 text-primary" />
                            </div>
                            <h3 className="text-xl font-bold mb-2 text-white">{feature.title}</h3>
                            <p className="text-gray-400">{feature.description}</p>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
