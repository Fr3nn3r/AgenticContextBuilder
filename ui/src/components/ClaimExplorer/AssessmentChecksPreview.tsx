import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ClipboardCheck,
  FileText,
  ChevronRight,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { ClaimAssessment, AssessmentCheck } from "../../types";

interface AssessmentChecksPreviewProps {
  assessment: ClaimAssessment | null;
  loading?: boolean;
  maxItems?: number;
  onViewAll?: () => void;
  onEvidenceClick?: (ref: string) => void;
  className?: string;
}

type CheckResult = "PASS" | "FAIL" | "INCONCLUSIVE";

// Result icon component
function ResultIcon({
  result,
  size = "sm",
}: {
  result: CheckResult;
  size?: "sm" | "md";
}) {
  const sizeClass = size === "sm" ? "h-4 w-4" : "h-5 w-5";

  switch (result) {
    case "PASS":
      return <CheckCircle2 className={cn(sizeClass, "text-green-600 dark:text-green-400")} />;
    case "FAIL":
      return <XCircle className={cn(sizeClass, "text-red-600 dark:text-red-400")} />;
    case "INCONCLUSIVE":
      return <AlertTriangle className={cn(sizeClass, "text-amber-500")} />;
  }
}

// Evidence count badge
function EvidenceBadge({ count }: { count: number }) {
  if (count === 0) return null;

  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
      <FileText className="h-3 w-3" />
      {count}
    </span>
  );
}

// Compact check row
function CheckRow({
  check,
  onEvidenceClick,
}: {
  check: AssessmentCheck;
  onEvidenceClick?: (ref: string) => void;
}) {
  const evidenceCount = check.evidence_refs?.length || 0;

  return (
    <div
      className={cn(
        "flex items-center gap-2 py-2 px-3 border-b border-slate-100 dark:border-slate-800 last:border-b-0",
        "transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
      )}
    >
      <ResultIcon result={check.result} />

      <div className="flex-1 min-w-0">
        <span className="text-sm text-slate-700 dark:text-slate-200 truncate block">
          {check.check_name}
        </span>
      </div>

      <EvidenceBadge count={evidenceCount} />

      {evidenceCount > 0 && onEvidenceClick && (
        <button
          onClick={() => onEvidenceClick(check.evidence_refs[0])}
          className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
          title="View evidence"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

// Summary stats row
function SummaryRow({
  passCount,
  failCount,
  inconclusiveCount,
}: {
  passCount: number;
  failCount: number;
  inconclusiveCount: number;
}) {
  return (
    <div className="flex items-center gap-3 px-3 py-2 bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-700">
      <div className="flex items-center gap-1 text-xs">
        <CheckCircle2 className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
        <span className="font-semibold text-green-700 dark:text-green-400">{passCount}</span>
        <span className="text-slate-400">pass</span>
      </div>
      {failCount > 0 && (
        <div className="flex items-center gap-1 text-xs">
          <XCircle className="h-3.5 w-3.5 text-red-600 dark:text-red-400" />
          <span className="font-semibold text-red-700 dark:text-red-400">{failCount}</span>
          <span className="text-slate-400">fail</span>
        </div>
      )}
      {inconclusiveCount > 0 && (
        <div className="flex items-center gap-1 text-xs">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
          <span className="font-semibold text-amber-600 dark:text-amber-400">{inconclusiveCount}</span>
          <span className="text-slate-400">inconclusive</span>
        </div>
      )}
    </div>
  );
}

/**
 * Compact preview of assessment checks with evidence count badges.
 * Shows a limited number of checks with option to view all.
 */
export function AssessmentChecksPreview({
  assessment,
  loading,
  maxItems = 5,
  onViewAll,
  onEvidenceClick,
  className,
}: AssessmentChecksPreviewProps) {
  if (loading) {
    return (
      <div className={cn(
        "bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden",
        className
      )}>
        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-slate-400" />
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Assessment Checks
            </span>
          </div>
        </div>
        <div className="p-4">
          <div className="animate-pulse space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-8 bg-slate-100 dark:bg-slate-800 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (!assessment) {
    return (
      <div className={cn(
        "bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden",
        className
      )}>
        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-slate-400" />
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Assessment Checks
            </span>
          </div>
        </div>
        <div className="p-4 text-center">
          <p className="text-sm text-slate-500">No assessment available</p>
          <p className="text-xs text-slate-400 mt-1">Run an assessment to see checks</p>
        </div>
      </div>
    );
  }

  const checks = assessment.checks || [];
  const passCount = checks.filter((c) => c.result === "PASS").length;
  const failCount = checks.filter((c) => c.result === "FAIL").length;
  const inconclusiveCount = checks.filter((c) => c.result === "INCONCLUSIVE").length;

  // Sort checks: FAIL first, then INCONCLUSIVE, then PASS
  const sortedChecks = [...checks].sort((a, b) => {
    const order = { FAIL: 0, INCONCLUSIVE: 1, PASS: 2 };
    return order[a.result] - order[b.result];
  });

  const displayChecks = sortedChecks.slice(0, maxItems);
  const hasMore = checks.length > maxItems;

  return (
    <div className={cn(
      "bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden",
      className
    )}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ClipboardCheck className="h-4 w-4 text-slate-500" />
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Assessment Checks
          </span>
        </div>
        <span className="text-xs text-slate-400">
          {checks.length} checks
        </span>
      </div>

      {/* Summary stats */}
      <SummaryRow
        passCount={passCount}
        failCount={failCount}
        inconclusiveCount={inconclusiveCount}
      />

      {/* Check list */}
      <div className="divide-y divide-slate-100 dark:divide-slate-800">
        {displayChecks.map((check) => (
          <CheckRow
            key={check.check_number}
            check={check}
            onEvidenceClick={onEvidenceClick}
          />
        ))}
      </div>

      {/* View all link */}
      {hasMore && onViewAll && (
        <div className="px-3 py-2 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/30">
          <button
            onClick={onViewAll}
            className="w-full text-center text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300"
          >
            View all {checks.length} checks
          </button>
        </div>
      )}
    </div>
  );
}
