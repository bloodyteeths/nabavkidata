"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";

export default function Navbar() {
    return (
        <motion.nav
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4 glass"
        >
            <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold text-xl">N</span>
                </div>
                <span className="text-xl font-bold tracking-tight text-white">nabavkidata</span>
            </div>

            <div className="hidden md:flex items-center gap-8">
                <Link href="#features" className="text-sm font-medium text-gray-300 hover:text-white transition-colors">
                    Можности
                </Link>
                <Link href="#comparison" className="text-sm font-medium text-gray-300 hover:text-white transition-colors">
                    Предности
                </Link>
                <Link href="#pricing" className="text-sm font-medium text-gray-300 hover:text-white transition-colors">
                    Цени
                </Link>
            </div>

            <div className="flex items-center gap-4">
                <Link href="/auth/login">
                    <Button variant="ghost" className="text-white hover:text-white hover:bg-white/10">
                        Најава
                    </Button>
                </Link>
                <Link href="/auth/register">
                    <Button className="bg-primary hover:bg-primary/90 text-white shadow-[0_0_20px_rgba(124,58,237,0.5)]">
                        Започни Бесплатно
                    </Button>
                </Link>
            </div>
        </motion.nav>
    );
}
