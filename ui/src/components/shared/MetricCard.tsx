import { cn } from "../../lib/utils";
import type { BadgeVariant } from "./StatusBadge";

interface MetricCardProps {
  /** Main value to display (e.g., "67%", "130", "2/3") */
  value: string | number;
  /** Label describing the metric */
  label: string;
  /** Optional subtext for additional context */
  subtext?: string;
  /** Visual variant based on the metric's meaning */
  variant?: BadgeVariant;
  /** Size variant */
  size?: "sm" | "md" | "lg";
  /** Optional click handler */
  onClick?: () => void;
  className?: string;
  /** Test ID for e2e tests */
  testId?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  success: "bg-success/5 border-success/20",
  warning: "bg-warning/5 border-warning/20",
  error: "bg-destructive/5 border-destructive/20",
  info: "bg-info/5 border-info/20",
  neutral: "bg-muted/50 border-border",
  default: "bg-card border-border",
};

const sizeStyles: Record<"sm" | "md" | "lg", { container: string; value: string; label: string; subtext: string }> = {
  sm: {
    container: "p-2",
    value: "text-lg font-bold text-foreground",
    label: "text-[10px] text-muted-foreground",
    subtext: "text-[9px] text-muted-foreground/70",
  },
  md: {
    container: "p-3",
    value: "text-xl font-bold text-foreground",
    label: "text-xs text-muted-foreground",
    subtext: "text-[10px] text-muted-foreground/70",
  },
  lg: {
    container: "p-4",
    value: "text-2xl font-bold text-foreground",
    label: "text-sm text-muted-foreground",
    subtext: "text-xs text-muted-foreground/70",
  },
};

/**
 * Consistent metric/KPI card component used across all screens.
 * Displays a primary value with label and optional subtext.
 */
export function MetricCard({
  value,
  label,
  subtext,
  variant = "default",
  size = "md",
  onClick,
  className,
  testId,
}: MetricCardProps) {
  const styles = sizeStyles[size];
  const Component = onClick ? "button" : "div";

  return (
    <Component
      onClick={onClick}
      data-testid={testId}
      className={cn(
        "rounded-lg border shadow-sm text-left",
        styles.container,
        variantStyles[variant],
        onClick && "cursor-pointer hover:shadow-md transition-shadow",
        className
      )}
    >
      <div className={styles.value}>{value}</div>
      <div className={styles.label}>{label}</div>
      {subtext && <div className={styles.subtext}>{subtext}</div>}
    </Component>
  );
}

/**
 * Helper to determine variant based on a percentage score
 */
export function getScoreVariant(score: number): BadgeVariant {
  if (score >= 80) return "success";
  if (score >= 60) return "warning";
  if (score > 0) return "error";
  return "default";
}

/**
 * Metric card that shows a delta/change compared to baseline
 */
interface DeltaMetricCardProps {
  label: string;
  current: number;
  baseline: number;
  delta: number;
  isPercent?: boolean;
  size?: "sm" | "md" | "lg";
}

export function DeltaMetricCard({
  label,
  current,
  baseline,
  delta,
  isPercent = true,
  size = "md",
}: DeltaMetricCardProps) {
  const styles = sizeStyles[size];
  const isPositive = delta > 0;
  const isNegative = delta < 0;

  return (
    <div className={cn("rounded-lg border shadow-sm bg-card", styles.container)}>
      <div className={styles.value}>
        {current}{isPercent ? "%" : ""}
        {delta !== 0 && (
          <span
            className={cn(
              "ml-2 text-sm",
              isPositive && "text-success",
              isNegative && "text-destructive",
              !isPositive && !isNegative && "text-muted-foreground/70"
            )}
          >
            {isPositive ? "+" : ""}{delta}{isPercent ? "%" : ""}
          </span>
        )}
      </div>
      <div className={styles.label}>{label}</div>
      <div className={styles.subtext}>was {baseline}{isPercent ? "%" : ""}</div>
    </div>
  );
}

/**
 * Horizontal row of metric cards with consistent spacing
 */
interface MetricCardRowProps {
  children: React.ReactNode;
  columns?: 3 | 4 | 5 | 6;
  className?: string;
  /** Test ID for e2e tests */
  testId?: string;
}

export function MetricCardRow({ children, columns = 5, className, testId }: MetricCardRowProps) {
  const gridCols = {
    3: "grid-cols-3",
    4: "grid-cols-2 md:grid-cols-4",
    5: "grid-cols-3 md:grid-cols-5",
    6: "grid-cols-3 md:grid-cols-6",
  };

  return (
    <div data-testid={testId} className={cn("grid gap-3", gridCols[columns], className)}>
      {children}
    </div>
  );
}
