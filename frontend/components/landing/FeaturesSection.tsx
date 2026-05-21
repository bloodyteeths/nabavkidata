"use client";

import { motion } from "framer-motion";
import { MessageSquare, Target, PoundSterling, Shield, FileSearch, Bell } from "lucide-react";

const features = [
    {
        icon: PoundSterling,
        title: "Престанете да нудите наслепо",
        description: "Видете го точниот ценовен ранг што победува — мин, просек, макс од илјадници доделени тендери. Дознајте дали 500.000 МКД е конкурентно за медицински материјали.",
        outcome: "Знајте ја победничката цена пред да понудите"
    },
    {
        icon: Shield,
        title: "Дознајте кој победува и зошто",
        description: "Win rate, историја на победи, пазарен удел по сектор. Видете кои 3 фирми доминираат во вашата категорија — и каде не учествуваат.",
        outcome: "Избегнете битки кои ги губите. Најдете празнини кои ги добивате."
    },
    {
        icon: MessageSquare,
        title: "Прашајте, добијте одговор",
        description: "\"Кои тендери за ИТ опрема се отворени?\" — AI пребарува 170K тендери и 70K документи. Директни одговори, не листа на линкови.",
        outcome: "2 минути наместо 2 часа"
    },
    {
        icon: FileSearch,
        title: "AI чита документи за вас",
        description: "Листи за усогласеност, задолжителни барања, критериуми за евалуација — извлечени од реални тендерски документи. Поставете follow-up: \"Дали ми треба ISO за ова?\"",
        outcome: "Никогаш не губете поради пропуштено барање"
    },
    {
        icon: Target,
        title: "Тендери прилагодени на вашиот бизнис",
        description: "Поставете ја вашата дејност, регион и буџет. AI ги наоѓа тендерите што ги пропуштате на е-набавки — вклучувајќи мали набавки и рамковни договори.",
        outcome: "Релевантни тендери, не шум"
    },
    {
        icon: Bell,
        title: "Нови тендери пред конкурентите",
        description: "Скрепирање на секои 3 часа од е-набавки.гов.мк. Добијте алерт штом се појави релевантен тендер — дневен дигест или инстант.",
        outcome: "Прв знае = прв се подготвува"
    }
];

export default function FeaturesSection() {
    return (
        <section id="features" className="py-16 relative overflow-hidden">
            <div className="container px-4 md:px-6">
                <div className="text-center mb-12">
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        Престанете да погодувате. <span className="text-gradient">Нудете со податоци.</span>
                    </h2>
                    <p className="text-muted-foreground max-w-2xl mx-auto text-lg">
                        Разликата меѓу победа и пораз е знаење на тоа што другите не го знаат.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {features.map((feature, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                            className="p-6 rounded-2xl bg-foreground/5 border border-border hover:bg-foreground/10 transition-colors group"
                        >
                            <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                                <feature.icon className="w-6 h-6 text-primary" />
                            </div>
                            <h3 className="text-xl font-bold mb-2 text-foreground">{feature.title}</h3>
                            <p className="text-muted-foreground text-sm leading-relaxed mb-3">{feature.description}</p>
                            <p className="text-xs font-medium text-primary">{feature.outcome}</p>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
