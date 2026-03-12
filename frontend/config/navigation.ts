import { LayoutDashboard, Search, TrendingUp, Mail, MessageSquare, Settings, Package, ShoppingCart, Building2, LineChart, Users, Bell, ShieldAlert } from 'lucide-react';

export interface NavItem {
  name: string;
  href: string;
  icon: any;
  /** If true, only show after onboarding wizard is completed */
  requiresOnboarding?: boolean;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navigationGroups: NavGroup[] = [
  {
    label: 'Главно',
    items: [
      { name: 'Табла', href: '/dashboard', icon: LayoutDashboard },
      { name: 'Тендери', href: '/tenders', icon: Search },
      { name: 'Алерти', href: '/alerts', icon: Bell, requiresOnboarding: true },
    ],
  },
  {
    label: 'Пазар',
    items: [
      { name: 'e-Пазар', href: '/epazar', icon: ShoppingCart, requiresOnboarding: true },
      { name: 'Производи', href: '/products', icon: Package },
      { name: 'Добавувачи', href: '/suppliers', icon: Building2, requiresOnboarding: true },
    ],
  },
  {
    label: 'Анализа',
    items: [
      { name: 'Анализа на Ризик', href: '/risk-analysis', icon: ShieldAlert, requiresOnboarding: true },
      { name: 'Конкуренти', href: '/competitors', icon: Users, requiresOnboarding: true },
      { name: 'Бизнис Анализа', href: '/trends', icon: LineChart, requiresOnboarding: true },
    ],
  },
  {
    label: 'Алатки',
    items: [
      { name: 'AI Асистент', href: '/chat', icon: MessageSquare },
      { name: 'Пораки', href: '/inbox', icon: Mail, requiresOnboarding: true },
    ],
  },
];

// Flat list for backward compatibility
export const navigation = navigationGroups.flatMap(g => g.items).concat([
  { name: 'Поставки', href: '/settings', icon: Settings },
]);
