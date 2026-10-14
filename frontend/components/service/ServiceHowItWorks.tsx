"use client";

import { motion } from "framer-motion";
import { ClipboardCheck, PenLine, FileSignature, Trophy } from "lucide-react";

const steps = [
    {
        icon: ClipboardCheck,
        title: "Бесплатна проценка",
        description:
            "Кажете ни со што се занимава вашата фирма и кои тендери ве интересираат. Проверуваме дали ги исполнувате условите и дали има реална шанса за победа.",
        color: "from-blue-500 to-cyan-500",
    },
    {
        icon: PenLine,
        title: "Ние ја подготвуваме понудата",
        description:
            "Ја читаме целата тендерска документација од е-набавки и ја подготвуваме комплетната понуда: изјави, техничка понуда, финансиска понуда и докази.",
        color: "from-purple-500 to-pink-500",
    },
    {
        icon: FileSignature,
        title: "Вие прегледувате и поднесувате",
        description:
            "Ја добивате готовата понуда навреме пред рокот. Ја прегледувате, ја потпишувате со вашиот сертификат и ја поднесувате на е-набавки.",
        color: "from-amber-500 to-orange-500",
    },
    {
        icon: Trophy,
        title: "Надомест за успех само ако победите",
        description:
            "Ако договорот ви биде доделен, плаќате 5% од вредноста за првата година. Ако не победите, надомест за успех нема.",
        color: "from-green-500 to-emerald-500",
    },
];

export default function ServiceHowItWorks() {
    return (
        <section id="how-it-works" className="py-16 relative overflow-hidden scroll-mt-20">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/10 via-background to-background" />

            <div className="container relative z-10 px-4 md:px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="text-center mb-12"
                >
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        <span className="text-foreground">Како </span>
                        <span className="text-gradient">работи</span>
                    </h2>
                    <p className="text-muted-foreground max-w-2xl mx-auto text-lg">
                        Од тендер што ве интересира до поднесена понуда, без вие да ја пишувате.
                    </p>
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 max-w-6xl mx-auto">
                    {steps.map((step, index) => {
                        const Icon = step.icon;
                        return (
                            <motion.div
                                key={step.title}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.12 }}
                                className="relative group"
                            >
                                <div className="relative h-full p-6 rounded-2xl bg-foreground/5 border border-border backdrop-blur-sm hover:bg-foreground/10 transition-all duration-300">
                                    <div className="absolute -top-4 -left-4 w-12 h-12 rounded-full bg-gradient-to-br from-primary to-purple-600 flex items-center justify-center text-white font-bold text-xl shadow-lg">
                                        {index + 1}
                                    </div>

                                    <div className={`w-14 h-14 rounded-xl bg-gradient-to-br ${step.color} p-3 mb-4 shadow-lg`}>
                                        <Icon className="w-full h-full text-white" />
                                    </div>

                                    <h3 className="text-lg font-semibold text-foreground mb-3">{step.title}</h3>
                                    <p className="text-muted-foreground text-sm leading-relaxed">{step.description}</p>
                                </div>
                            </motion.div>
                        );
                    })}
                </div>
            </div>
        </section>
    );
}
