import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

const MONTHS_SHORT_MK = ["јан", "фев", "мар", "апр", "мај", "јун", "јул", "авг", "сеп", "окт", "ное", "дек"];
const MONTHS_LONG_MK = [
  "јануари",
  "февруари",
  "март",
  "април",
  "мај",
  "јуни",
  "јули",
  "август",
  "септември",
  "октомври",
  "ноември",
  "декември",
];

// Macedonia timezone
export const MACEDONIA_TZ = "Europe/Skopje";

const toDate = (value: string | number | Date) =>
  value instanceof Date ? value : new Date(value);

// Convert to Macedonia timezone and get date parts
const toMacedoniaDate = (date: Date) => {
  // Use Intl.DateTimeFormat to get parts in Macedonia timezone
  const formatter = new Intl.DateTimeFormat("en-CA", {
    timeZone: MACEDONIA_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  const parts = formatter.formatToParts(date);
  const partMap: Record<string, string> = {};
  parts.forEach(p => { partMap[p.type] = p.value; });
  return {
    year: parseInt(partMap.year || "0"),
    month: parseInt(partMap.month || "1") - 1, // 0-indexed
    day: parseInt(partMap.day || "1"),
    hour: parseInt(partMap.hour || "0"),
    minute: parseInt(partMap.minute || "0"),
  };
};

const pad2 = (n: number) => n.toString().padStart(2, "0");

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number | undefined, currency: string = "MKD"): string {
  if (value === undefined || value === null) return "N/A";

  const formatted = Math.trunc(value)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ",");

  const symbol = currency === "EUR" ? "€" : currency === "USD" ? "$" : "ден";

  // Place symbol consistently to avoid environment-specific currency layout differences.
  if (currency === "EUR" || currency === "USD") {
    return `${symbol}${formatted}`;
  }

  return `${formatted} ${symbol}`;
}

export function formatDate(
  date: string | number | Date | undefined | null,
  options: Intl.DateTimeFormatOptions = {}
): string {
  if (!date) return "N/A";

  const d = toDate(date);
  const mkDate = toMacedoniaDate(d);
  const monthOpt = options.month ?? "short";
  const dayOpt = options.day ?? "numeric";
  const yearOpt = options.year ?? "numeric";

  const month =
    monthOpt === "long"
      ? MONTHS_LONG_MK[mkDate.month]
      : monthOpt === "short"
      ? MONTHS_SHORT_MK[mkDate.month]
      : monthOpt === "2-digit"
      ? pad2(mkDate.month + 1)
      : (mkDate.month + 1).toString();

  const day = dayOpt === "2-digit" ? pad2(mkDate.day) : mkDate.day.toString();
  const year = yearOpt === "numeric" ? mkDate.year.toString() : "";

  // Common formats used across the app; join parts that exist.
  const parts = [day, month, year].filter(Boolean);
  return parts.join(" ").trim();
}

export function formatDateTime(
  date: string | number | Date | undefined | null,
  options: Intl.DateTimeFormatOptions = {}
): string {
  if (!date) return "N/A";

  // Map dateStyle/timeStyle helpers to concrete parts we support
  const mappedOptions: Intl.DateTimeFormatOptions = { ...options };
  if (options.dateStyle === "medium") {
    mappedOptions.year = "numeric";
    mappedOptions.month = "short";
    mappedOptions.day = "numeric";
  }
  if (options.timeStyle === "short") {
    mappedOptions.hour = "2-digit";
    mappedOptions.minute = "2-digit";
  }

  const d = toDate(date);
  const mkDate = toMacedoniaDate(d);
  const datePart = mappedOptions.year || mappedOptions.month || mappedOptions.day ? formatDate(d, mappedOptions) : "";
  const hour = mappedOptions.hour ? pad2(mkDate.hour) : "";
  const minute = mappedOptions.minute ? pad2(mkDate.minute) : "";
  const timePart = hour && minute ? `${hour}:${minute}` : hour || minute;

  if (datePart && timePart) return `${datePart} ${timePart}`;
  return datePart || timePart || d.toISOString();
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

// Get current date in Macedonia timezone (YYYY-MM-DD format)
export function getTodayMK(): string {
  const now = new Date();
  const mkDate = toMacedoniaDate(now);
  return `${mkDate.year}-${pad2(mkDate.month + 1)}-${pad2(mkDate.day)}`;
}

// Get current datetime in Macedonia timezone
export function getNowMK(): { year: number; month: number; day: number; hour: number; minute: number } {
  return toMacedoniaDate(new Date());
}
