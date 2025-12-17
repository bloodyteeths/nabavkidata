"use client";

import { motion } from "framer-motion";
import { Database, TrendingUp, DollarSign, Building2, FileText, Users } from "lucide-react";

const stats = [
    {
        icon: Database,
        title: "Огромна База на Знаење",
        color: "from-blue-500 to-cyan-500",
        items: [
            { label: "Тендери анализирани", value: "9,181" },
            { label: "Документи индексирани", value: "31,592" },
            { label: "PDF екстрактирани", value: "10,693" },
            { label: "Години историја", value: "5" }
        ]
    },
    {
        icon: Users,
        title: "Конкурентска Интелигенција",
        color: "from-purple-500 to-pink-500",
        items: [
            { label: "Компании следени", value: "1,873" },
            { label: "Институции мапирани", value: "1,013" },
            { label: "Win rate анализа", value: "✓" },
            { label: "Market share по сектор", value: "✓" }
        ]
    },
    {
        icon: DollarSign,
        title: "Ценовна Транспарентност",
        color: "from-orange-500 to-red-500",
        items: [
            { label: "Производи со цени", value: "7,597" },
            { label: "E-Pazar тендери", value: "890" },
            { label: "Ценовни трендови", value: "✓" },
            { label: "Конкурентни препораки", value: "✓" }
        ]
    }
];

export default function ValuePropositionSection() {
    return (
        <section className="py-16 md:py-24 relative overflow-hidden">
            {/* Background Elements */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/5 via-background to-background" />

            <div className="container relative z-10 px-4 md:px-6">
                {/* Section Header */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="text-center mb-12 md:mb-16"
                >
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        Податоци што <span className="text-gradient">Донесуваат Победи</span>
                    </h2>
                    <p className="text-lg text-gray-400 max-w-2xl mx-auto">
                        Најголемата база на податоци за јавни набавки во Македонија, достапна преку AI
                    </p>
                </motion.div>

                {/* Stats Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
                    {stats.map((stat, index) => {
                        const Icon = stat.icon;
                        return (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.1 }}
                                className="relative group"
                            >
                                <div className="h-full p-6 md:p-8 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm hover:bg-white/10 transition-all duration-300">
                                    {/* Icon */}
                                    <div className={`w-14 h-14 md:w-16 md:h-16 rounded-xl bg-gradient-to-br ${stat.color} p-3 mb-4 md:mb-6 shadow-lg`}>
                                        <Icon className="w-full h-full text-white" />
                                    </div>

                                    {/* Title */}
                                    <h3 className="text-xl md:text-2xl font-bold text-white mb-4 md:mb-6">
                                        {stat.title}
                                    </h3>

                                    {/* Stats List */}
                                    <ul className="space-y-3">
                                        {stat.items.map((item, itemIndex) => (
                                            <li key={itemIndex} className="flex items-center justify-between">
                                                <span className="text-sm md:text-base text-gray-400">{item.label}</span>
                                                <span className="text-lg md:text-xl font-bold text-white">{item.value}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            </motion.div>
                        );
                    })}
                </div>

                {/* Bottom Highlight */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.4 }}
                    className="mt-12 md:mt-16 text-center"
                >
                    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/30">
                        <FileText className="w-4 h-4 text-primary" />
                        <span className="text-sm md:text-base text-gray-300">
                            Ажурирано секојден од официјални извори
                        </span>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
