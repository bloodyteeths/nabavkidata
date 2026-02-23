"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Globe } from "lucide-react";
import { useState } from "react";
import Image from "next/image";
import { ThemeToggle } from "@/components/ui/theme-toggle";

export default function Navbar() {
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

    const menuItems = [
        { href: "#features", label: "Можности" },
        { href: "#comparison", label: "Предности" },
        { href: "#pricing", label: "Цени" },
        { href: "/contact", label: "Контакт" },
    ];

    return (
        <>
            <motion.nav
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 md:px-6 py-4 glass"
            >
                <Link href="/" className="flex items-center gap-2">
                    <Image
                        src="/logo.png"
                        alt="nabavkidata"
                        width={32}
                        height={32}
                        className="w-8 h-8"
                    />
                    <span className="text-lg md:text-xl font-bold tracking-tight text-foreground">nabavkidata</span>
                </Link>

                {/* Desktop Menu */}
                <div className="hidden md:flex items-center gap-8">
                    {menuItems.map((item) => (
                        <Link
                            key={item.href}
                            href={item.href}
                            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
                        >
                            {item.label}
                        </Link>
                    ))}
                </div>

                {/* Desktop Auth Buttons + Language Switch */}
                <div className="hidden md:flex items-center gap-4">
                    {/* Language Switch */}
                    <Link
                        href="/sr"
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-foreground/10 transition-colors"
                        title="Srpski"
                        aria-label="Префрли на српски јазик"
                    >
                        <Globe className="w-4 h-4" />
                        <span>SR</span>
                    </Link>
                    <ThemeToggle className="text-muted-foreground hover:text-foreground hover:bg-foreground/10" />
                    <Link href="/auth/login">
                        <Button variant="ghost" className="text-foreground hover:text-foreground hover:bg-foreground/10" aria-label="Најави се">
                            Најава
                        </Button>
                    </Link>
                    <Link href="/auth/register">
                        <Button className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_20px_rgba(124,58,237,0.5)]" aria-label="Започни бесплатна регистрација">
                            Започни Бесплатно
                        </Button>
                    </Link>
                </div>

                {/* Mobile Actions */}
                <div className="md:hidden flex items-center gap-3">
                    <Link href="/auth/register">
                        <Button size="sm" className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_10px_rgba(124,58,237,0.3)] px-4" aria-label="Започни регистрација">
                            Започни
                        </Button>
                    </Link>
                    <ThemeToggle className="text-muted-foreground hover:text-foreground" />
                    <button
                        onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                        className="p-2 text-foreground hover:bg-foreground/10 rounded-lg transition-colors"
                        aria-label="Toggle menu"
                    >
                        {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                    </button>
                </div>
            </motion.nav>

            {/* Mobile Menu */}
            <AnimatePresence>
                {mobileMenuOpen && (
                    <motion.div
                        initial={{ opacity: 0, x: "100%" }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: "100%" }}
                        transition={{ type: "spring", damping: 25, stiffness: 200 }}
                        className="fixed top-[72px] right-0 bottom-0 w-full sm:w-80 bg-background/95 backdrop-blur-xl border-l border-border z-40 md:hidden"
                    >
                        <div className="flex flex-col h-full p-6">
                            {/* Menu Items */}
                            <nav className="flex flex-col gap-4 mb-8">
                                {menuItems.map((item, index) => (
                                    <motion.div
                                        key={item.href}
                                        initial={{ opacity: 0, x: 20 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        transition={{ delay: index * 0.1 }}
                                    >
                                        <Link
                                            href={item.href}
                                            onClick={() => setMobileMenuOpen(false)}
                                            className="block px-4 py-3 text-lg font-medium text-muted-foreground hover:text-foreground hover:bg-foreground/5 rounded-lg transition-colors"
                                        >
                                            {item.label}
                                        </Link>
                                    </motion.div>
                                ))}
                                {/* Mobile Language Switch */}
                                <motion.div
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.3 }}
                                >
                                    <Link
                                        href="/sr"
                                        onClick={() => setMobileMenuOpen(false)}
                                        className="flex items-center gap-2 px-4 py-3 text-lg font-medium text-muted-foreground hover:text-foreground hover:bg-foreground/5 rounded-lg transition-colors"
                                    >
                                        <Globe className="w-5 h-5" />
                                        <span>Srpski (SR)</span>
                                    </Link>
                                </motion.div>
                            </nav>

                            {/* Auth Buttons */}
                            <div className="flex flex-col gap-3 mt-auto">
                                <Link href="/auth/login" onClick={() => setMobileMenuOpen(false)}>
                                    <Button variant="outline" className="w-full h-12 text-foreground border-border hover:bg-foreground/10" aria-label="Најави се">
                                        Најава
                                    </Button>
                                </Link>
                                <Link href="/auth/register" onClick={() => setMobileMenuOpen(false)}>
                                    <Button className="w-full h-12 bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_20px_rgba(124,58,237,0.5)]" aria-label="Започни бесплатна регистрација">
                                        Започни Бесплатно
                                    </Button>
                                </Link>
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </>
    );
}
