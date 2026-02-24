"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Building2, Calendar, ChevronRight } from "lucide-react";
import Link from "next/link";
import { formatDate } from "@/lib/utils";
import type { ProductSearchResult } from "@/lib/api";

function formatPrice(price: number | undefined): string {
  if (!price) return "-";
  return new Intl.NumberFormat("mk-MK", {
    style: "currency",
    currency: "MKD",
    maximumFractionDigits: 0,
  }).format(price);
}

function formatQuantity(qty: number | undefined, unit: string | undefined): string {
  if (!qty) return "-";
  return `${qty.toLocaleString("mk-MK")} ${unit || ""}`.trim();
}

interface ProductCardProps {
  product: ProductSearchResult;
}

export function ProductCard({ product }: ProductCardProps) {
  return (
    <Link href={`/tenders/${encodeURIComponent(product.tender_id)}`} className="block group">
      <Card className="hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer">
        <CardContent className="p-4 sm:p-5">
          {/* Product name + arrow */}
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold text-sm sm:text-base leading-snug flex-1">
              {product.name}
            </h3>
            <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5 group-hover:text-primary transition-colors" />
          </div>

          {/* Price & quantity badges */}
          <div className="flex flex-wrap gap-1.5 mt-2">
            {product.unit_price != null && (
              <Badge variant="outline" className="text-xs font-medium">
                {formatPrice(product.unit_price)}
                {product.unit ? ` / ${product.unit}` : ""}
              </Badge>
            )}
            {product.total_price != null && (
              <Badge className="bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-950 dark:text-green-300 text-xs font-medium">
                Вкупно: {formatPrice(product.total_price)}
              </Badge>
            )}
            {product.quantity != null && (
              <Badge variant="secondary" className="text-xs">
                {formatQuantity(product.quantity, product.unit)}
              </Badge>
            )}
            {product.cpv_code && (
              <Badge variant="outline" className="font-mono text-[11px] text-muted-foreground">
                {product.cpv_code}
              </Badge>
            )}
          </div>

          {/* Tender context — subtle footer */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-3 pt-2 border-t text-xs text-muted-foreground">
            <span className="flex items-center gap-1 truncate max-w-[250px] sm:max-w-[350px]">
              <Building2 className="h-3 w-3 shrink-0" />
              {product.procuring_entity}
            </span>
            {product.opening_date && (
              <span className="flex items-center gap-1">
                <Calendar className="h-3 w-3 shrink-0" />
                {formatDate(product.opening_date)}
              </span>
            )}
            {product.status && (
              <Badge variant="outline" className="text-[11px] h-5">
                {product.status}
              </Badge>
            )}
            {product.winner && (
              <span className="text-green-600 dark:text-green-400 truncate max-w-[180px]">
                Добитник: {product.winner}
              </span>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
