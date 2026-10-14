"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Clock, PenLine } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import QualifyForm from "@/components/service/QualifyForm";
import { cn } from "@/lib/utils";

/** Statuses under which a tender still accepts bids. */
const OPEN_STATUSES = new Set(["open", "active"]);

/**
 * True when a bid can still be submitted: status is open/active (or missing)
 * and the closing date, if known, is today or later.
 */
export function isTenderOpenForBids(status?: string | null, closingDate?: string | null): boolean {
  if (status && !OPEN_STATUSES.has(status.toLowerCase())) return false;
  if (closingDate) {
    const close = new Date(closingDate);
    if (!Number.isNaN(close.getTime())) {
      close.setHours(0, 0, 0, 0);
      const today = new Date();
      today.setHours(0, 0, 0, 0);
      if (close < today) return false;
    }
  }
  return true;
}

interface WriteMyBidCardProps {
  tenderId: string;
  status?: string | null;
  closingDate?: string | null;
  className?: string;
}

/**
 * "We write this bid" — the tender page's entry into the bid-writing service.
 * Rendered at the top of the tender sidebar with id="ponuda" so other CTAs can
 * link to #ponuda. ?ponuda=1 scrolls it into view and highlights it briefly.
 * Hidden once the tender no longer accepts bids (a short notice is shown
 * instead when the visitor arrived via ?ponuda=1).
 */
export default function WriteMyBidCard({ tenderId, status, closingDate, className }: WriteMyBidCardProps) {
  const searchParams = useSearchParams();
  const ref = useRef<HTMLDivElement>(null);
  const [highlight, setHighlight] = useState(false);
  const open = isTenderOpenForBids(status, closingDate);
  const focus = searchParams?.get("ponuda") === "1";

  useEffect(() => {
    if (!open || !focus || !ref.current) return;
    ref.current.scrollIntoView({ behavior: "smooth", block: "start" });
    setHighlight(true);
    const t = window.setTimeout(() => setHighlight(false), 2500);
    return () => window.clearTimeout(t);
  }, [open, focus]);

  if (!open) {
    // Arrived from an email CTA (?ponuda=1) after the deadline: explain instead of silence.
    if (!focus) return null;
    return (
      <Card className={cn("border-amber-500/30 bg-amber-500/5", className)}>
        <CardContent className="flex items-start gap-3 p-4 text-sm">
          <Clock className="h-4 w-4 mt-0.5 shrink-0 text-amber-600" />
          <p className="text-muted-foreground">
            Рокот за овој тендер истече.{" "}
            <Link href="/usluga?src=tender_closed" className="font-medium text-primary underline underline-offset-4">
              Побарајте проценка за слични тендери
            </Link>
            .
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      id="ponuda"
      ref={ref}
      className={cn(
        "scroll-mt-24 border-primary/30 transition-shadow duration-500",
        highlight && "ring-2 ring-primary shadow-lg shadow-primary/20",
        className
      )}
    >
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2">
          <PenLine className="h-4 w-4 text-primary" />
          Ние ја пишуваме оваа понуда
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2 text-sm text-muted-foreground">
          <p>
            Ја подготвуваме целата понуда врз основа на тендерската документација. Вие ја прегледувате,
            ја потпишувате со вашиот сертификат и ја поднесувате на е-набавки.
          </p>
          <p>
            <span className="font-medium text-foreground">од 30.000 МКД</span> за подготовка, договорено
            однапред, и 5% од вредноста на договорот за првата година само ако победите.
          </p>
        </div>
        <QualifyForm compact tenderId={tenderId} source="tender_card" />
      </CardContent>
    </Card>
  );
}
