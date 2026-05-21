import { cn } from "@/lib/utils";

interface PageContainerProps {
  children: React.ReactNode;
  className?: string;
}

export function PageContainer({ children, className }: PageContainerProps) {
  return (
    <div className={cn("mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8 space-y-6", className)}>
      {children}
    </div>
  );
}

export function PageSection({ children, className }: PageContainerProps) {
  return (
    <section className={cn("space-y-4", className)}>
      {children}
    </section>
  );
}
