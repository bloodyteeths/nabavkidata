import { LayoutDashboard, Search, TrendingUp, Mail, MessageSquare, Settings } from 'lucide-react';

export const navigation = [
  {
    name: 'Табла',
    href: '/',
    icon: LayoutDashboard,
  },
  {
    name: 'Тендери',
    href: '/tenders',
    icon: Search,
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
