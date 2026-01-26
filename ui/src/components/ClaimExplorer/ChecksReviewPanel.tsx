import { useState } from "react";
import { ClipboardCheck, Filter } from "lucide-react";
import { cn } from "../../lib/utils";
import type { AssessmentCheck, CheckResult } from "../../types";
import { CheckCard } from "./CheckCard";
import { StatusBadge } from "../shared";

interface ChecksReviewPanelProps {
  checks: AssessmentCheck[];
  onEvidenceClick?: (ref: string) => void;
  className?: string;
}

type FilterMode = "all" | "FAIL" | "INCONCLUSIVE";

/**
 * Accordion panel for reviewing assessment checks.
 * Shows summary badges and allows filtering by result type.
 */
export function ChecksReviewPanel({ checks, onEvidenceClick, className }: ChecksReviewPanelProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [filter, setFilter] = useState<FilterMode>("all");

  // Count by result type
  const counts: Record<CheckResult, number> = {
    PASS: checks.filter((c) => c.result === "PASS").length,
    FAIL: checks.filter((c) => c.result === "FAIL").length,
    INCONCLUSIVE: checks.filter((c) => c.result === "INCONCLUSIVE").length,
  };

  // Filter checks based on current filter
  const filteredChecks = filter === "all"
    ? checks
    : checks.filter((c) => c.result === filter);

  // Auto-expand first failing check if any
  const handleToggle = (index: number) => {
    setExpandedIndex(expandedIndex === index ? null : index);
  };

  if (checks.length === 0) {
    return (
      <div className={cn("bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700", className)}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <ClipboardCheck className="h-4 w-4 text-slate-400" />
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200">Assessment Checks</h3>
        </div>
        <div className="p-4 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">No checks performed</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700", className)}>
      {/* Header with summary badges */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="h-4 w-4 text-slate-500" />
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Assessment Checks
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge variant="success" size="sm">
            {counts.PASS} PASS
          </StatusBadge>
          {counts.FAIL > 0 && (
            <StatusBadge variant="error" size="sm">
              {counts.FAIL} FAIL
            </StatusBadge>
          )}
          {counts.INCONCLUSIVE > 0 && (
            <StatusBadge variant="warning" size="sm">
              {counts.INCONCLUSIVE} INCONCLUSIVE
            </StatusBadge>
          )}
        </div>
      </div>

      {/* Filter chips */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50">
        <Filter className="h-3.5 w-3.5 text-slate-400" />
        <span className="text-xs text-slate-500 dark:text-slate-400">Filter:</span>
        <div className="flex gap-1">
          <FilterChip
            label="All"
            count={checks.length}
            isActive={filter === "all"}
            onClick={() => setFilter("all")}
          />
          <FilterChip
            label="FAIL"
            count={counts.FAIL}
            isActive={filter === "FAIL"}
            onClick={() => setFilter("FAIL")}
            variant="error"
          />
          <FilterChip
            label="INCONCLUSIVE"
            count={counts.INCONCLUSIVE}
            isActive={filter === "INCONCLUSIVE"}
            onClick={() => setFilter("INCONCLUSIVE")}
            variant="warning"
          />
        </div>
      </div>

      {/* Check cards */}
      <div className="p-4 space-y-2">
        {filteredChecks.length > 0 ? (
          filteredChecks.map((check, idx) => {
            // Find the original index for expansion tracking
            const originalIndex = checks.indexOf(check);
            return (
              <CheckCard
                key={`${check.check_number}-${idx}`}
                check={check}
                isExpanded={expandedIndex === originalIndex}
                onToggle={() => handleToggle(originalIndex)}
                onEvidenceClick={onEvidenceClick}
              />
            );
          })
        ) : (
          <p className="text-center text-sm text-slate-500 dark:text-slate-400 py-4">
            No {filter} checks found
          </p>
        )}
      </div>
    </div>
  );
}

interface FilterChipProps {
  label: string;
  count: number;
  isActive: boolean;
  onClick: () => void;
  variant?: "default" | "error" | "warning";
}

function FilterChip({ label, count, isActive, onClick, variant = "default" }: FilterChipProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-2 py-1 rounded text-xs font-medium transition-all",
        isActive
          ? variant === "error"
            ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 ring-1 ring-red-300 dark:ring-red-700"
            : variant === "warning"
            ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 ring-1 ring-amber-300 dark:ring-amber-700"
            : "bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-200 ring-1 ring-slate-400 dark:ring-slate-600"
          : "bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700"
      )}
    >
      {label} ({count})
    </button>
  );
}
