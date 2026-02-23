"use client";

import { motion } from "framer-motion";
import { AlertTriangle, Clock, DollarSign, Eye, TrendingDown, Users } from "lucide-react";

const losses = [
    {
        icon: DollarSign,
        title: "Губите Тендери",
        color: "from-red-500 to-orange-500",
        pain: "Конкурентите ги знаат победничките цени. Вие погодувате.",
        losses: [
            "Не знаете колку платиле институциите претходно",
            "Ги нудите погрешните цени и губите",
            "Не знаете кој колку попуст дава",
            "Конкурентите имаат информации - вие немате"
        ],
        solution: "Ние ги анализиравме цените од 7,597 производи за 5 години."
    },
    {
        icon: Clock,
        title: "Губите Време",
        color: "from-orange-500 to-yellow-500",
        pain: "Денови читате документи. AI го прави тоа за секунди.",
        losses: [
            "2-3 часа дневно барате релевантни тендери",
            "Недели читате PDF спецификации",
            "Рачно пребарувате низ e-nabavki",
            "Пропуштате рокови додека истражувате"
        ],
        solution: "Нашиот AI пребарува 40,000+ документи за 10 секунди."
    },
    {
        icon: Eye,
        title: "Губите Слепо",
        color: "from-yellow-500 to-red-500",
        pain: "Не знаете против кого се натпреварувате.",
        losses: [
            "Не знаете win rate на конкурентите",
            "Не знаете кој доминира во вашиот сектор",
            "Не знаете како се позиционираат другите",
            "Стратегијата ви е базирана на претпоставки"
        ],
        solution: "Следиме 1,873 компании и нивните стратегии."
    }
];

export default function ValuePropositionSection() {
    return (
        <section className="py-16 md:py-24 relative overflow-hidden">
            {/* Background Elements */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-red-500/5 via-background to-background" />

            <div className="container relative z-10 px-4 md:px-6">
                {/* Section Header */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="text-center mb-12 md:mb-16"
                >
                    <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-red-500/10 border border-red-500/30 mb-6">
                        <AlertTriangle className="w-4 h-4 text-red-400" />
                        <span className="text-sm text-red-300">Секој ден без нас ве чини пари</span>
                    </div>
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        Што <span className="text-red-400">губите</span> без вистински податоци?
                    </h2>
                    <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                        Вашите конкуренти веќе имаат пристап до информации што вие ги немате. Секој изгубен тендер е пропуштена шанса.
                    </p>
                </motion.div>

                {/* Loss Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
                    {losses.map((loss, index) => {
                        const Icon = loss.icon;
                        return (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.1 }}
                                className="relative group"
                            >
                                <div className="h-full p-6 md:p-8 rounded-2xl bg-foreground/5 border border-red-500/20 backdrop-blur-sm hover:border-red-500/40 transition-all duration-300">
                                    {/* Icon */}
                                    <div className={`w-14 h-14 md:w-16 md:h-16 rounded-xl bg-gradient-to-br ${loss.color} p-3 mb-4 shadow-lg`}>
                                        <Icon className="w-full h-full text-white" />
                                    </div>

                                    {/* Title */}
                                    <h3 className="text-xl md:text-2xl font-bold text-red-400 mb-2">
                                        {loss.title}
                                    </h3>

                                    {/* Pain Point */}
                                    <p className="text-foreground font-medium mb-4">
                                        {loss.pain}
                                    </p>

                                    {/* Loss List */}
                                    <ul className="space-y-2 mb-6">
                                        {loss.losses.map((item, itemIndex) => (
                                            <li key={itemIndex} className="flex items-start gap-2 text-sm text-muted-foreground">
                                                <TrendingDown className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                                                {item}
                                            </li>
                                        ))}
                                    </ul>

                                    {/* Solution */}
                                    <div className="pt-4 border-t border-border">
                                        <p className="text-sm text-primary font-medium">
                                            ✓ {loss.solution}
                                        </p>
                                    </div>
                                </div>
                            </motion.div>
                        );
                    })}
                </div>

                {/* Bottom CTA */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.4 }}
                    className="mt-12 md:mt-16 text-center"
                >
                    <p className="text-xl md:text-2xl text-foreground font-bold mb-2">
                        Колку тендери изгубивте минатиот месец?
                    </p>
                    <p className="text-muted-foreground">
                        Дознајте што ве чини незнаењето. Пробајте бесплатно.
                    </p>
                </motion.div>
            </div>
        </section>
    );
}
