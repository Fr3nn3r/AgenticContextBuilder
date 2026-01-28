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
      <div className={cn("bg-card rounded-lg border border-border", className)}>
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-foreground">Assessment Checks</h3>
        </div>
        <div className="p-4 text-center">
          <p className="text-sm text-muted-foreground">No checks performed</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("bg-card rounded-lg border border-border", className)}>
      {/* Header with summary badges */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-foreground">
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
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-muted/50">
        <Filter className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">Filter:</span>
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
          <p className="text-center text-sm text-muted-foreground py-4">
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
            ? "bg-destructive/10 text-destructive ring-1 ring-destructive/30"
            : variant === "warning"
            ? "bg-warning/10 text-warning ring-1 ring-warning/30"
            : "bg-primary/10 text-primary ring-1 ring-primary/30"
          : "bg-muted text-muted-foreground hover:bg-muted/80"
      )}
    >
      {label} ({count})
    </button>
  );
}
