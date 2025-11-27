import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

const DEFAULT_LOCALE = "mk-MK";
const DEFAULT_TIME_ZONE = "Europe/Skopje";

const toDate = (value: string | number | Date) =>
  value instanceof Date ? value : new Date(value);

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number | undefined, currency: string = "MKD"): string {
  if (value === undefined || value === null) return "N/A";

  const formatter = new Intl.NumberFormat(DEFAULT_LOCALE, {
    style: "decimal",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    useGrouping: true,
  });

  const symbol = currency === "EUR" ? "€" : currency === "USD" ? "$" : "ден";
  const formatted = formatter.format(value);

  // Place symbol consistently to avoid environment-specific currency layout differences.
  if (currency === "EUR" || currency === "USD") {
    return `${symbol}${formatted}`;
  }

  return `${formatted} ${symbol}`;
}

export function formatDate(
  date: string | number | Date | undefined | null,
  options: Intl.DateTimeFormatOptions = {},
  locale: string = DEFAULT_LOCALE
): string {
  if (!date) return "N/A";

  const formatter = new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: DEFAULT_TIME_ZONE,
    ...options,
  });

  return formatter.format(toDate(date));
}

export function formatDateTime(
  date: string | number | Date | undefined | null,
  options: Intl.DateTimeFormatOptions = {},
  locale: string = DEFAULT_LOCALE
): string {
  if (!date) return "N/A";

  const formatter = new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: DEFAULT_TIME_ZONE,
    ...options,
  });

  return formatter.format(toDate(date));
}

export function formatRelativeTime(date: string): string {
  const now = new Date();
  const past = new Date(date);
  const diffMs = now.getTime() - past.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Денес";
  if (diffDays === 1) return "Вчера";
  if (diffDays < 7) return `Пред ${diffDays} дена`;
  if (diffDays < 30) return `Пред ${Math.floor(diffDays / 7)} недели`;
  return formatDate(date);
}
