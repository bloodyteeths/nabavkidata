import { AlertTriangle, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { DeadlineState } from '@/lib/bid-service-types';

const SKOPJE_TZ = 'Europe/Skopje';
const HAS_OFFSET = /(?:[zZ]|[+-]\d{2}:?\d{2})$/;

/** Parts of an offset-carrying ISO timestamp in Skopje time, or null. */
function skopjeParts(value: string): Record<string, string> | null {
  if (!HAS_OFFSET.test(value)) return null;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return null;
  const out: Record<string, string> = {};
  for (const p of new Intl.DateTimeFormat('en-GB', {
    timeZone: SKOPJE_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(d)) {
    out[p.type] = p.value;
  }
  return out;
}

/**
 * Format a "YYYY-MM-DD" date or an ISO timestamp as dd.mm.yyyy.
 * Plain dates are shown as given (no timezone shift); timestamps with an offset
 * (all bid-service timestamps) are shown in Skopje time.
 */
export function formatDmy(value: string | null | undefined): string {
  if (!value) return '—';
  const p = skopjeParts(value);
  if (p) return `${p.day}.${p.month}.${p.year}`;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!m) return value;
  return `${m[3]}.${m[2]}.${m[1]}`;
}

/** Format an ISO timestamp as dd.mm.yyyy HH:MM in Skopje time. */
export function formatDmyTime(value: string | null | undefined): string {
  if (!value) return '—';
  const p = skopjeParts(value);
  if (p) return `${p.day}.${p.month}.${p.year} ${p.hour}:${p.minute}`;
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/.exec(value);
  if (!m) return formatDmy(value);
  return `${m[3]}.${m[2]}.${m[1]} ${m[4]}:${m[5]}`;
}

/** "1 ден", "2 дена", ... */
export function daysLabel(n: number): string {
  return n === 1 ? '1 ден' : `${n} дена`;
}

interface DeadlineWarningProps {
  closingDate: string | null;
  deadlineState: DeadlineState | null;
  daysLeft: number | null;
  className?: string;
}

/** Deadline notice for jobs that are not yet submitted. Renders nothing when the deadline is comfortable. */
export default function DeadlineWarning({ closingDate, deadlineState, daysLeft, className }: DeadlineWarningProps) {
  if (!deadlineState || deadlineState === 'ok') return null;

  if (deadlineState === 'soon') {
    return (
      <div
        className={cn(
          'flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200',
          className
        )}
      >
        <Clock className="h-4 w-4 shrink-0" />
        <span>
          Рок за поднесување: {formatDmy(closingDate)} (уште {daysLabel(daysLeft ?? 0)})
        </span>
      </div>
    );
  }

  const text =
    deadlineState === 'today'
      ? 'Рокот за поднесување истекува денес.'
      : `Рокот за поднесување истече на ${formatDmy(closingDate)}.`;

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-800 dark:bg-red-950/40 dark:text-red-200',
        className
      )}
    >
      <AlertTriangle className="h-4 w-4 shrink-0" />
      <span>{text}</span>
    </div>
  );
}
