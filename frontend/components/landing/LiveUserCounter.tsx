"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Users } from "lucide-react";

export default function LiveUserCounter() {
    const [count, setCount] = useState(4365);
    const [isIncrementing, setIsIncrementing] = useState(false);

    useEffect(() => {
        const incrementCounter = () => {
            const increment = Math.floor(Math.random() * 3) + 1; // 1-3
            setIsIncrementing(true);
            setCount((prev) => prev + increment);

            setTimeout(() => {
                setIsIncrementing(false);
            }, 500);
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
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm"
        >
            <Users className="w-4 h-4 text-primary" />
            <span className="text-sm text-gray-300">
                <motion.span
                    key={count}
                    initial={{ scale: isIncrementing ? 1.2 : 1 }}
                    animate={{ scale: 1 }}
                    transition={{ duration: 0.3 }}
                    className="font-semibold text-white"
                >
                    {count.toLocaleString('mk-MK')}+
                </motion.span>
                {" "}компании веќе користат Nabavkidata
            </span>
        </motion.div>
    );
}
