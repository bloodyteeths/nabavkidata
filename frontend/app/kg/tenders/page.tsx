import Link from "next/link";

const API = "https://api.nabavkidata.com";

async function fetchTenders(params: {
  q?: string;
  status?: string;
  offset?: number;
  limit?: number;
}) {
  const qs = new URLSearchParams();
  if (params.q) qs.set("q", params.q);
  if (params.status) qs.set("status", params.status);
  if (params.offset != null) qs.set("offset", String(params.offset));
  qs.set("limit", String(params.limit ?? 50));

  try {
    const res = await fetch(`${API}/api/kg/tenders?${qs.toString()}`, {
      next: { revalidate: 60 },
    });
    if (!res.ok) return { tenders: [], total: 0, limit: 50, offset: 0 };
    return res.json();
  } catch {
    return { tenders: [], total: 0, limit: 50, offset: 0 };
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
    month: "short",
    year: "numeric",
  });
}

function statusLabel(s: string | null): { text: string; color: string } {
  if (!s) return { text: "—", color: "bg-gray-100 text-gray-700" };
  const activeLike = /PUBLISHED|OPEN|ACTIVE|VERIFIED/i.test(s);
  const finishedLike = /COMPLET|CONTRACT|CLOSED|AWARDED/i.test(s);
  const cancelled = /CANCEL|ANNUL|REJECT/i.test(s);
  if (cancelled) return { text: "Отменён", color: "bg-red-100 text-red-800" };
  if (finishedLike) return { text: "Завершён", color: "bg-gray-100 text-gray-700" };
  if (activeLike) return { text: "Активен", color: "bg-green-100 text-green-800" };
  return { text: s, color: "bg-blue-100 text-blue-800" };
}

export default async function KGTendersListPage({
  searchParams,
}: {
  searchParams: { q?: string; status?: string; offset?: string };
}) {
  const offset = Number(searchParams.offset ?? 0);
  const limit = 50;
  const data = await fetchTenders({
    q: searchParams.q,
    status: searchParams.status,
    offset,
    limit,
  });

  const totalPages = Math.ceil((data.total || 0) / limit);
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div>
      <div className="mb-6 flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Тендеры Кыргызстана</h1>
          <p className="text-sm text-gray-600 mt-1">
            Всего в базе: <b>{new Intl.NumberFormat("ru-RU").format(data.total || 0)}</b> тендеров
          </p>
        </div>
      </div>

      {/* Search form */}
      <form method="get" className="mb-6 bg-white rounded-lg shadow-sm p-4 flex flex-col sm:flex-row gap-3">
        <input
          type="text"
          name="q"
          defaultValue={searchParams.q ?? ""}
          placeholder="Поиск по названию, покупателю, номеру..."
          className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          name="status"
          defaultValue={searchParams.status ?? ""}
          className="border border-gray-300 rounded-md px-3 py-2 text-sm"
        >
          <option value="">Все статусы</option>
          <option value="active">Только активные</option>
          <option value="finished">Завершённые</option>
        </select>
        <button
          type="submit"
          className="bg-blue-600 text-white rounded-md px-4 py-2 text-sm font-medium hover:bg-blue-700"
        >
          Найти
        </button>
      </form>

      {/* Results table */}
      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <ul className="divide-y divide-gray-100">
          {data.tenders?.map((t: {
            tender_id: string;
            tender_number: string;
            title: string;
            buyer_name: string;
            amount_kgs: number | null;
            date_published: string | null;
            date_contest: string | null;
            status: string | null;
            source: string;
          }) => {
            const st = statusLabel(t.status);
            return (
              <li key={t.tender_id} className="p-4 hover:bg-gray-50 transition-colors">
                <Link href={`/kg/tenders/${encodeURIComponent(t.tender_id)}`} className="block">
                  <div className="flex flex-col sm:flex-row sm:justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs px-2 py-0.5 rounded ${st.color}`}>{st.text}</span>
                        <span className="text-xs text-gray-500 font-mono">№ {t.tender_number}</span>
                      </div>
                      <h3 className="font-medium text-gray-900 line-clamp-2 mb-1">{t.title}</h3>
                      <p className="text-sm text-gray-600">{t.buyer_name}</p>
                    </div>
                    <div className="flex flex-col sm:items-end sm:text-right text-sm min-w-fit">
                      <span className="font-semibold text-gray-900">{fmtAmount(t.amount_kgs)}</span>
                      <span className="text-gray-500">Опубликован: {fmtDate(t.date_published)}</span>
                      {t.date_contest && (
                        <span className="text-gray-500">Дедлайн: {fmtDate(t.date_contest)}</span>
                      )}
                    </div>
                  </div>
                </Link>
              </li>
            );
          })}
          {(!data.tenders || data.tenders.length === 0) && (
            <li className="p-12 text-center text-gray-500">Тендеры не найдены</li>
          )}
        </ul>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-6 flex items-center justify-between text-sm">
          <span className="text-gray-600">
            Страница {currentPage} из {totalPages}
          </span>
          <div className="flex gap-2">
            {offset > 0 && (
              <Link
                href={`/kg/tenders?${new URLSearchParams({
                  ...(searchParams.q ? { q: searchParams.q } : {}),
                  ...(searchParams.status ? { status: searchParams.status } : {}),
                  offset: String(Math.max(0, offset - limit)),
                })}`}
                className="px-3 py-1.5 bg-white border border-gray-300 rounded hover:bg-gray-50"
              >
                ← Назад
              </Link>
            )}
            {offset + limit < data.total && (
              <Link
                href={`/kg/tenders?${new URLSearchParams({
                  ...(searchParams.q ? { q: searchParams.q } : {}),
                  ...(searchParams.status ? { status: searchParams.status } : {}),
                  offset: String(offset + limit),
                })}`}
                className="px-3 py-1.5 bg-white border border-gray-300 rounded hover:bg-gray-50"
              >
                Далее →
              </Link>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
