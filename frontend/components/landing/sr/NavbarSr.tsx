"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Globe } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import Image from "next/image";

export default function NavbarSr() {
    const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
    const [countryOpen, setCountryOpen] = useState(false);
    const countryRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClickOutside(e: MouseEvent) {
            if (countryRef.current && !countryRef.current.contains(e.target as Node)) {
                setCountryOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const menuItems = [
        { href: "/sr#features", label: "Mogućnosti" },
        { href: "/sr#comparison", label: "Prednosti" },
        { href: "/sr#pricing", label: "Cene" },
        { href: "/contact", label: "Kontakt" },
    ];

    return (
        <>
            <motion.nav
                initial={{ opacity: 0, y: -20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 md:px-6 py-4 glass"
            >
                <Link href="/sr" className="flex items-center gap-2">
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
                        href="/"
                        className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-foreground/10 transition-colors"
                        title="Makedonski"
                    >
                        <Globe className="w-4 h-4" />
                        <span>MK</span>
                    </Link>
                    {/* Country Switch */}
                    <div className="relative" ref={countryRef}>
                        <button
                            onClick={() => setCountryOpen(!countryOpen)}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm text-muted-foreground hover:text-foreground hover:bg-foreground/10 transition-colors"
                            aria-label="Promeni zemlju"
                        >
                            <span>🇲🇰</span>
                            <span>MK</span>
                            <svg className={`w-3 h-3 transition-transform ${countryOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                        </button>
                        {countryOpen && (
                            <div className="absolute top-full right-0 mt-1 w-36 rounded-lg border border-border bg-background/95 backdrop-blur-xl shadow-lg overflow-hidden z-50">
                                <button
                                    onClick={() => setCountryOpen(false)}
                                    className="flex items-center gap-2 w-full px-3 py-2 text-sm text-foreground bg-foreground/5 font-medium"
                                >
                                    <span>🇲🇰</span>
                                    <span>MK</span>
                                </button>
                                <a
                                    href="https://uk.nabavkidata.com"
                                    className="flex items-center gap-2 w-full px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors"
                                >
                                    <span>🇬🇧</span>
                                    <span>UK</span>
                                </a>
                            </div>
                        )}
                    </div>
                    <Link href="/auth/login">
                        <Button variant="ghost" className="text-foreground hover:text-foreground hover:bg-foreground/10">
                            Prijava
                        </Button>
                    </Link>
                    <Link href="/auth/register">
                        <Button className="bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_20px_rgba(124,58,237,0.5)]">
                            Započni Besplatno
                        </Button>
                    </Link>
                </div>

                {/* Mobile Menu Button */}
                <button
                    onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                    className="md:hidden p-2 text-foreground hover:bg-foreground/10 rounded-lg transition-colors"
                    aria-label="Toggle menu"
                >
                    {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
                </button>
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
                                        href="/"
                                        onClick={() => setMobileMenuOpen(false)}
                                        className="flex items-center gap-2 px-4 py-3 text-lg font-medium text-muted-foreground hover:text-foreground hover:bg-foreground/5 rounded-lg transition-colors"
                                    >
                                        <Globe className="w-5 h-5" />
                                        <span>Makedonski (MK)</span>
                                    </Link>
                                </motion.div>
                                {/* Mobile Country Switch */}
                                <motion.div
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.4 }}
                                >
                                    <div className="px-4 py-3">
                                        <p className="text-xs uppercase tracking-wider text-muted-foreground/60 mb-2">Zemlja</p>
                                        <div className="flex gap-2">
                                            <span className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-foreground bg-foreground/5 rounded-lg">
                                                <span>🇲🇰</span> MK
                                            </span>
                                            <a
                                                href="https://uk.nabavkidata.com"
                                                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-foreground/5 rounded-lg transition-colors"
                                            >
                                                <span>🇬🇧</span> UK
                                            </a>
                                        </div>
                                    </div>
                                </motion.div>
                            </nav>

                            {/* Auth Buttons */}
                            <div className="flex flex-col gap-3 mt-auto">
                                <Link href="/auth/login" onClick={() => setMobileMenuOpen(false)}>
                                    <Button variant="outline" className="w-full h-12 text-foreground border-border hover:bg-foreground/10">
                                        Prijava
                                    </Button>
                                </Link>
                                <Link href="/auth/register" onClick={() => setMobileMenuOpen(false)}>
                                    <Button className="w-full h-12 bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_20px_rgba(124,58,237,0.5)]">
                                        Započni Besplatno
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
