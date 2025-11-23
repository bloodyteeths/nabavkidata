import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(value: number | undefined, currency: string = 'MKD'): string {
  if (!value) return 'N/A';
  return new Intl.NumberFormat('mk-MK', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatDate(date: string | undefined): string {
  if (!date) return 'N/A';
  return new Date(date).toLocaleDateString('mk-MK', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export function formatRelativeTime(date: string): string {
  const now = new Date();
  const past = new Date(date);
  const diffMs = now.getTime() - past.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return 'Денес';
  if (diffDays === 1) return 'Вчера';
  if (diffDays < 7) return `Пред ${diffDays} дена`;
  if (diffDays < 30) return `Пред ${Math.floor(diffDays / 7)} недели`;
  return formatDate(date);
}
