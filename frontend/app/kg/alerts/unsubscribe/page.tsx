const API = "https://api.nabavkidata.com";

async function unsubscribe(token: string) {
  try {
    const res = await fetch(`${API}/api/kg/alerts/unsubscribe?token=${encodeURIComponent(token)}`, {
      cache: "no-store",
    });
    return res.json();
  } catch {
    return { ok: false, message: "Не удалось связаться с сервером." };
  }
}

export default async function KGUnsubscribePage({
  searchParams,
}: {
  searchParams: { token?: string };
}) {
  const token = searchParams.token;
  const result = token
    ? await unsubscribe(token)
    : { ok: false, message: "Токен отсутствует в ссылке." };

  return (
    <div className="max-w-lg mx-auto text-center py-12">
      <div className="text-5xl mb-4">{result.ok ? "👋" : "⚠️"}</div>
      <h1 className="text-2xl font-bold text-gray-900 mb-3">
        {result.ok ? "Подписка отменена" : "Не удалось отписаться"}
      </h1>
      <p className="text-gray-600 mb-6">{result.message}</p>
      <a
        href="/kg/alerts"
        className="inline-flex items-center px-5 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
      >
        Оформить новую подписку
      </a>
    </div>
  );
}
