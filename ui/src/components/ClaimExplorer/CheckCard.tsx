import { CheckCircle2, XCircle, HelpCircle, AlertTriangle, ExternalLink } from "lucide-react";
import { cn } from "../../lib/utils";
import type { AssessmentCheck, CheckResult } from "../../types";
import { StatusBadge } from "../shared";

interface CheckCardProps {
  check: AssessmentCheck;
  isExpanded?: boolean;
  onToggle?: () => void;
  onEvidenceClick?: (ref: string) => void;
}

const resultConfig: Record<CheckResult, {
  icon: typeof CheckCircle2;
  variant: "success" | "error" | "warning";
  label: string;
}> = {
  PASS: { icon: CheckCircle2, variant: "success", label: "PASS" },
  FAIL: { icon: XCircle, variant: "error", label: "FAIL" },
  INCONCLUSIVE: { icon: HelpCircle, variant: "warning", label: "INCONCLUSIVE" },
};

/**
 * Single assessment check display with expandable details.
 */
export function CheckCard({ check, isExpanded = false, onToggle, onEvidenceClick }: CheckCardProps) {
  const config = resultConfig[check.result];
  const Icon = config.icon;
  const hasNoEvidence = check.evidence_refs.length === 0;

  return (
    <div
      className={cn(
        "border rounded-lg overflow-hidden transition-colors",
        check.result === "FAIL" && "border-red-200 dark:border-red-900",
        check.result === "INCONCLUSIVE" && "border-amber-200 dark:border-amber-900",
        check.result === "PASS" && "border-slate-200 dark:border-slate-700"
      )}
    >
      {/* Header */}
      <button
        onClick={onToggle}
        className={cn(
          "w-full flex items-center gap-3 px-4 py-3 text-left transition-colors",
          "hover:bg-slate-50 dark:hover:bg-slate-800/50",
          isExpanded && "bg-slate-50 dark:bg-slate-800/50"
        )}
      >
        <Icon className={cn(
          "h-5 w-5 flex-shrink-0",
          config.variant === "success" && "text-green-500",
          config.variant === "error" && "text-red-500",
          config.variant === "warning" && "text-amber-500"
        )} />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 font-mono">#{check.check_number}</span>
            <span className="font-medium text-slate-700 dark:text-slate-200 truncate">
              {check.check_name}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {hasNoEvidence && (
            <AlertTriangle className="h-4 w-4 text-amber-500" title="No evidence linked" />
          )}
          <StatusBadge variant={config.variant} size="sm">
            {config.label}
          </StatusBadge>
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-4 pb-4 pt-2 border-t border-slate-100 dark:border-slate-800">
          {/* Details */}
          <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">
            {check.details}
          </p>

          {/* Evidence References */}
          <div className="space-y-1">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
              Evidence ({check.evidence_refs.length})
            </span>
            {check.evidence_refs.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {check.evidence_refs.map((ref, idx) => (
                  <button
                    key={idx}
                    onClick={() => onEvidenceClick?.(ref)}
                    className={cn(
                      "inline-flex items-center gap-1 px-2 py-1 rounded text-xs",
                      "bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400",
                      "hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors"
                    )}
                  >
                    <ExternalLink className="h-3 w-3" />
                    {formatEvidenceRef(ref)}
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />
                No evidence linked to this check
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** Format evidence reference for display (e.g., "doc_123:page_2" -> "Doc 123, Page 2") */
function formatEvidenceRef(ref: string): string {
  // Simple formatting - can be enhanced based on actual ref format
  return ref
    .replace(/_/g, " ")
    .replace(/:/g, ", ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
