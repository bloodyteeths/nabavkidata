import { cn } from "@/lib/utils";

interface TenderStatsProps {
  stats: { total: number; open: number; awarded: number };
  activeStatus: string;
  onStatusChange: (status: string) => void;
  loading?: boolean;
}

export function TenderStats({ stats, activeStatus, onStatusChange, loading }: TenderStatsProps) {
  const tabs = [
    { key: 'open', label: 'Отворени', count: stats.open },
    { key: 'awarded', label: 'Доделени', count: stats.awarded },
    { key: 'all', label: 'Сите', count: stats.total },
  ];

  return (
    <div className="flex gap-2 overflow-x-auto pb-1">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onStatusChange(tab.key)}
          className={cn(
            "flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all whitespace-nowrap",
            activeStatus === tab.key
              ? "bg-primary text-primary-foreground shadow-md"
              : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
          )}
        >
          {tab.label}
          <span className={cn(
            "text-xs px-1.5 py-0.5 rounded-md",
            activeStatus === tab.key
              ? "bg-primary-foreground/20 text-primary-foreground"
              : "bg-background text-muted-foreground"
          )}>
            {loading ? '...' : tab.count.toLocaleString()}
          </span>
        </button>
      ))}
    </div>
  );
}
