"use client";

import { motion } from "framer-motion";
import { CheckCircle, Search, Bell, TrendingUp } from "lucide-react";

const steps = [
    {
        icon: Search,
        title: "Регистрирај се и постави преференци",
        description: "Создади профил и конфигурирај ги твоите интереси - сектори, CPV кодови, буџет и повеќе.",
        color: "from-blue-500 to-cyan-500"
    },
    {
        icon: CheckCircle,
        title: "AI ги анализира тендерите",
        description: "Нашата вештачка интелигенција автоматски ги скенира сите тендери и ги наоѓа оние што одговараат на твоите критериуми.",
        color: "from-purple-500 to-pink-500"
    },
    {
        icon: Bell,
        title: "Добивај инсајти и алерти",
        description: "Прими AI-базирани препораки, известувања за нови тендери и детални анализи на конкуренцијата.",
        color: "from-orange-500 to-red-500"
    },
    {
        icon: TrendingUp,
        title: "Освојувај повеќе тендери",
        description: "Користи ја конкурентската интелигенција за да ја подобриш твојата стратегија и да победуваш почесто.",
        color: "from-green-500 to-emerald-500"
    }
];

export default function HowItWorksSection() {
    return (
        <section id="how-it-works" className="py-24 relative overflow-hidden">
            {/* Background Elements */}
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/10 via-background to-background" />

            <div className="container relative z-10 px-4 md:px-6">
                {/* Section Header */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="text-center mb-16"
                >
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        <span className="text-foreground">Како работи</span>
                        <span className="text-gradient"> Nabavkidata</span>?
                    </h2>
                    <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                        Од регистрација до победа - едноставен процес во 4 чекори
                    </p>
                </motion.div>

                {/* Steps Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                    {steps.map((step, index) => {
                        const Icon = step.icon;
                        return (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.1 }}
                                className="relative group"
                            >
                                {/* Card */}
                                <div className="relative h-full p-6 rounded-2xl bg-foreground/5 border border-border backdrop-blur-sm hover:bg-foreground/10 transition-all duration-300">
                                    {/* Step Number */}
                                    <div className="absolute -top-4 -left-4 w-12 h-12 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center text-white font-bold text-xl shadow-lg">
                                        {index + 1}
                                    </div>

                                    {/* Icon */}
                                    <div className={`w-16 h-16 rounded-xl bg-gradient-to-br ${step.color} p-3 mb-4 shadow-lg`}>
                                        <Icon className="w-full h-full text-white" />
                                    </div>

                                    {/* Content */}
                                    <h3 className="text-xl font-semibold text-foreground mb-3">
                                        {step.title}
                                    </h3>
                                    <p className="text-muted-foreground text-sm leading-relaxed">
                                        {step.description}
                                    </p>

                                    {/* Connecting Line (hidden on mobile, shown on desktop except for last item) */}
                                    {index < steps.length - 1 && (
                                        <div className="hidden lg:block absolute top-1/2 -right-4 w-8 h-0.5 bg-gradient-to-r from-primary/50 to-transparent" />
                                    )}
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
                    className="text-center mt-16"
                >
                    <p className="text-muted-foreground mb-4">
                        Подготвени да започнете?
                    </p>
                    <a
                        href="/auth/register"
                        className="inline-flex items-center justify-center px-8 py-3 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground font-medium transition-all duration-300 shadow-[0_0_30px_rgba(124,58,237,0.5)] hover:shadow-[0_0_50px_rgba(124,58,237,0.7)]"
                    >
                        Започни бесплатно денес
                    </a>
                </motion.div>
            </div>
        </section>
    );
}
