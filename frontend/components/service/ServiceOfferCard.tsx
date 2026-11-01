import Link from "next/link";
import { PenLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface ServiceOfferCardProps {
  title: string;
  text: string;
  /** Source tag kept on the /usluga lead, so requests can be counted per page type. */
  source: string;
  className?: string;
}

/** Short offer of the bid-writing service on public pages that search traffic reaches. */
export default function ServiceOfferCard({ title, text, source, className }: ServiceOfferCardProps) {
  return (
    <Card className={className ?? "mb-6 border-primary/20 bg-primary/5"}>
      <CardContent className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-start gap-3">
          <PenLine className="h-8 w-8 text-primary shrink-0" />
          <div>
            <p className="font-semibold">{title}</p>
            <p className="text-sm text-muted-foreground">{text}</p>
          </div>
        </div>
        <Link href={`/usluga?src=${source}`} className="shrink-0">
          <Button>Побарајте цена за подготовка</Button>
        </Link>
      </CardContent>
    </Card>
  );
}
