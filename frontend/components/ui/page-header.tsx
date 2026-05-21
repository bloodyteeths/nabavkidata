import { cn } from "@/lib/utils";
import type { LucideIcon } from "lucide-react";

interface PageHeaderProps {
  icon?: LucideIcon;
  iconColor?: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
  className?: string;
}

export function PageHeader({ icon: Icon, iconColor = "text-primary", title, description, children, className }: PageHeaderProps) {
  return (
    <div className={cn("flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between", className)}>
      <div className="flex items-center gap-3 min-w-0">
        {Icon && (
          <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10", iconColor.includes("bg-") ? iconColor : "")}>
            <Icon className={cn("h-5 w-5", iconColor.includes("bg-") ? "text-white" : iconColor)} />
          </div>
        )}
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-foreground sm:text-2xl truncate">{title}</h1>
          {description && (
            <p className="text-sm text-muted-foreground line-clamp-2">{description}</p>
          )}
        </div>
      </div>
      {children && <div className="flex items-center gap-2 shrink-0">{children}</div>}
    </div>
  );
}
