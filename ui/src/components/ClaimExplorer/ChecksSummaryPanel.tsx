import { CheckCircle2, XCircle, HelpCircle, ClipboardCheck } from "lucide-react";
import { cn } from "../../lib/utils";
import type { AssessmentCheck, CheckResult } from "../../types";

interface ChecksSummaryPanelProps {
  checks: AssessmentCheck[];
  onCheckClick?: (checkNumber: number) => void;
  className?: string;
}

const RESULT_CONFIG: Record<CheckResult, {
  icon: typeof CheckCircle2;
  dot: string;
  text: string;
  bg: string;
}> = {
  PASS: {
    icon: CheckCircle2,
    dot: "bg-emerald-500",
    text: "text-emerald-600 dark:text-emerald-400",
    bg: "bg-emerald-50 dark:bg-emerald-900/20",
  },
  FAIL: {
    icon: XCircle,
    dot: "bg-red-500",
    text: "text-red-600 dark:text-red-400",
    bg: "bg-red-50 dark:bg-red-900/20",
  },
  INCONCLUSIVE: {
    icon: HelpCircle,
    dot: "bg-amber-500",
    text: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-50 dark:bg-amber-900/20",
  },
};

/**
 * Compact assessment checks panel for the Overview tab.
 * Traffic light visual indicators for instant status scanning.
 */
export function ChecksSummaryPanel({ checks, onCheckClick, className }: ChecksSummaryPanelProps) {
  // Count by result type
  const counts: Record<CheckResult, number> = {
    PASS: checks.filter((c) => c.result === "PASS").length,
    FAIL: checks.filter((c) => c.result === "FAIL").length,
    INCONCLUSIVE: checks.filter((c) => c.result === "INCONCLUSIVE").length,
  };

  const total = checks.length;
  const passRate = total > 0 ? Math.round((counts.PASS / total) * 100) : 0;

  if (checks.length === 0) {
    return (
      <div className={cn("bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700", className)}>
        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Assessment Checks
            </h3>
          </div>
        </div>
        <div className="p-4 text-center">
          <p className="text-sm text-slate-500 dark:text-slate-400">No checks performed</p>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden", className)}>
      {/* Header with visual summary */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-slate-500" />
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Assessment Checks
            </h3>
          </div>
          {/* Traffic light summary */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
              <span className="text-xs font-medium text-slate-600 dark:text-slate-300">{counts.PASS}</span>
            </div>
            {counts.FAIL > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                <span className="text-xs font-medium text-slate-600 dark:text-slate-300">{counts.FAIL}</span>
              </div>
            )}
            {counts.INCONCLUSIVE > 0 && (
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500" />
                <span className="text-xs font-medium text-slate-600 dark:text-slate-300">{counts.INCONCLUSIVE}</span>
              </div>
            )}
          </div>
        </div>

        {/* Progress bar */}
        <div className="mt-2 h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden flex">
          {counts.PASS > 0 && (
            <div
              className="h-full bg-emerald-500 transition-all"
              style={{ width: `${(counts.PASS / total) * 100}%` }}
            />
          )}
          {counts.FAIL > 0 && (
            <div
              className="h-full bg-red-500 transition-all"
              style={{ width: `${(counts.FAIL / total) * 100}%` }}
            />
          )}
          {counts.INCONCLUSIVE > 0 && (
            <div
              className="h-full bg-amber-500 transition-all"
              style={{ width: `${(counts.INCONCLUSIVE / total) * 100}%` }}
            />
          )}
        </div>
      </div>

      {/* Compact check list */}
      <div className="divide-y divide-slate-100 dark:divide-slate-800 max-h-[280px] overflow-y-auto">
        {checks.map((check) => {
          const config = RESULT_CONFIG[check.result];
          const Icon = config.icon;

          return (
            <button
              key={check.check_number}
              onClick={() => onCheckClick?.(check.check_number)}
              className={cn(
                "w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors",
                "hover:bg-slate-50 dark:hover:bg-slate-800/50",
                check.result === "FAIL" && "bg-red-50/50 dark:bg-red-900/10"
              )}
            >
              {/* Status dot */}
              <span className={cn("w-2 h-2 rounded-full flex-shrink-0", config.dot)} />

              {/* Check info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-slate-400 font-mono">#{check.check_number}</span>
                  <span className={cn(
                    "text-sm truncate",
                    check.result === "PASS"
                      ? "text-slate-600 dark:text-slate-300"
                      : config.text
                  )}>
                    {check.check_name}
                  </span>
                </div>
              </div>

              {/* Result icon */}
              <Icon className={cn("h-4 w-4 flex-shrink-0", config.text)} />
            </button>
          );
        })}
      </div>

      {/* Footer with pass rate */}
      <div className="px-4 py-2 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/30">
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {counts.PASS} of {total} checks passed
          </span>
          <span className={cn(
            "text-xs font-semibold",
            passRate >= 80 ? "text-emerald-600 dark:text-emerald-400" :
            passRate >= 50 ? "text-amber-600 dark:text-amber-400" :
            "text-red-600 dark:text-red-400"
          )}>
            {passRate}%
          </span>
        </div>
      </div>
    </div>
  );
}
