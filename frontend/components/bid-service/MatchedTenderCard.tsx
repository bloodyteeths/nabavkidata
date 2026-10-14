'use client';

import Link from 'next/link';
import { Building2, CalendarDays } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { tenderUrl } from '@/lib/utils';
import { formatMkd } from '@/lib/bid-service-types';
import type { MatchedTender } from '@/lib/bid-service-types';
import { formatDmy } from '@/components/bid-service/DeadlineWarning';
import StartBidButton from '@/components/bid-service/StartBidButton';

interface MatchedTenderCardProps {
  tender: MatchedTender;
}

/** A tender matched to the client's profile, with a confirmed "start a bid" action. */
export default function MatchedTenderCard({ tender }: MatchedTenderCardProps) {
  return (
    <Card className="flex h-full flex-col">
      <CardContent className="flex flex-1 flex-col gap-3 p-4">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{tender.tender_id}</p>
          <Link
            href={tenderUrl(tender.tender_id)}
            className="line-clamp-3 font-semibold leading-snug hover:underline"
          >
            {tender.title || tender.tender_id}
          </Link>
        </div>
        <div className="space-y-1 text-sm text-muted-foreground">
          {tender.procuring_entity && (
            <p className="flex items-start gap-1">
              <Building2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span className="line-clamp-2">{tender.procuring_entity}</span>
            </p>
          )}
          <p className="flex items-center gap-1">
            <CalendarDays className="h-3.5 w-3.5 shrink-0" />
            Рок: {formatDmy(tender.closing_date)}
          </p>
          <p>Проценета вредност: {formatMkd(tender.estimated_value_mkd)}</p>
          {tender.match_reasons.length > 0 && (
            <p className="text-xs">{tender.match_reasons.slice(0, 2).join(' · ')}</p>
          )}
        </div>
        <div className="mt-auto pt-1">
          <StartBidButton tenderId={tender.tender_id} tenderTitle={tender.title} className="w-full" />
        </div>
      </CardContent>
    </Card>
  );
}
