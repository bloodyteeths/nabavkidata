import { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Категории на јавни набавки (CPV кодови) | NabavkiData',
  description: 'Прегледајте ги сите категории на јавни набавки во Македонија по CPV класификација. Градежништво, медицина, ИТ, транспорт и повеќе.',
  openGraph: {
    title: 'Категории на јавни набавки (CPV кодови)',
    description: 'Прегледајте ги сите категории на јавни набавки во Македонија по CPV класификација.',
    url: 'https://www.nabavkidata.com/categories',
  },
  alternates: {
    canonical: 'https://www.nabavkidata.com/categories',
  },
};

const CPV_CATEGORIES = [
  { code: '45000000', name: 'Градежни работи', icon: '🏗️' },
  { code: '30000000', name: 'Канцелариска и компјутерска опрема', icon: '💻' },
  { code: '31000000', name: 'Електрична опрема и апарати', icon: '⚡' },
  { code: '32000000', name: 'Радио, телевизиска и комуникациска опрема', icon: '📡' },
  { code: '33000000', name: 'Медицинска опрема', icon: '🏥' },
  { code: '34000000', name: 'Транспортна опрема', icon: '🚗' },
  { code: '35000000', name: 'Безбедносна опрема', icon: '🛡️' },
  { code: '39000000', name: 'Мебел, подни и други покривки', icon: '🪑' },
  { code: '44000000', name: 'Конструкциски материјали', icon: '🧱' },
  { code: '48000000', name: 'Софтверски пакети и информациски системи', icon: '📦' },
  { code: '50000000', name: 'Услуги за поправка и одржување', icon: '🔧' },
  { code: '60000000', name: 'Транспортни услуги', icon: '🚚' },
  { code: '70000000', name: 'Услуги поврзани со недвижен имот', icon: '🏠' },
  { code: '71000000', name: 'Архитектонски, инженерски и градежни услуги', icon: '📐' },
  { code: '72000000', name: 'ИТ услуги', icon: '🖥️' },
  { code: '73000000', name: 'Истражување и развој', icon: '🔬' },
  { code: '75000000', name: 'Јавна администрација', icon: '🏛️' },
  { code: '76000000', name: 'Услуги поврзани со нафтена и гасна индустрија', icon: '⛽' },
  { code: '77000000', name: 'Земјоделство, шумарство и рибарство', icon: '🌾' },
  { code: '79000000', name: 'Деловни услуги', icon: '💼' },
  { code: '80000000', name: 'Образовни и обучни услуги', icon: '📚' },
  { code: '85000000', name: 'Здравствени и социјални услуги', icon: '❤️' },
  { code: '90000000', name: 'Услуги за отстранување на отпад и канализација', icon: '♻️' },
  { code: '92000000', name: 'Рекреативни, културни и спортски услуги', icon: '⚽' },
  { code: '98000000', name: 'Други услуги', icon: '📋' },
];

export default function CategoriesPage() {
  return (
    <div className="min-h-screen bg-white dark:bg-gray-950">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'CollectionPage',
            name: 'Категории на јавни набавки',
            description: 'Сите CPV категории на јавни набавки во Македонија',
            url: 'https://www.nabavkidata.com/categories',
            breadcrumb: {
              '@type': 'BreadcrumbList',
              itemListElement: [
                { '@type': 'ListItem', position: 1, name: 'Почетна', item: 'https://www.nabavkidata.com' },
                { '@type': 'ListItem', position: 2, name: 'Категории', item: 'https://www.nabavkidata.com/categories' },
              ],
            },
          }),
        }}
      />

      <div className="max-w-5xl mx-auto px-4 py-12">
        <h1 className="text-3xl md:text-4xl font-bold mb-3">Категории на јавни набавки</h1>
        <p className="text-gray-600 dark:text-gray-400 mb-8 max-w-2xl">
          Прегледајте ги сите категории на јавни набавки во Македонија класифицирани по CPV (Common Procurement Vocabulary) кодови.
          Над 290,000 тендери распоредени во 5,000+ подкатегории.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {CPV_CATEGORIES.map((cat) => (
            <Link
              key={cat.code}
              href={`/categories/${cat.code}`}
              className="group flex items-start gap-3 p-4 rounded-xl border border-gray-200 dark:border-gray-800 hover:border-blue-400 dark:hover:border-blue-600 hover:shadow-md transition-all"
            >
              <span className="text-2xl shrink-0">{cat.icon}</span>
              <div>
                <h2 className="font-semibold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                  {cat.name}
                </h2>
                <p className="text-xs text-gray-500 dark:text-gray-500 font-mono mt-1">CPV {cat.code}</p>
              </div>
            </Link>
          ))}
        </div>

        <div className="mt-12 text-center">
          <p className="text-gray-500 dark:text-gray-400 mb-4">
            Поставете аларм за вашата категорија и добивајте известување кога ќе се објави нов тендер.
          </p>
          <Link
            href="/auth/register"
            className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 transition-colors"
          >
            Регистрирајте се бесплатно
            <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
