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
      <div className={cn("bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700", className)}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <Info className="h-4 w-4 text-slate-400" />
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200">Assumptions</h3>
        </div>
        <div className="p-4 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">No assumptions made</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Assumptions
          </h3>
          <span className="text-xs text-slate-500 dark:text-slate-400">
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
            <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
              <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300 w-10">#</th>
              <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Field</th>
              <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Assumed Value</th>
              <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Impact</th>
              <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Reason</th>
            </tr>
          </thead>
          <tbody>
            {sortedAssumptions.map((assumption, idx) => {
              const config = impactConfig[assumption.impact];
              return (
                <tr
                  key={`${assumption.check_number}-${assumption.field}-${idx}`}
                  className={cn(
                    "border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50",
                    assumption.impact === "high" && "bg-red-50/50 dark:bg-red-900/10"
                  )}
                >
                  <td className="px-4 py-2 text-slate-500 dark:text-slate-400 font-mono text-xs">
                    {assumption.check_number}
                  </td>
                  <td className="px-4 py-2 font-medium text-slate-700 dark:text-slate-200">
                    {formatFieldName(assumption.field)}
                  </td>
                  <td className="px-4 py-2 text-slate-600 dark:text-slate-300 font-mono text-xs">
                    {assumption.assumed_value || <span className="text-slate-400 italic">empty</span>}
                  </td>
                  <td className="px-4 py-2 text-center">
                    <StatusBadge variant={config.variant} size="sm">
                      {config.label}
                    </StatusBadge>
                  </td>
                  <td className="px-4 py-2 text-slate-500 dark:text-slate-400 text-xs max-w-[200px] truncate" title={assumption.reason}>
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
