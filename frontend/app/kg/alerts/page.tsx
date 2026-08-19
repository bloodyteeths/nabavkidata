"use client";

import { useState, type FormEvent } from "react";

export default function KGAlertsSignupPage() {
  const [email, setEmail] = useState("");
  const [keywords, setKeywords] = useState("");
  const [message, setMessage] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const kwList = keywords
      .split(/[,\n]+/)
      .map((k) => k.trim())
      .filter(Boolean);

    if (!email || kwList.length === 0) {
      setMessage("Введите email и хотя бы одно ключевое слово.");
      return;
    }

    const subject = encodeURIComponent(`Подписка на тендер-уведомления · Zakupki.KG`);
    const body = encodeURIComponent(
      `Здравствуйте,\n\nПрошу подключить меня к ежедневным уведомлениям на портале Zakupki.KG.\n\n` +
      `Email: ${email}\n\n` +
      `Ключевые слова:\n${kwList.map((k) => `  • ${k}`).join("\n")}\n\n` +
      `Спасибо!`
    );
    window.location.href = `mailto:hello@facturino.mk?subject=${subject}&body=${body}`;
    setMessage("Открывается ваш email-клиент. Отправьте письмо, и мы подключим вас в течение 24 часов.");
  }

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Подписка на тендер-уведомления</h1>
      <p className="text-gray-600 mb-6">
        Получайте ежедневные email-уведомления о новых тендерах Кыргызстана по вашим ключевым словам.
        Работает как для русских, так и для латинских транслитераций.
      </p>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow-sm p-6 space-y-4">
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
            Ваш email
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        <div>
          <label htmlFor="keywords" className="block text-sm font-medium text-gray-700 mb-1">
            Ключевые слова (через запятую или каждое с новой строки)
          </label>
          <textarea
            id="keywords"
            rows={5}
            required
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="Например:&#10;программное обеспечение&#10;IT услуги&#10;веб-разработка&#10;хостинг"
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
          />
          <p className="text-xs text-gray-500 mt-1">
            Совет: используйте составные фразы (2+ слова) для точных совпадений. Слишком общие слова
            дают много ложных срабатываний.
          </p>
        </div>

        <button
          type="submit"
          className="w-full sm:w-auto bg-blue-600 text-white rounded-md px-6 py-2.5 text-sm font-medium hover:bg-blue-700"
        >
          Подписаться
        </button>

        {message && (
          <div className="p-3 bg-blue-50 text-blue-800 text-sm rounded-md">{message}</div>
        )}
      </form>

      <div className="mt-6 text-sm text-gray-600 space-y-2">
        <p>
          <b>Как это работает:</b> Каждый день в 09:00 (Бишкекское время) наш скрипт проверяет
          все новые тендеры и отправляет вам сводку тех, что совпадают с вашими ключевыми словами.
          Отписаться можно в любой момент через ссылку в email.
        </p>
        <p>
          Пока подписка обрабатывается вручную (24 часа). В следующей версии подписка будет
          мгновенной прямо через сайт.
        </p>
      </div>
    </div>
  );
}
