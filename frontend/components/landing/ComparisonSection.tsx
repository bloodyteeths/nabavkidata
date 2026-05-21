"use client";

import { motion } from "framer-motion";
import { Check, X, Minus, Clock } from "lucide-react";

const rows = [
    { feature: "Пребарување тендери", enabavki: true, nabavki: true },
    { feature: "Пребарување по клучен збор", enabavki: true, nabavki: true },
    { feature: "Филтрирање по категорија", enabavki: "основно", nabavki: true },
    { feature: "Историски цени на победници", enabavki: false, nabavki: true },
    { feature: "Win rate и историја на конкуренти", enabavki: false, nabavki: true },
    { feature: "AI чита тендерски документи", enabavki: false, nabavki: true },
    { feature: "Алерти за нови тендери", enabavki: false, nabavki: true },
    { feature: "Профили на добавувачи", enabavki: false, nabavki: true },
    { feature: "Прашања на македонски", enabavki: false, nabavki: true },
    { feature: "Анализа на ризик и корупција", enabavki: false, nabavki: true },
    { feature: "Време за наоѓање тендери", enabavki: "3-5 часа", nabavki: "10 секунди" },
];

const timeSavings = [
    { task: "Најди релевантни тендери", manual: "2-3 часа", withAI: "10 секунди" },
    { task: "Анализирај конкурент", manual: "1-2 дена", withAI: "30 секунди" },
    { task: "Добиј историја на цени", manual: "Невозможно", withAI: "Инстант" },
    { task: "Прочитај 100 документи", manual: "1 недела", withAI: "1 минута" },
    { task: "Следи пазарни трендови", manual: "Невозможно", withAI: "Реално време" },
];

function CellIcon({ value }: { value: boolean | string }) {
    if (value === true) return <Check className="w-4 h-4 text-green-500" />;
    if (value === false) return <X className="w-4 h-4 text-red-400" />;
    if (value === "основно") return <Minus className="w-4 h-4 text-amber-400" />;
    return <span className="text-xs text-muted-foreground">{value}</span>;
}

export default function ComparisonSection() {
    return (
        <section id="comparison" className="py-16 relative overflow-hidden">
            <div className="container px-4 md:px-6">
                {/* Head-to-head comparison */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="text-center mb-10"
                >
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        Зошто не само <span className="text-gradient">е-набавки</span>?
                    </h2>
                    <p className="text-muted-foreground max-w-2xl mx-auto text-lg">
                        е-набавки ги листа тендерите. Ние ви помагаме да ги победите.
                    </p>
                </motion.div>

                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: 0.1 }}
                    className="max-w-2xl mx-auto mb-16"
                >
                    <div className="rounded-2xl border border-border bg-foreground/5 overflow-hidden">
                        {/* Header */}
                        <div className="grid grid-cols-[1fr_80px_80px] md:grid-cols-[1fr_120px_120px] bg-foreground/5 border-b border-border">
                            <div className="p-3 md:p-4" />
                            <div className="p-3 md:p-4 text-center text-xs md:text-sm font-medium text-muted-foreground">
                                е-набавки
                            </div>
                            <div className="p-3 md:p-4 text-center text-xs md:text-sm font-bold text-primary">
                                NabavkiData
                            </div>
                        </div>

                        {/* Rows */}
                        {rows.map((row, index) => (
                            <div
                                key={index}
                                className={`grid grid-cols-[1fr_80px_80px] md:grid-cols-[1fr_120px_120px] ${
                                    index < rows.length - 1 ? "border-b border-border" : ""
                                } ${index % 2 === 0 ? "" : "bg-foreground/[0.02]"}`}
                            >
                                <div className="p-3 md:p-4 text-xs md:text-sm text-foreground">
                                    {row.feature}
                                </div>
                                <div className="p-3 md:p-4 flex items-center justify-center">
                                    <CellIcon value={row.enabavki} />
                                </div>
                                <div className="p-3 md:p-4 flex items-center justify-center">
                                    <CellIcon value={row.nabavki} />
                                </div>
                            </div>
                        ))}
                    </div>

                    <p className="text-center text-xs text-muted-foreground mt-4">
                        Ги повлекуваме податоците од е-набавки.гов.мк — потоа додаваме интелигенција.
                    </p>
                </motion.div>

                {/* Time Savings Table */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="max-w-4xl mx-auto"
                >
                    <div className="flex items-center justify-center gap-2 mb-6">
                        <Clock className="w-5 h-5 text-primary" />
                        <h3 className="text-2xl font-bold text-foreground">Заштедете Време</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full rounded-xl overflow-hidden">
                            <thead>
                                <tr className="bg-foreground/10">
                                    <th className="px-4 py-3 text-left text-sm font-semibold text-muted-foreground">Задача</th>
                                    <th className="px-4 py-3 text-center text-sm font-semibold text-red-400">Рачно</th>
                                    <th className="px-4 py-3 text-center text-sm font-semibold text-primary">Со NabavkiData</th>
                                </tr>
                            </thead>
                            <tbody>
                                {timeSavings.map((item, index) => (
                                    <tr key={index} className="border-t border-foreground/5 hover:bg-foreground/5 transition-colors">
                                        <td className="px-4 py-3 text-sm text-muted-foreground">{item.task}</td>
                                        <td className="px-4 py-3 text-center text-sm text-red-400">{item.manual}</td>
                                        <td className="px-4 py-3 text-center text-sm font-bold text-primary">{item.withAI}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
