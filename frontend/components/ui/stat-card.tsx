import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  icon: LucideIcon;
  iconColor?: string;
  label: string;
  value: string | number;
  subtitle?: string;
  trend?: { value: string; positive: boolean };
  className?: string;
}

export function StatCard({ icon: Icon, iconColor = "bg-primary/10 text-primary", label, value, subtitle, trend, className }: StatCardProps) {
  const [bgClass, textClass] = iconColor.includes(" ") ? iconColor.split(" ") : [iconColor, "text-primary"];
  return (
    <div className={cn("rounded-xl border bg-card p-4 transition-colors hover:bg-accent/5", className)}>
      <div className="flex items-center gap-3">
        <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg", bgClass)}>
          <Icon className={cn("h-4 w-4", textClass)} />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground truncate">{label}</p>
          <p className="text-lg font-semibold tabular-nums text-foreground">{value}</p>
          {(subtitle || trend) && (
            <div className="flex items-center gap-1.5">
              {trend && (
                <span className={cn("text-xs font-medium", trend.positive ? "text-green-500" : "text-red-500")}>
                  {trend.positive ? "↑" : "↓"} {trend.value}
                </span>
              )}
              {subtitle && <span className="text-xs text-muted-foreground truncate">{subtitle}</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface StatsGridProps {
  children: React.ReactNode;
  columns?: 2 | 3 | 4;
  className?: string;
}

export function StatsGrid({ children, columns = 4, className }: StatsGridProps) {
  const colClass = {
    2: "grid-cols-1 sm:grid-cols-2",
    3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
    4: "grid-cols-2 lg:grid-cols-4",
  }[columns];

  return (
    <div className={cn("grid gap-3", colClass, className)}>
      {children}
    </div>
  );
}
