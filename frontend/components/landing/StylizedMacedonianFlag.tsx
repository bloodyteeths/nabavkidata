"use client";

import { motion } from "framer-motion";

export default function StylizedMacedonianFlag({ className }: { className?: string }) {
    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className={`relative group cursor-default ${className}`}
        >
            {/* Glow Effect */}
            <div className="absolute -inset-4 bg-red-600/20 rounded-full blur-xl group-hover:bg-red-600/30 transition-all duration-500" />

            {/* Flag Container */}
            <div className="relative w-16 h-10 md:w-20 md:h-12 rounded-lg overflow-hidden shadow-2xl border border-white/10 bg-gradient-to-br from-red-700 to-red-900">
                {/* Sun Center */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                    <div className="w-3 h-3 md:w-4 md:h-4 bg-yellow-400 rounded-full shadow-[0_0_10px_rgba(250,204,21,0.8)]" />
                </div>

                {/* Rays Container */}
                <div className="absolute inset-0 flex items-center justify-center">
                    {/* Vertical Ray */}
                    <div className="absolute w-1 md:w-1.5 h-full bg-yellow-400/90 [clip-path:polygon(20%_0%,80%_0%,100%_100%,0%_100%)]" />

                    {/* Horizontal Ray */}
                    <div className="absolute h-1 md:h-1.5 w-full bg-yellow-400/90 [clip-path:polygon(0%_20%,100%_0%,100%_100%,0%_80%)]" />

                    {/* Diagonal Rays */}
                    <div className="absolute w-full h-1 md:h-1.5 bg-yellow-400/90 rotate-45 [clip-path:polygon(0%_0%,100%_20%,100%_80%,0%_100%)]" />
                    <div className="absolute w-full h-1 md:h-1.5 bg-yellow-400/90 -rotate-45 [clip-path:polygon(0%_0%,100%_20%,100%_80%,0%_100%)]" />

                    {/* Refined Rays (Trying to mimic the actual flag's widening rays) */}
                    {/* Top */}
                    <div className="absolute top-0 left-1/2 -translate-x-1/2 w-4 md:w-6 h-[50%] bg-gradient-to-b from-yellow-400 to-transparent [clip-path:polygon(0%_0%,100%_0%,50%_100%)]" />
                    {/* Bottom */}
                    <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-4 md:w-6 h-[50%] bg-gradient-to-t from-yellow-400 to-transparent [clip-path:polygon(0%_100%,100%_100%,50%_0%)]" />
                    {/* Left */}
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 h-4 md:h-6 w-[50%] bg-gradient-to-r from-yellow-400 to-transparent [clip-path:polygon(0%_0%,0%_100%,100%_50%)]" />
                    {/* Right */}
                    <div className="absolute right-0 top-1/2 -translate-y-1/2 h-4 md:h-6 w-[50%] bg-gradient-to-l from-yellow-400 to-transparent [clip-path:polygon(100%_0%,100%_100%,0%_50%)]" />

                    {/* Diagonals */}
                    <div className="absolute w-[140%] h-3 md:h-4 bg-gradient-to-r from-transparent via-yellow-400/80 to-transparent rotate-45" />
                    <div className="absolute w-[140%] h-3 md:h-4 bg-gradient-to-r from-transparent via-yellow-400/80 to-transparent -rotate-45" />
                </div>

                {/* Glass Shine */}
                <div className="absolute inset-0 bg-gradient-to-tr from-white/10 to-transparent opacity-50" />
            </div>
        </motion.div>
    );
}
