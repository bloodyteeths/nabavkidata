"use client";

import { motion } from "framer-motion";
import Image from "next/image";

export default function StylizedMacedonianFlag({ className }: { className?: string }) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className={`relative group cursor-default ${className}`}
        >
            {/* Glow Effect */}
            <div className="absolute -inset-2 bg-red-600/10 rounded-lg blur-lg group-hover:bg-red-600/20 transition-all duration-500" />

            {/* Flag Image Container */}
            <div className="relative w-16 h-16 md:w-24 md:h-24 lg:w-28 lg:h-28">
                <Image
                    src="/macedonian-flag.png"
                    alt="Macedonian Flag"
                    fill
                    className="object-contain drop-shadow-2xl"
                    priority
                    sizes="(max-width: 768px) 64px, (max-width: 1024px) 96px, 112px"
                />
            </div>
        </motion.div>
    );
}
