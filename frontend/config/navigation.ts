import { LayoutDashboard, Search, TrendingUp, Mail, MessageSquare, Settings, Package, ShoppingCart } from 'lucide-react';

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
    name: 'Конкуренти',
    href: '/competitors',
    icon: TrendingUp,
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
