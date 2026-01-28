import { CheckCircle, AlertTriangle, XCircle, AlertCircle } from "lucide-react";
import type { ReconciliationGate } from "../../types";
import { cn } from "../../lib/utils";

interface ReconciliationStatusCardProps {
  gate: ReconciliationGate;
  factCount: number;
}

/**
 * Card showing reconciliation gate status with metrics and reasons.
 */
export function ReconciliationStatusCard({
  gate,
  factCount,
}: ReconciliationStatusCardProps) {
  const statusConfig = {
    pass: {
      icon: CheckCircle,
      label: "PASS",
      bgColor: "bg-success/10",
      borderColor: "border-success/30",
      textColor: "text-success",
      badgeColor: "bg-success/20 text-success",
    },
    warn: {
      icon: AlertTriangle,
      label: "WARN",
      bgColor: "bg-warning/10",
      borderColor: "border-warning/30",
      textColor: "text-warning",
      badgeColor: "bg-warning/20 text-warning",
    },
    fail: {
      icon: XCircle,
      label: "FAIL",
      bgColor: "bg-destructive/10",
      borderColor: "border-destructive/30",
      textColor: "text-destructive",
      badgeColor: "bg-destructive/20 text-destructive",
    },
  };

  const config = statusConfig[gate.status];
  const StatusIcon = config.icon;

  const coveragePct = Math.round(gate.provenance_coverage * 100);
  const missingCount = gate.missing_critical_facts.length;

  return (
    <div
      className={cn(
        "rounded-lg border overflow-hidden",
        config.bgColor,
        config.borderColor
      )}
    >
      {/* Header */}
      <div className="px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <StatusIcon className={cn("h-5 w-5", config.textColor)} />
          <h3 className="font-semibold text-foreground">
            Reconciliation Status
          </h3>
        </div>
        <span
          className={cn(
            "px-3 py-1 rounded-full text-sm font-bold",
            config.badgeColor
          )}
        >
          {config.label}
        </span>
      </div>

      {/* Metrics */}
      <div className="px-4 py-2 bg-card/50 border-t border-b border-border">
        <div className="flex items-center gap-4 text-sm">
          <MetricBadge
            value={gate.conflict_count}
            label="conflict"
            pluralLabel="conflicts"
            type={gate.conflict_count > 0 ? "warning" : "neutral"}
          />
          <MetricBadge
            value={missingCount}
            label="missing critical"
            pluralLabel="missing critical"
            type={missingCount > 0 ? "error" : "neutral"}
          />
          <MetricBadge
            value={factCount}
            label="fact"
            pluralLabel="facts"
            type="neutral"
          />
          <MetricBadge
            value={`${coveragePct}%`}
            label="coverage"
            type={coveragePct >= 80 ? "success" : coveragePct >= 50 ? "warning" : "error"}
          />
        </div>
      </div>

      {/* Reasons */}
      {gate.reasons.length > 0 && (
        <div className="px-4 py-3">
          <div className="flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Reasons
              </span>
              <ul className="space-y-1">
                {gate.reasons.map((reason, idx) => (
                  <li
                    key={idx}
                    className="text-sm text-foreground"
                  >
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Missing Critical Facts */}
      {missingCount > 0 && (
        <div className="px-4 py-3 border-t border-border">
          <div className="flex items-start gap-2">
            <XCircle className="h-4 w-4 text-destructive mt-0.5 flex-shrink-0" />
            <div className="space-y-1">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Missing Critical Facts
              </span>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {gate.missing_critical_facts.map((fact) => (
                  <span
                    key={fact}
                    className="px-2 py-0.5 text-xs font-medium rounded bg-destructive/10 text-destructive"
                  >
                    {fact.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface MetricBadgeProps {
  value: number | string;
  label: string;
  pluralLabel?: string;
  type: "success" | "warning" | "error" | "neutral";
}

function MetricBadge({ value, label, pluralLabel, type }: MetricBadgeProps) {
  const typeColors = {
    success: "text-success",
    warning: "text-warning",
    error: "text-destructive",
    neutral: "text-muted-foreground",
  };

  const numValue = typeof value === "number" ? value : parseInt(value, 10);
  const displayLabel = pluralLabel && numValue !== 1 ? pluralLabel : label;

  return (
    <span className={cn("font-medium", typeColors[type])}>
      {value} {displayLabel}
    </span>
  );
}
