"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

// CPV division code → emoji mapping
const CPV_EMOJI: Record<string, string> = {
  "03": "🌾", "09": "⛽", "14": "⛏️", "15": "🍞",
  "16": "🚜", "18": "👔", "19": "👜", "22": "📄",
  "24": "🧪", "30": "🖥️", "31": "⚡", "32": "📡",
  "33": "🏥", "34": "🚗", "35": "🛡️", "37": "🎵",
  "38": "🔬", "39": "🪑", "41": "💧", "42": "⚙️",
  "43": "🏔️", "44": "🧱", "45": "🏗️", "48": "💿",
  "50": "🔧", "51": "📦", "55": "🏨", "60": "🚚",
  "63": "🚢", "64": "📬", "65": "💡", "66": "🏦",
  "70": "🏠", "71": "📐", "72": "💻", "73": "🔎",
  "75": "🏛️", "76": "🛢️", "77": "🌿", "79": "💼",
  "80": "🎓", "85": "❤️", "90": "♻️", "92": "🎭",
  "98": "🏘️",
};

export interface Division {
  code: string;
  name: string;
  name_mk: string;
  tender_count: number;
  total_value_mkd: number | null;
}

interface CategoryGridProps {
  divisions: Division[];
  loading: boolean;
  onSelect: (cpvCode: string, nameMk: string) => void;
}

function CategoryGridSkeleton() {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {Array.from({ length: 12 }).map((_, i) => (
        <Card key={i} className="overflow-hidden">
          <CardContent className="p-4">
            <Skeleton className="h-8 w-8 rounded-md mb-2" />
            <Skeleton className="h-4 w-3/4 mb-1" />
            <Skeleton className="h-3 w-1/2" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export function CategoryGrid({ divisions, loading, onSelect }: CategoryGridProps) {
  if (loading) {
    return <CategoryGridSkeleton />;
  }

  if (divisions.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {divisions.map((div) => (
        <button
          key={div.code}
          onClick={() => onSelect(div.code, div.name_mk)}
          className="text-left group"
        >
          <Card className="h-full overflow-hidden transition-all hover:border-primary/50 hover:shadow-md group-focus-visible:ring-2 group-focus-visible:ring-ring">
            <CardContent className="p-4">
              <div className="flex items-start justify-between gap-2">
                <span className="text-2xl" role="img" aria-hidden="true">
                  {CPV_EMOJI[div.code] || "📦"}
                </span>
                <Badge variant="secondary" className="text-xs shrink-0">
                  {div.tender_count.toLocaleString()}
                </Badge>
              </div>
              <h3 className="font-medium text-sm mt-2 line-clamp-2 group-hover:text-primary transition-colors">
                {div.name_mk}
              </h3>
            </CardContent>
          </Card>
        </button>
      ))}
    </div>
  );
}
