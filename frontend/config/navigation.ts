import { LayoutDashboard, Search, MessageSquare, Settings, ShoppingCart, Building2, LineChart, Users, Bell, ShieldAlert, Swords, Bookmark } from 'lucide-react';

export interface NavItem {
  name: string;
  href: string;
  icon: any;
  description?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
  collapsible?: boolean;
}

export const navigationGroups: NavGroup[] = [
  {
    label: 'Главно',
    items: [
      { name: 'Табла', href: '/dashboard', icon: LayoutDashboard, description: 'Преглед на вашата активност' },
      { name: 'Тендери', href: '/tenders', icon: Search, description: 'Пребарувајте јавни набавки' },
      { name: 'Pipeline', href: '/pipeline', icon: Bookmark, description: 'Следете ги вашите понуди' },
      { name: 'Алерти', href: '/alerts', icon: Bell, description: 'Известувања за нови тендери' },
      { name: 'AI Асистент', href: '/chat', icon: MessageSquare, description: 'Прашајте за тендери, добијте совети' },
    ],
  },
  {
    label: 'Разузнавање',
    items: [
      { name: 'Добавувачи', href: '/suppliers', icon: Building2, description: 'Профили на компании и историја' },
      { name: 'Конкуренти', href: '/competitors', icon: Swords, description: 'Анализирајте ги конкурентите' },
      { name: 'e-Пазар', href: '/epazar', icon: ShoppingCart, description: 'Цени на производи и услуги' },
      { name: 'Трендови', href: '/trends', icon: LineChart, description: 'Пазарни трендови и анализи' },
      { name: 'Анализа на Ризик', href: '/risk-analysis', icon: ShieldAlert, description: 'Ризик и транспарентност' },
    ],
  },
];

// Flat list for backward compatibility
export const navigation = navigationGroups.flatMap(g => g.items).concat([
  { name: 'Поставки', href: '/settings', icon: Settings },
]);
