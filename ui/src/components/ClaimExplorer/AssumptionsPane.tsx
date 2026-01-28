import { AlertTriangle, Info } from "lucide-react";
import { cn } from "../../lib/utils";
import type { AssessmentAssumption, AssumptionImpact } from "../../types";
import { StatusBadge } from "../shared";

interface AssumptionsPaneProps {
  assumptions: AssessmentAssumption[];
  className?: string;
}

const impactConfig: Record<AssumptionImpact, { variant: "error" | "warning" | "neutral"; label: string }> = {
  high: { variant: "error", label: "High" },
  medium: { variant: "warning", label: "Medium" },
  low: { variant: "neutral", label: "Low" },
};

/**
 * Displays assumptions made during claim assessment.
 * Sorted by impact (high first) with color-coded badges.
 */
export function AssumptionsPane({ assumptions, className }: AssumptionsPaneProps) {
  // Sort assumptions by impact (high > medium > low)
  const sortedAssumptions = [...assumptions].sort((a, b) => {
    const order: Record<AssumptionImpact, number> = { high: 0, medium: 1, low: 2 };
    return order[a.impact] - order[b.impact];
  });

  const criticalCount = assumptions.filter((a) => a.impact === "high").length;

  if (assumptions.length === 0) {
    return (
      <div className={cn("bg-card rounded-lg border border-border", className)}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <Info className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-foreground">Assumptions</h3>
        </div>
        <div className="p-4 text-center">
          <p className="text-sm text-muted-foreground">No assumptions made</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("bg-card rounded-lg border border-border", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-warning" />
          <h3 className="text-sm font-medium text-foreground">
            Assumptions
          </h3>
          <span className="text-xs text-muted-foreground">
            ({assumptions.length})
          </span>
        </div>
        {criticalCount > 0 && (
          <StatusBadge variant="error" size="sm">
            {criticalCount} High Impact
          </StatusBadge>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="text-left px-4 py-2 font-medium text-foreground w-10">#</th>
              <th className="text-left px-4 py-2 font-medium text-foreground">Field</th>
              <th className="text-left px-4 py-2 font-medium text-foreground">Assumed Value</th>
              <th className="text-center px-4 py-2 font-medium text-foreground">Impact</th>
              <th className="text-left px-4 py-2 font-medium text-foreground">Reason</th>
            </tr>
          </thead>
          <tbody>
            {sortedAssumptions.map((assumption, idx) => {
              const config = impactConfig[assumption.impact];
              return (
                <tr
                  key={`${assumption.check_number}-${assumption.field}-${idx}`}
                  className={cn(
                    "border-b border-border hover:bg-muted/50",
                    assumption.impact === "high" && "bg-destructive/5"
                  )}
                >
                  <td className="px-4 py-2 text-muted-foreground font-mono text-xs">
                    {assumption.check_number}
                  </td>
                  <td className="px-4 py-2 font-medium text-foreground">
                    {formatFieldName(assumption.field)}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground font-mono text-xs">
                    {assumption.assumed_value || <span className="opacity-60 italic">empty</span>}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <StatusBadge variant={config.variant} size="sm">
                      {config.label}
                    </StatusBadge>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground text-xs max-w-[200px] truncate" title={assumption.reason}>
                    {assumption.reason}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Format field name from snake_case to Title Case */
function formatFieldName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
