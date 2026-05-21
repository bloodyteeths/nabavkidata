"use client";

import { motion } from "framer-motion";
import { Search, Brain, Trophy } from "lucide-react";

const steps = [
    {
        icon: Search,
        title: "Кажете ни на што нудите",
        description: "Чистење, ИТ, градежништво — поставете ги вашите сектори, регион и буџет. Трае 2 минути.",
        color: "from-blue-500 to-cyan-500"
    },
    {
        icon: Brain,
        title: "AI ги наоѓа вашите можности",
        description: "Секој нов тендер е скениран спрема вашиот профил. Добивате совпаднати тендери со податоци за цени, историја на конкуренти и анализа на документи.",
        color: "from-purple-500 to-pink-500"
    },
    {
        icon: Trophy,
        title: "Нудете попаметно, победувајте почесто",
        description: "Знајте ја правилната цена, клучните барања и со кого се натпреварувате — пред да напишете збор.",
        color: "from-green-500 to-emerald-500"
    }
];

export default function HowItWorksSection() {
    return (
        <section id="how-it-works" className="py-16 relative overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/10 via-background to-background" />

            <div className="container relative z-10 px-4 md:px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="text-center mb-10"
                >
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        <span className="text-foreground">Од регистрација до </span>
                        <span className="text-gradient">победничка понуда</span>
                        <span className="text-foreground"> во 3 чекори</span>
                    </h2>
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-5xl mx-auto">
                    {steps.map((step, index) => {
                        const Icon = step.icon;
                        return (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.15 }}
                                className="relative group"
                            >
                                <div className="relative h-full p-6 rounded-2xl bg-foreground/5 border border-border backdrop-blur-sm hover:bg-foreground/10 transition-all duration-300">
                                    <div className="absolute -top-4 -left-4 w-12 h-12 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center text-white font-bold text-xl shadow-lg">
                                        {index + 1}
                                    </div>

                                    <div className={`w-16 h-16 rounded-xl bg-gradient-to-br ${step.color} p-3 mb-4 shadow-lg`}>
                                        <Icon className="w-full h-full text-white" />
                                    </div>

                                    <h3 className="text-xl font-semibold text-foreground mb-3">
                                        {step.title}
                                    </h3>
                                    <p className="text-muted-foreground text-sm leading-relaxed">
                                        {step.description}
                                    </p>

                                    {index < steps.length - 1 && (
                                        <div className="hidden md:block absolute top-1/2 -right-4 w-8 h-0.5 bg-gradient-to-r from-primary/50 to-transparent" />
                                    )}
                                </div>
                            </motion.div>
                        );
                    })}
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.4 }}
                    className="text-center mt-10"
                >
                    <a
                        href="/auth/register"
                        className="inline-flex items-center justify-center px-8 py-3 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground font-medium transition-all duration-300 shadow-[0_0_30px_rgba(124,58,237,0.5)] hover:shadow-[0_0_50px_rgba(124,58,237,0.7)]"
                    >
                        Почнете бесплатно денес
                    </a>
                </motion.div>
            </div>
        </section>
    );
}
