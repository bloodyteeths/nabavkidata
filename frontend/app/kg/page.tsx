import Link from "next/link";

const API = "https://api.nabavkidata.com";

async function getStats() {
  try {
    const res = await fetch(`${API}/api/kg/stats`, { next: { revalidate: 300 } });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function getRecentTenders() {
  try {
    const res = await fetch(`${API}/api/kg/tenders?limit=10`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return { tenders: [] };
    return res.json();
  } catch {
    return { tenders: [] };
  }
}

function fmtAmount(v: number | null) {
  if (v == null) return "—";
  return new Intl.NumberFormat("ru-RU").format(v) + " сом";
}

function fmtDate(v: string | null) {
  if (!v) return "—";
  return new Date(v).toLocaleDateString("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

export default async function KGHomePage() {
  const [stats, recent] = await Promise.all([getStats(), getRecentTenders()]);

  return (
    <div>
      {/* Hero */}
      <section className="bg-white rounded-lg shadow-sm p-8 mb-8">
        <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-3">
          Государственные закупки Кыргызстана
        </h1>
        <p className="text-lg text-gray-600 mb-6">
          Поиск и мониторинг тендеров с двух главных площадок: <b>goszakupki.okmot.kg</b> и
          <b> zakupki.gov.kg</b>. Ежедневные уведомления по вашим ключевым словам.
        </p>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/kg/tenders"
            className="inline-flex items-center px-5 py-2.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 font-medium"
          >
            Все тендеры
          </Link>
          <Link
            href="/kg/alerts"
            className="inline-flex items-center px-5 py-2.5 bg-white text-blue-700 border border-blue-600 rounded-md hover:bg-blue-50 font-medium"
          >
            Подписаться на уведомления
          </Link>
        </div>
      </section>

      {/* Stats */}
      {stats && (
        <section className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow-sm p-5">
            <div className="text-sm text-gray-500">Всего тендеров в базе</div>
            <div className="text-3xl font-bold text-gray-900 mt-1">
              {new Intl.NumberFormat("ru-RU").format(stats.total)}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-5">
            <div className="text-sm text-gray-500">Активные (открыты для заявок)</div>
            <div className="text-3xl font-bold text-blue-600 mt-1">
              {new Intl.NumberFormat("ru-RU").format(stats.active)}
            </div>
          </div>
          <div className="bg-white rounded-lg shadow-sm p-5">
            <div className="text-sm text-gray-500">Источники</div>
            <div className="mt-1 text-sm">
              {stats.by_source?.map((s: { source: string; count: number }) => (
                <div key={s.source} className="flex justify-between">
                  <span className="text-gray-700">{s.source}</span>
                  <span className="font-semibold">{new Intl.NumberFormat("ru-RU").format(s.count)}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Recent tenders */}
      <section className="bg-white rounded-lg shadow-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">Недавние тендеры</h2>
          <Link href="/kg/tenders" className="text-sm text-blue-600 hover:underline">
            Смотреть все →
          </Link>
        </div>
        <ul className="divide-y divide-gray-100">
          {recent.tenders?.map((t: {
            tender_id: string;
            title: string;
            buyer_name: string;
            amount_kgs: number | null;
            date_published: string | null;
            source: string;
          }) => (
            <li key={t.tender_id} className="py-4">
              <Link href={`/kg/tenders/${encodeURIComponent(t.tender_id)}`} className="block hover:bg-gray-50 -mx-3 px-3 py-2 rounded">
                <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-2">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-gray-900 line-clamp-2">{t.title}</h3>
                    <p className="text-sm text-gray-500 mt-1">{t.buyer_name}</p>
                  </div>
                  <div className="flex flex-col sm:items-end text-sm">
                    <span className="font-semibold text-gray-900">{fmtAmount(t.amount_kgs)}</span>
                    <span className="text-gray-500">{fmtDate(t.date_published)}</span>
                    <span className="text-xs text-gray-400 mt-1">{t.source}</span>
                  </div>
                </div>
              </Link>
            </li>
          ))}
          {(!recent.tenders || recent.tenders.length === 0) && (
            <li className="py-8 text-center text-gray-500">Тендеры не найдены</li>
          )}
        </ul>
      </section>
    </div>
  );
}
