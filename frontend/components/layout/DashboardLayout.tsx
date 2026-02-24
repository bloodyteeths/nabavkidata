"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { navigationGroups } from "@/config/navigation";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { LogOut, Settings, User, Menu, X } from "lucide-react";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { NotificationBell } from "@/components/notifications/NotificationBell";
import { GlobalChatWidget } from "@/components/ai/GlobalChatWidget";
import { useState } from "react";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const { user, logout, isAuthenticated } = useAuth();
    const pathname = usePathname();
    const router = useRouter();
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    const handleLogout = async () => {
        await logout();
        router.push('/auth/login');
    };

    const getUserInitials = () => {
        if (!user?.full_name) return "U";
        const names = user.full_name.split(" ");
        return names.length > 1
            ? `${names[0][0]}${names[1][0]}`.toUpperCase()
            : names[0][0].toUpperCase();
    };

    const SidebarContent = () => (
        <>
            <div className="p-6">
                <Link href="/dashboard" className="flex items-center gap-2 mb-1 hover:opacity-80 transition-opacity">
                    <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                        <span className="text-white font-bold text-xl">N</span>
                    </div>
                    <h1 className="text-xl font-bold text-foreground tracking-tight">nabavkidata</h1>
                </Link>
                <p className="text-xs text-muted-foreground ml-10">Тендер Интелигенција</p>
            </div>

            <nav className="flex-1 px-4 space-y-4 overflow-y-auto">
                {navigationGroups.map((group) => (
                    <div key={group.label}>
                        <p className="px-3 mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                            {group.label}
                        </p>
                        <div className="space-y-0.5">
                            {group.items.map((item) => {
                                const Icon = item.icon;
                                const isActive = pathname === item.href;
                                return (
                                    <Link
                                        key={item.name}
                                        href={item.href}
                                        onClick={() => setIsMobileMenuOpen(false)}
                                        className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${isActive
                                            ? "bg-primary text-white shadow-[0_0_20px_rgba(124,58,237,0.3)]"
                                            : "text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
                                            }`}
                                    >
                                        <Icon className="h-5 w-5" />
                                        {item.name}
                                    </Link>
                                );
                            })}
                        </div>
                    </div>
                ))}
                {/* Settings at bottom, separated */}
                <div className="pt-2 border-t border-border/40">
                    <Link
                        href="/settings"
                        onClick={() => setIsMobileMenuOpen(false)}
                        className={`flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${pathname === '/settings'
                            ? "bg-primary text-white shadow-[0_0_20px_rgba(124,58,237,0.3)]"
                            : "text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
                            }`}
                    >
                        <Settings className="h-5 w-5" />
                        Поставки
                    </Link>
                </div>
            </nav>

            <div className="p-4 border-t border-border bg-muted/20">
                <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                        <Button variant="ghost" className="w-full justify-start p-2 hover:bg-foreground/5 rounded-xl">
                            <div className="flex items-center gap-3">
                                <Avatar className="h-8 w-8 border-2 border-primary/20">
                                    <AvatarFallback className="bg-primary/20 text-primary">{getUserInitials()}</AvatarFallback>
                                </Avatar>
                                <div className="flex-1 text-left overflow-hidden">
                                    <p className="text-sm font-medium truncate text-foreground">{user?.full_name || user?.email}</p>
                                    <p className="text-xs text-muted-foreground truncate capitalize">
                                        {user?.subscription_tier} план
                                    </p>
                                </div>
                            </div>
                        </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-56 bg-card/95 backdrop-blur-xl border-border">
                        <DropdownMenuItem onClick={() => router.push('/settings')} className="focus:bg-primary/20 focus:text-foreground cursor-pointer">
                            <Settings className="mr-2 h-4 w-4" />
                            Поставки
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => router.push('/settings')} className="focus:bg-primary/20 focus:text-foreground cursor-pointer">
                            <User className="mr-2 h-4 w-4" />
                            Профил
                        </DropdownMenuItem>
                        <DropdownMenuSeparator className="bg-border" />
                        <DropdownMenuItem onClick={handleLogout} className="text-red-400 focus:bg-red-500/10 focus:text-red-400 cursor-pointer">
                            <LogOut className="mr-2 h-4 w-4" />
                            Одјави се
                        </DropdownMenuItem>
                    </DropdownMenuContent>
                </DropdownMenu>
            </div>
        </>
    );

    return (
        <ProtectedRoute>
            <div className="flex h-screen bg-background">
                {/* Mobile Header */}
                <div className="md:hidden fixed top-0 left-0 right-0 h-16 border-b border-border bg-background/80 backdrop-blur-md z-30 flex items-center justify-between px-4">
                    <Link href="/dashboard" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
                        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
                            <span className="text-white font-bold text-xl">N</span>
                        </div>
                        <span className="font-bold text-foreground">nabavkidata</span>
                    </Link>
                    <div className="flex items-center gap-2">
                        <ThemeToggle />
                        <NotificationBell />
                        <Button variant="ghost" size="icon" onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}>
                            {isMobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
                        </Button>
                    </div>
                </div>

                {/* Desktop Sidebar */}
                <aside className="hidden md:flex w-64 border-r border-border flex-col glass relative z-20">
                    <SidebarContent />
                </aside>

                {/* Desktop Header with Notification Bell */}
                <div className="hidden md:block fixed top-0 right-0 left-64 h-16 border-b border-border bg-background/80 backdrop-blur-md z-20 px-6">
                    <div className="flex items-center justify-end h-full gap-2">
                        <ThemeToggle />
                        <NotificationBell />
                    </div>
                </div>

                {/* Mobile Sidebar Overlay */}
                {isMobileMenuOpen && (
                    <div className="fixed inset-0 z-40 md:hidden">
                        {/* Backdrop */}
                        <div
                            className="absolute inset-0 bg-background/80 backdrop-blur-sm"
                            onClick={() => setIsMobileMenuOpen(false)}
                        />
                        {/* Sidebar */}
                        <aside className="absolute top-16 bottom-0 left-0 w-64 border-r border-border flex flex-col bg-background/95 backdrop-blur-xl animate-in slide-in-from-left">
                            <SidebarContent />
                        </aside>
                    </div>
                )}

                {/* Main Content */}
                <main className="flex-1 overflow-y-auto overflow-x-hidden pt-16 bg-background">
                    {children}
                </main>

                {/* Global AI Chat Widget */}
                <GlobalChatWidget />
            </div>
        </ProtectedRoute>
    );
}

