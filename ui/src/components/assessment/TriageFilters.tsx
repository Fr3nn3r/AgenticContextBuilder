import { Filter, X } from "lucide-react";
import { cn } from "../../lib/utils";
import type {
  TriagePriority,
  TriageReason,
  AssessmentDecision,
  TriageQueueFilters,
} from "../../types";

interface TriageFiltersProps {
  filters: TriageQueueFilters;
  onFiltersChange: (filters: TriageQueueFilters) => void;
  className?: string;
}

const PRIORITY_OPTIONS: { value: TriagePriority; label: string; color: string }[] = [
  { value: "critical", label: "Critical", color: "bg-red-500" },
  { value: "high", label: "High", color: "bg-orange-500" },
  { value: "medium", label: "Medium", color: "bg-amber-500" },
  { value: "low", label: "Low", color: "bg-slate-400" },
];

const REASON_OPTIONS: { value: TriageReason; label: string }[] = [
  { value: "low_confidence", label: "Low Confidence" },
  { value: "high_impact_assumption", label: "High Impact Assumption" },
  { value: "fraud_indicator", label: "Fraud Indicator" },
  { value: "inconclusive_check", label: "Inconclusive Check" },
  { value: "conflicting_evidence", label: "Conflicting Evidence" },
];

const DECISION_OPTIONS: { value: AssessmentDecision; label: string }[] = [
  { value: "APPROVE", label: "Approve" },
  { value: "REJECT", label: "Reject" },
  { value: "REFER_TO_HUMAN", label: "Refer to Human" },
];

/**
 * Filter controls for the triage queue with URL persistence.
 */
export function TriageFilters({ filters, onFiltersChange, className }: TriageFiltersProps) {
  const hasActiveFilters =
    (filters.priority?.length ?? 0) > 0 ||
    (filters.reasons?.length ?? 0) > 0 ||
    (filters.decision?.length ?? 0) > 0 ||
    filters.min_confidence !== undefined ||
    filters.max_confidence !== undefined;

  const togglePriority = (priority: TriagePriority) => {
    const current = filters.priority || [];
    const updated = current.includes(priority)
      ? current.filter((p) => p !== priority)
      : [...current, priority];
    onFiltersChange({ ...filters, priority: updated.length > 0 ? updated : undefined });
  };

  const toggleReason = (reason: TriageReason) => {
    const current = filters.reasons || [];
    const updated = current.includes(reason)
      ? current.filter((r) => r !== reason)
      : [...current, reason];
    onFiltersChange({ ...filters, reasons: updated.length > 0 ? updated : undefined });
  };

  const toggleDecision = (decision: AssessmentDecision) => {
    const current = filters.decision || [];
    const updated = current.includes(decision)
      ? current.filter((d) => d !== decision)
      : [...current, decision];
    onFiltersChange({ ...filters, decision: updated.length > 0 ? updated : undefined });
  };

  const clearFilters = () => {
    onFiltersChange({});
  };

  return (
    <div className={cn("bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-4", className)}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-500" />
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200">Filters</h3>
        </div>
        {hasActiveFilters && (
          <button
            onClick={clearFilters}
            className="text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 flex items-center gap-1"
          >
            <X className="h-3 w-3" />
            Clear all
          </button>
        )}
      </div>

      <div className="space-y-4">
        {/* Priority Filter */}
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2 block">
            Priority
          </label>
          <div className="flex flex-wrap gap-2">
            {PRIORITY_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => togglePriority(option.value)}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1.5 rounded-full text-xs font-medium transition-all",
                  filters.priority?.includes(option.value)
                    ? "bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-900"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
                )}
              >
                <span className={cn("w-2 h-2 rounded-full", option.color)} />
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Reason Filter */}
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2 block">
            Reason
          </label>
          <div className="flex flex-wrap gap-2">
            {REASON_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => toggleReason(option.value)}
                className={cn(
                  "px-2.5 py-1.5 rounded-full text-xs font-medium transition-all",
                  filters.reasons?.includes(option.value)
                    ? "bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-900"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Decision Filter */}
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2 block">
            Decision
          </label>
          <div className="flex flex-wrap gap-2">
            {DECISION_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => toggleDecision(option.value)}
                className={cn(
                  "px-2.5 py-1.5 rounded-full text-xs font-medium transition-all",
                  filters.decision?.includes(option.value)
                    ? "bg-slate-800 dark:bg-slate-200 text-white dark:text-slate-900"
                    : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700"
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        {/* Confidence Range */}
        <div>
          <label className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2 block">
            Confidence Range
          </label>
          <div className="flex items-center gap-2">
            <input
              type="number"
              min={0}
              max={100}
              placeholder="Min"
              value={filters.min_confidence ?? ""}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  min_confidence: e.target.value ? Number(e.target.value) : undefined,
                })
              }
              className="w-20 px-2 py-1 text-xs border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800"
            />
            <span className="text-xs text-slate-400">to</span>
            <input
              type="number"
              min={0}
              max={100}
              placeholder="Max"
              value={filters.max_confidence ?? ""}
              onChange={(e) =>
                onFiltersChange({
                  ...filters,
                  max_confidence: e.target.value ? Number(e.target.value) : undefined,
                })
              }
              className="w-20 px-2 py-1 text-xs border border-slate-300 dark:border-slate-600 rounded bg-white dark:bg-slate-800"
            />
            <span className="text-xs text-slate-400">%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
