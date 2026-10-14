import Link from 'next/link';
import { Building2, CalendarDays, MessageSquare } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { WHOSE_MOVE_LABELS } from '@/lib/bid-service-types';
import type { BidJobSummary } from '@/lib/bid-service-types';
import JobStatusBadge from '@/components/bid-service/JobStatusBadge';
import DeadlineWarning, { formatDmy } from '@/components/bid-service/DeadlineWarning';

interface JobCardProps {
  job: BidJobSummary;
}

/** Compact card for one bid job, linking to its portal page. */
export default function JobCard({ job }: JobCardProps) {
  const moveLabel = WHOSE_MOVE_LABELS[job.whose_move];
  return (
    <Link href={`/portal/bid/${job.id}`} className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-lg">
      <Card
        className={cn(
          'transition-colors hover:border-primary/50',
          job.whose_move === 'client' && 'border-amber-300 dark:border-amber-700'
        )}
      >
        <CardContent className="space-y-3 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs text-muted-foreground">{job.tender_id}</p>
              <h3 className="line-clamp-2 font-semibold leading-snug">
                {job.tender_title || job.tender_id}
              </h3>
            </div>
            <JobStatusBadge status={job.status} className="shrink-0" />
          </div>

          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {job.procuring_entity && (
              <span className="flex min-w-0 items-center gap-1">
                <Building2 className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{job.procuring_entity}</span>
              </span>
            )}
            {job.closing_date && (
              <span className="flex items-center gap-1">
                <CalendarDays className="h-3.5 w-3.5 shrink-0" />
                Рок: {formatDmy(job.closing_date)}
              </span>
            )}
          </div>

          <p className="text-sm">{job.phase_text}</p>

          <DeadlineWarning
            closingDate={job.closing_date}
            deadlineState={job.deadline_state}
            daysLeft={job.days_left}
          />

          {(moveLabel || job.unread_messages > 0) && (
            <div className="flex flex-wrap items-center gap-3 text-xs">
              {moveLabel && (
                <span
                  className={cn(
                    'font-medium',
                    job.whose_move === 'client'
                      ? 'text-amber-700 dark:text-amber-300'
                      : 'text-blue-700 dark:text-blue-300'
                  )}
                >
                  {moveLabel}
                </span>
              )}
              {job.unread_messages > 0 && (
                <span className="flex items-center gap-1 font-medium text-primary">
                  <MessageSquare className="h-3.5 w-3.5" />
                  {job.unread_messages === 1
                    ? '1 нова порака'
                    : `${job.unread_messages} нови пораки`}
                </span>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
