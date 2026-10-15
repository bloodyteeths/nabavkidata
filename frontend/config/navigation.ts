import { LayoutDashboard, Search, MessageSquare, HelpCircle, Settings, ShoppingCart, Building2, LineChart, Users, Bell, ShieldAlert, Swords, Bookmark, Home, FileText, FolderOpen, CalendarDays, CreditCard } from 'lucide-react';

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
      { name: 'Прашања за тендери', href: '/chat', icon: HelpCircle, description: 'Основни одговори од нашата база' },
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

/** Sidebar for bid-service clients (prospect / managed_client). */
export const portalNavigationGroups: NavGroup[] = [
  {
    label: 'Портал',
    items: [
      { name: 'Почетна', href: '/portal', icon: Home, description: 'Преглед на вашите понуди' },
      { name: 'Мои понуди', href: '/portal/bids', icon: FileText, description: 'Сите понуди што ги подготвуваме' },
      { name: 'Тендери за мене', href: '/portal/tenders', icon: Search, description: 'Тендери што одговараат на вашиот профил' },
      { name: 'Документи', href: '/portal/documents', icon: FolderOpen, description: 'Документи на компанијата' },
      { name: 'Пораки', href: '/portal/messages', icon: MessageSquare, description: 'Пишете ни' },
      { name: 'Прашања за тендери', href: '/chat', icon: HelpCircle, description: 'Основни одговори од нашата база' },
      { name: 'Календар', href: '/portal/calendar', icon: CalendarDays, description: 'Рокови за поднесување' },
      { name: 'Плаќање', href: '/portal/billing', icon: CreditCard, description: 'Картичка и надомест за успех' },
      { name: 'Поставки', href: '/settings', icon: Settings, description: 'Профил и поставки' },
    ],
  },
];

/** Extra tools shown to portal users who are clients (managed_client): perks included with the service. */
export const portalToolsGroup: NavGroup = {
  label: 'Алатки',
  items: [
    { name: 'Тендери', href: '/tenders', icon: Search, description: 'Пребарувајте јавни набавки' },
    { name: 'Конкуренти', href: '/competitors', icon: Swords, description: 'Анализирајте ги конкурентите' },
    { name: 'Цени', href: '/products', icon: ShoppingCart, description: 'Цени на производи и услуги' },
  ],
};

// Flat list for backward compatibility
export const navigation = navigationGroups.flatMap(g => g.items).concat([
  { name: 'Поставки', href: '/settings', icon: Settings },
]);
