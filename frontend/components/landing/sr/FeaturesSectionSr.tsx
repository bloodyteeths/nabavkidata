"use client";

import { motion } from "framer-motion";
import { Brain, Search, Zap, Shield, BarChart3, Bell } from "lucide-react";

const features = [
    {
        icon: Brain,
        title: "Razgovarajte sa Tenderima",
        description: "Postavite pitanje i dobijte odgovor odmah iz dokumentacije, umesto da čitate stotine stranica."
    },
    {
        icon: Search,
        title: "Pametna Pretraga",
        description: "Zaboravite na ključne reči. Naš sistem razume kontekst i pronalazi tendere koji vam zaista odgovaraju."
    },
    {
        icon: Zap,
        title: "Instant Notifikacije",
        description: "Budite prvi koji sazna. Dobijajte obaveštenja u realnom vremenu o novim tenderima i promenama."
    },
    {
        icon: Shield,
        title: "Automatska Ekstrakcija",
        description: "AI čita PDF dokumente i automatski izvlači sve tehničke i finansijske zahteve, štedeći vam sate rada."
    },
    {
        icon: BarChart3,
        title: "Win Factors & Analiza",
        description: "Otkrijte zašto konkurenti pobeđuju. Da li je cena ili kvalitet? Naša AI analiza vam otkriva njihove tajne."
    },
    {
        icon: Bell,
        title: "Automatizacija",
        description: "Automatizujte proces praćenja i apliciranja. Uštedite vreme i resurse."
    }
];

export default function FeaturesSectionSr() {
    return (
        <section id="features" className="py-24 relative overflow-hidden">
            <div className="container px-4 md:px-6">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-5xl font-bold mb-4">
                        <span className="text-gradient">AI Magija</span> u vašoj službi
                    </h2>
                    <p className="text-gray-400 max-w-2xl mx-auto text-lg">
                        Više od običnog pretraživača. Nabavkidata je vaš pametan asistent za javne nabavke.
                    </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                    {features.map((feature, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: index * 0.1 }}
                            className="p-6 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-colors group"
                        >
                            <div className="w-12 h-12 rounded-lg bg-primary/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                                <feature.icon className="w-6 h-6 text-primary" />
                            </div>
                            <h3 className="text-xl font-bold mb-2 text-white">{feature.title}</h3>
                            <p className="text-gray-400">{feature.description}</p>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
