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
    "А", "Б", "В", "Г", "Д", "Е", "Ж", "З", "И", "К", "Л", "М",
    "Н", "О", "П", "Р", "С", "Т", "У", "Ф", "Х", "Ц", "Ч", "Ш"
];

const companySuffixes = ["ДОО", "ДООЕЛ", "ООД", "АД"];

const actions = [
    { text: "се претплати на Enterprise пакет", icon: Sparkles },
    { text: "се претплати на Pro пакет", icon: Sparkles },
    { text: "се приклучи", icon: UserPlus },
    { text: "ја освои својата прва понуда", icon: Trophy },
    { text: "започна бесплатен пробен период", icon: CheckCircle },
    { text: "се претплати на Premium пакет", icon: Sparkles },
];

const timeIntervals = [
    "пред 5 минути",
    "пред 15 минути",
    "пред 30 минути",
    "пред 45 минути",
    "пред 1 час",
    "пред 2 часа",
    "пред 3 часа",
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

export default function SocialProofNotifications() {
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
                            className="bg-white/10 backdrop-blur-xl border border-white/20 rounded-lg p-4 shadow-2xl max-w-sm"
                        >
                            <div className="flex items-start gap-3">
                                <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                                    <Icon className="w-5 h-5 text-primary" />
                                </div>
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm font-medium text-white">
                                        {notification.company}
                                    </p>
                                    <p className="text-xs text-gray-300 mt-0.5">
                                        {notification.action}
                                    </p>
                                    <p className="text-xs text-gray-400 mt-1">
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
