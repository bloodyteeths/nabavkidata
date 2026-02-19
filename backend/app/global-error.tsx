"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Global error:", error);
  }, [error]);

  return (
    <html lang="mk">
      <body className="bg-gray-900 text-white min-h-screen flex items-center justify-center">
        <div className="max-w-md w-full p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-red-500/20 flex items-center justify-center mx-auto mb-6">
            <svg className="h-8 w-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>

          <h1 className="text-2xl font-bold mb-2">Критична грешка</h1>
          <p className="text-gray-400 mb-6">
            Апликацијата наиде на неочекуван проблем. Обидете се да ја освежите страницата.
          </p>

          <div className="flex flex-col gap-3">
            <button
              onClick={reset}
              className="px-4 py-2 bg-purple-600 hover:bg-purple-700 rounded-lg transition-colors"
            >
              Обиди се повторно
            </button>
            <button
              onClick={() => window.location.href = "/"}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            >
              Оди на почетна
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
