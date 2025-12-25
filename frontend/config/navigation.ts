import { LayoutDashboard, Search, TrendingUp, Mail, MessageSquare, Settings, Package, ShoppingCart, Building2, LineChart, Users, Bell, ShieldAlert } from 'lucide-react';

export const navigation = [
  {
    name: 'Табла',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    name: 'Тендери',
    href: '/tenders',
    icon: Search,
  },
  {
    name: 'e-Пазар',
    href: '/epazar',
    icon: ShoppingCart,
  },
  {
    name: 'Производи',
    href: '/products',
    icon: Package,
  },
  {
    name: 'Добавувачи',
    href: '/suppliers',
    icon: Building2,
  },
  {
    name: 'Анализа на Ризик',
    href: '/risk-analysis',
    icon: ShieldAlert,
  },
  {
    name: 'Конкуренти',
    href: '/competitors',
    icon: Users,
  },
  {
    name: 'Бизнис Анализа',
    href: '/trends',
    icon: LineChart,
  },
  {
    name: 'Алерти',
    href: '/alerts',
    icon: Bell,
  },
  {
    name: 'Пораки',
    href: '/inbox',
    icon: Mail,
  },
  {
    name: 'AI Асистент',
    href: '/chat',
    icon: MessageSquare,
  },
  {
    name: 'Поставки',
    href: '/settings',
    icon: Settings,
  },
];
