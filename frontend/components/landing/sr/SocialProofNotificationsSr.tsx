"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckCircle, UserPlus, Trophy, Sparkles } from "lucide-react";

interface Notification {
    id: string;
    company: string;
    action: string;
    time: string;
    icon: typeof CheckCircle;
}

const companyPrefixes = [
    "A", "B", "V", "G", "D", "E", "Ž", "Z", "I", "K", "L", "M",
    "N", "O", "P", "R", "S", "T", "U", "F", "H", "C", "Č", "Š"
];

const companySuffixes = ["DOO", "DOOPL", "AD", "OOD"];

const actions = [
    { text: "se pretplatio na Enterprise paket", icon: Sparkles },
    { text: "se pretplatio na Pro paket", icon: Sparkles },
    { text: "se pridružio", icon: UserPlus },
    { text: "je osvojio svoju prvu ponudu", icon: Trophy },
    { text: "je započeo besplatni probni period", icon: CheckCircle },
    { text: "se pretplatio na Premium paket", icon: Sparkles },
];

const timeIntervals = [
    "pre 5 minuta",
    "pre 15 minuta",
    "pre 30 minuta",
    "pre 45 minuta",
    "pre 1 sat",
    "pre 2 sata",
    "pre 3 sata",
];

function generateRandomNotification(): Notification {
    const prefix = companyPrefixes[Math.floor(Math.random() * companyPrefixes.length)];
    const suffix = companySuffixes[Math.floor(Math.random() * companySuffixes.length)];
    const action = actions[Math.floor(Math.random() * actions.length)];
    const time = timeIntervals[Math.floor(Math.random() * timeIntervals.length)];

    return {
        id: `${Date.now()}-${Math.random()}`,
        company: `${prefix}... ${suffix}`,
        action: action.text,
        time,
        icon: action.icon,
    };
}

export default function SocialProofNotificationsSr() {
    const [notifications, setNotifications] = useState<Notification[]>([]);

    useEffect(() => {
        // Show first notification after 5 seconds
        const initialTimeout = setTimeout(() => {
            setNotifications([generateRandomNotification()]);
        }, 5000);

        // Then show notifications at random intervals
        const interval = setInterval(() => {
            const newNotification = generateRandomNotification();
            setNotifications((prev) => {
                // Keep max 3 notifications
                const updated = [...prev, newNotification];
                return updated.slice(-3);
            });

            // Auto-remove after 6 seconds
            setTimeout(() => {
                setNotifications((prev) => prev.filter((n) => n.id !== newNotification.id));
            }, 6000);
        }, Math.random() * 30000 + 15000); // Random between 15-45 seconds

        return () => {
            clearTimeout(initialTimeout);
            clearInterval(interval);
        };
    }, []);

    return (
        <div className="fixed bottom-4 right-4 z-50 space-y-2 pointer-events-none">
            <AnimatePresence>
                {notifications.map((notification) => {
                    const Icon = notification.icon;
                    return (
                        <motion.div
                            key={notification.id}
                            initial={{ opacity: 0, y: 50, scale: 0.8 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, x: 100, scale: 0.8 }}
                            transition={{ duration: 0.3 }}
                            className="bg-foreground/10 backdrop-blur-xl border border-border rounded-lg p-3 md:p-4 shadow-2xl w-64 md:w-80"
                        >
                            <div className="flex items-start gap-2 md:gap-3">
                                <div className="w-8 h-8 md:w-10 md:h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                                    <Icon className="w-4 h-4 md:w-5 md:h-5 text-primary" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-xs md:text-sm font-medium text-foreground">
                                        {notification.company}
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-0.5">
                                        {notification.action}
                                    </p>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        {notification.time}
                                    </p>
                                </div>
                            </div>
                        </motion.div>
                    );
                })}
            </AnimatePresence>
        </div>
    );
}
