import { cn } from "../../lib/utils";

interface ChartCardProps {
  title: string;
  children: React.ReactNode;
  className?: string;
  height?: string;
}

/**
 * Consistent wrapper for chart components with title and styling
 */
export function ChartCard({ title, children, className, height = "h-[200px]" }: ChartCardProps) {
  return (
    <div className={cn("bg-card rounded-lg border shadow-sm p-4", className)}>
      <h3 className="text-sm font-semibold text-foreground mb-3">{title}</h3>
      <div className={cn("w-full", height)}>
        {children}
      </div>
    </div>
  );
}
