import { cn } from "../../lib/utils";

export type BadgeVariant = "success" | "warning" | "error" | "info" | "neutral" | "default";

interface StatusBadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: "sm" | "md";
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  success: "bg-success/10 text-success border-success/20",
  warning: "bg-warning/10 text-warning-foreground border-warning/20",
  error: "bg-destructive/10 text-destructive border-destructive/20",
  info: "bg-info/10 text-info border-info/20",
  neutral: "bg-muted text-muted-foreground border-border",
  default: "bg-muted/50 text-muted-foreground border-border",
};

const sizeStyles: Record<"sm" | "md", string> = {
  sm: "text-[10px] px-1.5 py-0.5",
  md: "text-xs px-2 py-1",
};

/**
 * Consistent status badge component used across all screens.
 * Replaces various inline badge implementations for visual consistency.
 */
export function StatusBadge({
  children,
  variant = "default",
  size = "sm",
  className
}: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center font-medium rounded border",
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
    >
      {children}
    </span>
  );
}

// Pre-configured badge variants for common use cases

export function LatestBadge() {
  return <StatusBadge variant="info">Latest</StatusBadge>;
}

export function BaselineBadge() {
  return <StatusBadge variant="success">Baseline</StatusBadge>;
}

export function CompleteBadge() {
  return <StatusBadge variant="success">Complete</StatusBadge>;
}

export function PartialBadge() {
  return <StatusBadge variant="warning">Partial</StatusBadge>;
}

export function PassBadge({ count }: { count?: number }) {
  return (
    <StatusBadge variant="success">
      {count !== undefined ? `${count} ` : ""}PASS
    </StatusBadge>
  );
}

export function WarnBadge({ count }: { count?: number }) {
  return (
    <StatusBadge variant="warning">
      {count !== undefined ? `${count} ` : ""}WARN
    </StatusBadge>
  );
}

export function FailBadge({ count }: { count?: number }) {
  return (
    <StatusBadge variant="error">
      {count !== undefined ? `${count} ` : ""}FAIL
    </StatusBadge>
  );
}

export function LabeledBadge() {
  return <StatusBadge variant="success">Labeled</StatusBadge>;
}

export function UnlabeledBadge() {
  return <StatusBadge variant="neutral">Unlabeled</StatusBadge>;
}

export function PendingBadge() {
  return <StatusBadge variant="neutral">Pending</StatusBadge>;
}

export function ConfirmedBadge() {
  return <StatusBadge variant="success">Confirmed</StatusBadge>;
}

export function NotInRunBadge() {
  return <StatusBadge variant="neutral">Not in run</StatusBadge>;
}

export function RequiredBadge() {
  return <StatusBadge variant="error">Required</StatusBadge>;
}

// Outcome badges for field labeling
export function CorrectBadge() {
  return <StatusBadge variant="success">Correct</StatusBadge>;
}

export function IncorrectBadge() {
  return <StatusBadge variant="error">Incorrect</StatusBadge>;
}

export function MissingBadge() {
  return <StatusBadge variant="warning">Missing</StatusBadge>;
}

export function UnverifiableBadge() {
  return <StatusBadge variant="neutral">Unverifiable</StatusBadge>;
}

/**
 * Score badge that shows a percentage with color coding
 */
export function ScoreBadge({ value, showPercent = true }: { value: number; showPercent?: boolean }) {
  const variant: BadgeVariant =
    value >= 80 ? "success" :
    value >= 60 ? "warning" :
    value > 0 ? "error" : "neutral";

  return (
    <span className={cn(
      "font-medium",
      variant === "success" && "text-success",
      variant === "warning" && "text-warning-foreground",
      variant === "error" && "text-destructive",
      variant === "neutral" && "text-muted-foreground"
    )}>
      {value}{showPercent ? "%" : ""}
    </span>
  );
}

/**
 * Gate status badge that shows PASS/WARN/FAIL with count
 */
export function GateStatusBadge({
  status,
  count
}: {
  status: "pass" | "warn" | "fail";
  count?: number;
}) {
  switch (status) {
    case "pass":
      return <PassBadge count={count} />;
    case "warn":
      return <WarnBadge count={count} />;
    case "fail":
      return <FailBadge count={count} />;
  }
}

/**
 * Outcome badge for field extraction results
 */
export function OutcomeBadge({ outcome }: { outcome: string | null }) {
  if (!outcome) return <span className="text-muted-foreground/50">-</span>;

  // Map outcomes to variants
  const outcomeMap: Record<string, { label: string; variant: BadgeVariant }> = {
    // Truth-based outcomes (v3)
    correct: { label: "Correct", variant: "success" },
    incorrect: { label: "Incorrect", variant: "error" },
    missing: { label: "Missing", variant: "warning" },
    unverifiable: { label: "Unverifiable", variant: "neutral" },
    // Legacy outcomes (backwards compatibility)
    match: { label: "Correct", variant: "success" },
    mismatch: { label: "Incorrect", variant: "error" },
    miss: { label: "Missing", variant: "warning" },
    extractor_miss: { label: "Missing", variant: "warning" },
    cannot_verify: { label: "Unknown", variant: "neutral" },
    correct_absent: { label: "Correct", variant: "neutral" },
  };

  const config = outcomeMap[outcome] || { label: outcome, variant: "neutral" as BadgeVariant };

  return <StatusBadge variant={config.variant}>{config.label}</StatusBadge>;
}
