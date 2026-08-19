import Link from "next/link";
import { notFound } from "next/navigation";

const API = "https://api.nabavkidata.com";

async function fetchTender(id: string) {
  try {
    const res = await fetch(`${API}/api/kg/tenders/${encodeURIComponent(id)}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function fmtAmount(v: number | null) {
  if (v == null) return "—";
  return new Intl.NumberFormat("ru-RU").format(v) + " сом";
}

function fmtDateTime(v: string | null) {
  if (!v) return "—";
  return new Date(v).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default async function KGTenderDetailPage({ params }: { params: { id: string } }) {
  const t = await fetchTender(params.id);
  if (!t) notFound();

  const sourceLink =
    t.source === "goszakupki.okmot.kg"
      ? `https://goszakupki.okmot.kg/popp/view/order/view.xhtml?id=${t.tender_id}`
      : `https://zakupki.gov.kg/popp/view/order/view.xhtml?id=${t.tender_id}`;

  return (
    <div>
      <nav className="text-sm mb-4">
        <Link href="/kg" className="text-blue-600 hover:underline">Главная</Link>
        <span className="mx-2 text-gray-400">/</span>
        <Link href="/kg/tenders" className="text-blue-600 hover:underline">Тендеры</Link>
        <span className="mx-2 text-gray-400">/</span>
        <span className="text-gray-500">{t.tender_number}</span>
      </nav>

      <article className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <div className="mb-4 flex items-center gap-2 flex-wrap">
          <span className="text-xs font-mono text-gray-500">№ {t.tender_number}</span>
          {t.status && (
            <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">{t.status}</span>
          )}
          {t.tender_type && (
            <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">{t.tender_type}</span>
          )}
          {t.procurement_method && (
            <span className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded">{t.procurement_method}</span>
          )}
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-2">{t.title}</h1>
        <p className="text-lg text-gray-700 mb-6">{t.buyer_name}</p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          <div>
            <div className="text-sm text-gray-500">Сумма закупки</div>
            <div className="text-xl font-semibold text-gray-900">{fmtAmount(t.amount_kgs)}</div>
          </div>
          {t.contract_amount_kgs != null && (
            <div>
              <div className="text-sm text-gray-500">Сумма контракта</div>
              <div className="text-xl font-semibold text-green-700">
                {fmtAmount(t.contract_amount_kgs)}
              </div>
            </div>
          )}
          <div>
            <div className="text-sm text-gray-500">Опубликован</div>
            <div className="text-gray-900">{fmtDateTime(t.date_published)}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Крайний срок подачи</div>
            <div className="text-gray-900">{fmtDateTime(t.date_contest)}</div>
          </div>
          {t.date_awarded && (
            <div>
              <div className="text-sm text-gray-500">Присуждён</div>
              <div className="text-gray-900">{fmtDateTime(t.date_awarded)}</div>
            </div>
          )}
          {t.winner_name && (
            <div>
              <div className="text-sm text-gray-500">Победитель</div>
              <div className="text-gray-900 font-medium">{t.winner_name}</div>
            </div>
          )}
        </div>

        {t.description && (
          <div className="border-t border-gray-200 pt-4">
            <h2 className="text-sm font-semibold text-gray-500 uppercase mb-2">Предмет закупки</h2>
            <p className="text-gray-800 whitespace-pre-line">{t.description}</p>
          </div>
        )}
      </article>

      <div className="bg-white rounded-lg shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-3">Официальные источники</h2>
        <div className="text-sm text-gray-600 space-y-2">
          <div>
            <b>Источник данных:</b> {t.source}
          </div>
          <div>
            <a
              href={sourceLink}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:underline"
            >
              Открыть на официальном портале →
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
