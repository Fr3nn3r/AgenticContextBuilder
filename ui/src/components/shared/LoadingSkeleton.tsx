import { cn } from "../../lib/utils";

interface SkeletonProps {
  className?: string;
}

/**
 * Base skeleton pulse animation
 */
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse bg-muted rounded",
        className
      )}
    />
  );
}

/**
 * Skeleton for text lines
 */
export function TextSkeleton({ lines = 1, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={cn(
            "h-4",
            i === lines - 1 && lines > 1 ? "w-3/4" : "w-full"
          )}
        />
      ))}
    </div>
  );
}

/**
 * Skeleton for metric cards
 */
export function MetricCardSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className={cn("grid gap-3", `grid-cols-${Math.min(count, 3)} md:grid-cols-${count}`)}>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border bg-card p-3 shadow-sm">
          <Skeleton className="h-7 w-16 mb-2" />
          <Skeleton className="h-3 w-20 mb-1" />
          <Skeleton className="h-2 w-24" />
        </div>
      ))}
    </div>
  );
}

/**
 * Skeleton for table rows
 */
export function TableRowSkeleton({ columns = 5, rows = 5 }: { columns?: number; rows?: number }) {
  return (
    <div className="bg-card rounded-lg border border-border shadow-sm overflow-hidden">
      {/* Header skeleton */}
      <div className="border-b border-border bg-muted/50 p-3 flex gap-4">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {/* Row skeletons */}
      {Array.from({ length: rows }).map((_, rowIdx) => (
        <div key={rowIdx} className="border-b border-border p-3 flex gap-4">
          {Array.from({ length: columns }).map((_, colIdx) => (
            <Skeleton key={colIdx} className="h-4 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

/**
 * Skeleton for sidebar run list
 */
export function RunListSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg border border-border bg-card p-3">
          <div className="flex items-center gap-2 mb-2">
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-14" />
          </div>
          <Skeleton className="h-3 w-32 mb-1" />
          <Skeleton className="h-3 w-24" />
        </div>
      ))}
    </div>
  );
}

/**
 * Full page loading state
 */
export function PageLoadingSkeleton({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <div className="relative">
        <div className="w-12 h-12 border-4 border-muted border-t-foreground rounded-full animate-spin" />
      </div>
      <p className="text-muted-foreground text-sm">{message}</p>
    </div>
  );
}

/**
 * Inline loading spinner
 */
export function Spinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const sizeStyles = {
    sm: "w-4 h-4 border-2",
    md: "w-6 h-6 border-2",
    lg: "w-8 h-8 border-3",
  };

  return (
    <div
      className={cn(
        "border-muted border-t-foreground rounded-full animate-spin",
        sizeStyles[size]
      )}
    />
  );
}

/**
 * Loading state for document viewer panel
 */
export function DocumentViewerSkeleton() {
  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <Skeleton className="h-6 w-48" />
        <div className="flex gap-2">
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-8 w-16" />
        </div>
      </div>
      <Skeleton className="h-[400px] w-full" />
    </div>
  );
}

/**
 * Loading state for field extraction list
 */
export function FieldListSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="border border-border rounded-lg p-3 bg-card">
          <div className="flex items-center justify-between mb-2">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-5 w-16" />
          </div>
          <Skeleton className="h-4 w-40 mb-2" />
          <div className="flex gap-2">
            <Skeleton className="h-7 w-24" />
            <Skeleton className="h-7 w-20" />
            <Skeleton className="h-7 w-28" />
          </div>
        </div>
      ))}
    </div>
  );
}
