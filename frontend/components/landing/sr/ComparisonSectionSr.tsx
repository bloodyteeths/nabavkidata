"use client";

import { motion } from "framer-motion";
import { Check, X } from "lucide-react";

export default function ComparisonSectionSr() {
    return (
        <section id="comparison" className="py-24 bg-white/5">
            <div className="container px-4 md:px-6">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        Zašto smo <span className="text-gradient">100 koraka ispred</span>?
                    </h2>
                    <p className="text-gray-400 max-w-2xl mx-auto text-lg">
                        Ne dozvolite da vas zastarele metode usporavaju. Pogledajte razliku.
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 max-w-5xl mx-auto">
                    {/* Competitors */}
                    <motion.div
                        initial={{ opacity: 0, x: -20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        className="p-8 rounded-2xl bg-red-500/5 border border-red-500/20"
                    >
                        <h3 className="text-2xl font-bold mb-6 text-red-400">Druga Rešenja</h3>
                        <ul className="space-y-4">
                            <li className="flex items-center gap-3 text-gray-400">
                                <X className="w-5 h-5 text-red-500" />
                                Ručna pretraga
                            </li>
                            <li className="flex items-center gap-3 text-gray-400">
                                <X className="w-5 h-5 text-red-500" />
                                Osnovne ključne reči
                            </li>
                            <li className="flex items-center gap-3 text-gray-400">
                                <X className="w-5 h-5 text-red-500" />
                                Bez analize rizika
                            </li>
                            <li className="flex items-center gap-3 text-gray-400">
                                <X className="w-5 h-5 text-red-500" />
                                Zastareli podaci
                            </li>
                            <li className="flex items-center gap-3 text-gray-400">
                                <X className="w-5 h-5 text-red-500" />
                                Komplikovan interfejs
                            </li>
                        </ul>
                    </motion.div>

                    {/* VS Badge */}
                    <div className="hidden lg:flex items-center justify-center">
                        <div className="w-16 h-16 rounded-full bg-white/10 flex items-center justify-center text-2xl font-bold text-white border border-white/20">
                            VS
                        </div>
                    </div>

                    {/* Nabavkidata */}
                    <motion.div
                        initial={{ opacity: 0, x: 20 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        className="p-8 rounded-2xl bg-primary/10 border border-primary/50 relative overflow-hidden"
                    >
                        <div className="absolute top-0 right-0 px-3 py-1 bg-primary text-white text-xs font-bold rounded-bl-lg">
                            PREPORUČENO
                        </div>
                        <h3 className="text-2xl font-bold mb-6 text-primary">Nabavkidata</h3>
                        <ul className="space-y-4">
                            <li className="flex items-center gap-3 text-white">
                                <Check className="w-5 h-5 text-primary" />
                                AI Automatizacija
                            </li>
                            <li className="flex items-center gap-3 text-white">
                                <Check className="w-5 h-5 text-primary" />
                                Semantičko razumevanje
                            </li>
                            <li className="flex items-center gap-3 text-white">
                                <Check className="w-5 h-5 text-primary" />
                                Napredna procena rizika
                            </li>
                            <li className="flex items-center gap-3 text-white">
                                <Check className="w-5 h-5 text-primary" />
                                Real-time ažuriranja
                            </li>
                            <li className="flex items-center gap-3 text-white">
                                <Check className="w-5 h-5 text-primary" />
                                Moderan i jednostavan UI
                            </li>
                        </ul>
                    </motion.div>
                </div>
            </div>
        </section>
    );
}
