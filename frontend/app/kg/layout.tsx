import type { Metadata } from "next";
import Link from "next/link";
import "../globals.css";

export const metadata: Metadata = {
  title: "Zakupki.KG — Портал государственных закупок Кыргызстана",
  description:
    "Мониторинг государственных закупок Кыргызской Республики: тендеры, объявления, победители контрактов. Ежедневная рассылка IT-тендеров.",
  robots: { index: true, follow: true },
  openGraph: {
    title: "Zakupki.KG — Портал государственных закупок",
    description: "Тендеры Кыргызстана в одном месте. Поиск, фильтры, ежедневные уведомления.",
    locale: "ru_RU",
    type: "website",
  },
};

export default function KGLayout({ children }: { children: React.ReactNode }) {
  return (
    <div lang="ru" className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <Link href="/kg" className="flex items-center gap-2">
              <span className="text-2xl">🇰🇬</span>
              <span className="font-bold text-lg text-gray-900">Zakupki.KG</span>
            </Link>
            <nav className="hidden sm:flex items-center gap-6 text-sm">
              <Link href="/kg" className="text-gray-700 hover:text-blue-600">Главная</Link>
              <Link href="/kg/tenders" className="text-gray-700 hover:text-blue-600">Тендеры</Link>
              <Link href="/kg/alerts" className="text-gray-700 hover:text-blue-600">Подписка</Link>
              <Link href="/" className="text-xs text-gray-500 hover:text-gray-700">MK: nabavkidata.com</Link>
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">{children}</main>

      <footer className="mt-16 border-t border-gray-200 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 text-sm text-gray-600">
          <div className="flex flex-col sm:flex-row justify-between gap-4">
            <div>
              <p className="font-medium text-gray-900">Zakupki.KG</p>
              <p>Независимый мониторинг государственных закупок Кыргызстана</p>
            </div>
            <div>
              <p>Данные из открытых источников: goszakupki.okmot.kg и zakupki.gov.kg</p>
              <p className="text-xs mt-1">© 2026 · Проект команды Nabavkidata.com</p>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
