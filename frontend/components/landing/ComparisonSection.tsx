"use client";

import { motion } from "framer-motion";
import { Check, X, AlertCircle, Clock } from "lucide-react";

const timeSavings = [
    { task: "Најди релевантни тендери", manual: "2-3 часа", withAI: "10 секунди" },
    { task: "Анализирај конкурент", manual: "1-2 дена", withAI: "30 секунди" },
    { task: "Добиј историја на цени", manual: "Невозможно", withAI: "Инстант" },
    { task: "Прочитај 100 документи", manual: "1 недела", withAI: "1 минута" },
    { task: "Следи пазарни трендови", manual: "Невозможно", withAI: "Реално време" }
];

export default function ComparisonSection() {
    return (
        <section id="comparison" className="py-24 bg-white/5">
            <div className="container px-4 md:px-6">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        Зошто сме <span className="text-gradient">100 чекори понапред</span>?
                    </h2>
                    <p className="text-gray-400 max-w-2xl mx-auto text-lg">
                        Не дозволувајте застарените методи да ве кочат. Видете ја разликата.
                    </p>
                </div>

                {/* Time Savings Table */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="mb-16 max-w-4xl mx-auto"
                >
                    <div className="flex items-center justify-center gap-2 mb-6">
                        <Clock className="w-5 h-5 text-primary" />
                        <h3 className="text-2xl font-bold text-white">Заштедете Време</h3>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full rounded-xl overflow-hidden">
                            <thead>
                                <tr className="bg-white/10">
                                    <th className="px-4 py-3 text-left text-sm font-semibold text-gray-300">Задача</th>
                                    <th className="px-4 py-3 text-center text-sm font-semibold text-red-400">Рачно</th>
                                    <th className="px-4 py-3 text-center text-sm font-semibold text-primary">Со AI</th>
                                </tr>
                            </thead>
                            <tbody>
                                {timeSavings.map((item, index) => (
                                    <tr key={index} className="border-t border-white/5 hover:bg-white/5 transition-colors">
                                        <td className="px-4 py-3 text-sm text-gray-300">{item.task}</td>
                                        <td className="px-4 py-3 text-center text-sm text-red-400">{item.manual}</td>
                                        <td className="px-4 py-3 text-center text-sm font-bold text-primary">{item.withAI}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </motion.div>

                {/* Three-Way Comparison */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 max-w-6xl mx-auto mb-12">
                    {/* Manual Methods */}
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        className="p-6 md:p-8 rounded-2xl bg-red-500/5 border border-red-500/20"
                    >
                        <h3 className="text-xl md:text-2xl font-bold mb-6 text-red-400">Рачни Методи</h3>
                        <ul className="space-y-3">
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <X className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                Рачно читање на 50+ страни PDF
                            </li>
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <X className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                Погодување на цени на конкуренти
                            </li>
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <X className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                Пропуштени рокови и шанси
                            </li>
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <X className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                Нема историски податоци
                            </li>
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <X className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                                Комплексен и бавен процес
                            </li>
                        </ul>
                    </motion.div>

                    {/* ChatGPT */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        className="p-6 md:p-8 rounded-2xl bg-yellow-500/5 border border-yellow-500/20"
                    >
                        <h3 className="text-xl md:text-2xl font-bold mb-6 text-yellow-400">ChatGPT</h3>
                        <ul className="space-y-3">
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <X className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                                Нема пристап до тендерски документи
                            </li>
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <X className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                                Не може да чита PDF од e-nabavki
                            </li>
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <X className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                                Нема историски податоци за цени
                            </li>
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <X className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                                Не знае за македонски компании
                            </li>
                            <li className="flex items-start gap-3 text-gray-400 text-sm">
                                <AlertCircle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                                Општи одговори без контекст
                            </li>
                        </ul>
                    </motion.div>

                    {/* NabavkiData */}
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        className="p-6 md:p-8 rounded-2xl bg-primary/10 border border-primary/50 relative overflow-hidden"
                    >
                        <div className="absolute top-0 right-0 px-3 py-1 bg-primary text-white text-xs font-bold rounded-bl-lg">
                            ПРЕПОРАЧАНО
                        </div>
                        <h3 className="text-xl md:text-2xl font-bold mb-6 text-primary">NabavkiData</h3>
                        <ul className="space-y-3">
                            <li className="flex items-start gap-3 text-white text-sm">
                                <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                                31,592 документи скрепирани и индексирани
                            </li>
                            <li className="flex items-start gap-3 text-white text-sm">
                                <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                                AI чита секој PDF и го зачувува во база
                            </li>
                            <li className="flex items-start gap-3 text-white text-sm">
                                <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                                Историја на цени за 7,597 производи
                            </li>
                            <li className="flex items-start gap-3 text-white text-sm">
                                <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                                Податоци за 1,873 компании
                            </li>
                            <li className="flex items-start gap-3 text-white text-sm">
                                <Check className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                                Специјализирана за македонски јавни набавки
                            </li>
                        </ul>
                    </motion.div>
                </div>

                {/* Callout Box */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="max-w-3xl mx-auto p-6 md:p-8 rounded-2xl bg-gradient-to-r from-primary/20 to-purple-500/20 border border-primary/30"
                >
                    <div className="flex items-start gap-4">
                        <div className="w-10 h-10 rounded-full bg-primary/30 flex items-center justify-center flex-shrink-0">
                            <AlertCircle className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                            <h4 className="text-lg md:text-xl font-bold text-white mb-2">
                                Зошто ChatGPT не може да го направи ова?
                            </h4>
                            <p className="text-sm md:text-base text-gray-300 leading-relaxed">
                                ChatGPT нема пристап до вашите тендерски документи. Ние скрепираме секој документ од e-nabavki и e-pazar, го екстрактираме содржината и ја зачувуваме во наша база. Нашиот AI го чита овој реален содржина и ви дава точни одговори базирани на вистински податоци, не општи претпоставки.
                            </p>
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}
