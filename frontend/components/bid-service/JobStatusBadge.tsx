import { cn } from '@/lib/utils';
import { BID_STATUS_BADGE_CLASS, BID_STATUS_LABELS } from '@/lib/bid-service-types';
import type { BidJobStatus } from '@/lib/bid-service-types';

interface JobStatusBadgeProps {
  status: BidJobStatus;
  className?: string;
}

/** Coloured pill showing a bid job's status label. */
export default function JobStatusBadge({ status, className }: JobStatusBadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        BID_STATUS_BADGE_CLASS[status],
        className
      )}
    >
      {BID_STATUS_LABELS[status] ?? status}
    </span>
  );
}
