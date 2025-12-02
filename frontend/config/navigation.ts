import { LayoutDashboard, Search, TrendingUp, Mail, MessageSquare, Settings, Package, ShoppingCart, Building2, BarChart3, LineChart, Users, Bell } from 'lucide-react';

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
    name: 'Аналитика',
    href: '/analytics',
    icon: BarChart3,
  },
  {
    name: 'Конкуренти',
    href: '/competitors',
    icon: Users,
  },
  {
    name: 'Трендови',
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
