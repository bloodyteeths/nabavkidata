"use client";

import { motion } from "framer-motion";
import { ArrowRight, Building2, Trophy, PoundSterling } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { formatCurrency } from "@/lib/utils";

interface FeaturedAward {
    tender_id: string;
    title: string;
    procuring_entity: string;
    winner: string;
    estimated_value_mkd: number;
    publication_date: string;
    category: string;
}

export default function SocialProofSection() {
    const [awards, setAwards] = useState<FeaturedAward[]>([]);

    useEffect(() => {
        fetch(`${process.env.NEXT_PUBLIC_API_URL || ""}/api/tenders?status=awarded&limit=6&sort=publication_date&order=desc`)
            .then((r) => r.json())
            .then((data) => {
                const items = (data.items || data.results || [])
                    .filter((t: FeaturedAward) => t.winner && t.estimated_value_mkd && t.estimated_value_mkd > 100000)
                    .slice(0, 6);
                setAwards(items);
            })
            .catch(() => {});
    }, []);

    if (awards.length === 0) return null;

    return (
        <section className="py-16 relative overflow-hidden">
            <div className="container px-4 md:px-6">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="text-center mb-10"
                >
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        Видете што победниците <span className="text-gradient">навистина понудиле</span>
                    </h2>
                    <p className="text-muted-foreground max-w-2xl mx-auto text-lg">
                        Реални доделени тендери од е-набавки.гов.мк — податоците до кои добивате пристап.
                    </p>
                </motion.div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-w-5xl mx-auto">
                    {awards.map((award, index) => (
                        <motion.div
                            key={award.tender_id}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                        >
                            <Link
                                href={`/tenders/${award.tender_id}`}
                                className="block p-5 rounded-xl bg-foreground/5 border border-border hover:border-primary/30 hover:bg-foreground/10 transition-all group h-full"
                            >
                                <p className="text-xs font-medium text-primary uppercase tracking-wider mb-2">
                                    {award.category || "Услуги"}
                                </p>
                                <h3 className="text-sm font-semibold text-foreground mb-3 line-clamp-2 leading-snug">
                                    {award.title}
                                </h3>

                                <div className="space-y-2 text-xs text-muted-foreground">
                                    <div className="flex items-center gap-1.5">
                                        <Building2 className="w-3 h-3 text-muted-foreground/60 flex-shrink-0" />
                                        <span className="truncate">{award.procuring_entity}</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <Trophy className="w-3 h-3 text-muted-foreground/60 flex-shrink-0" />
                                        <span className="truncate">{award.winner}</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                        <PoundSterling className="w-3 h-3 text-muted-foreground/60 flex-shrink-0" />
                                        <span className="font-semibold text-foreground">{formatCurrency(award.estimated_value_mkd)}</span>
                                    </div>
                                </div>

                                <div className="mt-3 pt-3 border-t border-border">
                                    <span className="text-xs text-primary font-medium group-hover:underline flex items-center gap-1">
                                        Видете детали <ArrowRight className="w-3 h-3" />
                                    </span>
                                </div>
                            </Link>
                        </motion.div>
                    ))}
                </div>

                <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    className="text-center mt-8"
                >
                    <Link
                        href="/tenders?status=awarded"
                        className="inline-flex items-center gap-2 text-primary hover:underline font-medium"
                    >
                        Пребарајте 170,000+ тендери <ArrowRight className="w-4 h-4" />
                    </Link>
                </motion.div>
            </div>
        </section>
    );
}
