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
  success: "bg-green-50 border-green-200",
  warning: "bg-yellow-50 border-yellow-200",
  error: "bg-red-50 border-red-200",
  info: "bg-blue-50 border-blue-200",
  neutral: "bg-gray-50 border-gray-200",
  default: "bg-white border-gray-200",
};

const sizeStyles: Record<"sm" | "md" | "lg", { container: string; value: string; label: string; subtext: string }> = {
  sm: {
    container: "p-2",
    value: "text-lg font-bold",
    label: "text-[10px] text-gray-600",
    subtext: "text-[9px] text-gray-400",
  },
  md: {
    container: "p-3",
    value: "text-xl font-bold",
    label: "text-xs text-gray-600",
    subtext: "text-[10px] text-gray-400",
  },
  lg: {
    container: "p-4",
    value: "text-2xl font-bold",
    label: "text-sm text-gray-600",
    subtext: "text-xs text-gray-400",
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
    <div className={cn("rounded-lg border shadow-sm bg-white", styles.container)}>
      <div className={styles.value}>
        {current}{isPercent ? "%" : ""}
        {delta !== 0 && (
          <span
            className={cn(
              "ml-2 text-sm",
              isPositive && "text-green-600",
              isNegative && "text-red-600",
              !isPositive && !isNegative && "text-gray-400"
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
