"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Building2, Calendar, ExternalLink } from "lucide-react";
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
    <Card className="hover:border-primary/50 transition-colors">
      <CardContent className="p-4 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4">
          {/* Product Info */}
          <div className="flex-1 space-y-2 min-w-0">
            <h3 className="font-semibold text-base sm:text-lg leading-tight">
              {product.name}
            </h3>

            <div className="flex flex-wrap gap-1.5 sm:gap-2">
              {product.quantity != null && (
                <Badge variant="secondary" className="text-xs">
                  Кол: {formatQuantity(product.quantity, product.unit)}
                </Badge>
              )}
              {product.unit_price != null && (
                <Badge variant="outline" className="text-xs">
                  Ед. цена: {formatPrice(product.unit_price)}
                </Badge>
              )}
              {product.total_price != null && (
                <Badge className="bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-950 dark:text-green-300 text-xs">
                  Вкупно: {formatPrice(product.total_price)}
                </Badge>
              )}
              {product.cpv_code && (
                <Badge variant="outline" className="font-mono text-xs">
                  CPV: {product.cpv_code}
                </Badge>
              )}
            </div>

            {/* Specifications */}
            {product.specifications && Object.keys(product.specifications).length > 0 && (
              <div className="text-xs text-muted-foreground">
                <p className="font-medium">Спецификации:</p>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {Object.entries(product.specifications).slice(0, 3).map(([key, value]) => (
                    <span key={key} className="bg-muted px-2 py-0.5 rounded text-xs">
                      {key}: {String(value)}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Tender Context */}
            <div className="pt-2 border-t">
              <div className="flex items-start gap-2 text-sm text-muted-foreground">
                <Building2 className="h-4 w-4 mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium text-foreground truncate">
                    {product.tender_title || "Без наслов"}
                  </p>
                  <p className="truncate">{product.procuring_entity}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-3 mt-1.5 text-xs text-muted-foreground">
                {product.opening_date && (
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {formatDate(product.opening_date)}
                  </span>
                )}
                {product.status && (
                  <Badge variant="outline" className="text-xs">
                    {product.status}
                  </Badge>
                )}
                {product.winner && (
                  <span className="text-green-600 dark:text-green-400 truncate max-w-[200px]">
                    Добитник: {product.winner}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Action */}
          <div className="shrink-0">
            <Link href={`/tenders/${encodeURIComponent(product.tender_id)}`}>
              <Button variant="outline" size="sm" className="w-full sm:w-auto">
                <ExternalLink className="h-4 w-4 mr-1.5" />
                Тендер
              </Button>
            </Link>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
