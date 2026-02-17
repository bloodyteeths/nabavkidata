"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Users } from "lucide-react";

export default function LiveUserCounterSr() {
    const [count, setCount] = useState(4365);
    const [increment, setIncrement] = useState<number | null>(null);

    useEffect(() => {
        const incrementCounter = () => {
            const incrementValue = Math.floor(Math.random() * 3) + 1; // 1-3
            setIncrement(incrementValue);
            setCount((prev) => prev + incrementValue);

            // Hide increment after animation
            setTimeout(() => {
                setIncrement(null);
            }, 2000);
        };

        // Random interval between 10-30 seconds
        const interval = setInterval(() => {
            incrementCounter();
        }, Math.random() * 20000 + 10000);

        return () => clearInterval(interval);
    }, []);

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.5 }}
            className="flex items-center gap-2 px-4 md:px-6 py-2 md:py-3 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm relative"
        >
            <Users className="w-4 h-4 md:w-5 md:h-5 text-primary flex-shrink-0" />
            <span className="text-sm md:text-base text-gray-300">
                <motion.span
                    key={count}
                    initial={{ scale: 1.3, color: "#7c3aed" }}
                    animate={{ scale: 1, color: "#ffffff" }}
                    transition={{ duration: 0.5 }}
                    className="font-semibold notranslate"
                >
                    {count.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".")}+
                </motion.span>
                {" "}kompanija već koristi Nabavkidata
            </span>

            {/* Increment indicator */}
            <AnimatePresence>
                {increment !== null && (
                    <motion.div
                        initial={{ opacity: 0, y: 0, scale: 0.5 }}
                        animate={{ opacity: 1, y: -30, scale: 1 }}
                        exit={{ opacity: 0, y: -50 }}
                        transition={{ duration: 1.5 }}
                        className="absolute -top-8 right-4 text-primary font-bold text-lg"
                    >
                        +{increment}
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}
