import { Loader2, History, CheckCircle2, XCircle, ArrowRightCircle, Eye } from "lucide-react";
import { cn } from "../../lib/utils";
import { formatTimestamp } from "../../lib/formatters";
import type { AssessmentDecision } from "../../types";
import { StatusBadge, ScoreBadge } from "../shared";

/** Assessment run history entry */
export interface AssessmentHistoryEntry {
  run_id: string;
  timestamp: string;
  decision: AssessmentDecision;
  confidence_score: number;
  check_count: number;
  pass_count: number;
  fail_count: number;
  assumption_count: number;
  is_current: boolean;
}

interface ClaimHistoryTabProps {
  claimId: string;
  history: AssessmentHistoryEntry[];
  loading: boolean;
  error: string | null;
  onViewRun?: (runId: string) => void;
}

const DECISION_CONFIG: Record<AssessmentDecision, {
  icon: typeof CheckCircle2;
  label: string;
  variant: "success" | "error" | "warning";
}> = {
  APPROVE: { icon: CheckCircle2, label: "Approved", variant: "success" },
  REJECT: { icon: XCircle, label: "Rejected", variant: "error" },
  REFER_TO_HUMAN: { icon: ArrowRightCircle, label: "Referred", variant: "warning" },
};

/**
 * History tab showing past assessment runs for a claim.
 */
export function ClaimHistoryTab({ claimId, history, loading, error, onViewRun }: ClaimHistoryTabProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
          <p className="text-sm text-slate-500">Loading history...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-red-200 dark:border-red-900 p-6 text-center">
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="p-4">
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-4">
            <History className="h-6 w-6 text-slate-400" />
          </div>
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
            No Assessment History
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Assessment runs for this claim will appear here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 flex items-center gap-2">
          <History className="h-4 w-4 text-slate-500" />
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Assessment History
          </h3>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            ({history.length} runs)
          </span>
        </div>

        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {history.map((entry) => {
            const config = DECISION_CONFIG[entry.decision];
            const Icon = config.icon;

            return (
              <div
                key={entry.run_id}
                className={cn(
                  "px-4 py-3 flex items-center gap-4",
                  entry.is_current && "bg-blue-50/50 dark:bg-blue-900/10"
                )}
              >
                {/* Decision Icon */}
                <Icon className={cn(
                  "h-5 w-5 flex-shrink-0",
                  config.variant === "success" && "text-green-500",
                  config.variant === "error" && "text-red-500",
                  config.variant === "warning" && "text-amber-500"
                )} />

                {/* Main Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-600 dark:text-slate-300">
                      {entry.run_id}
                    </span>
                    {entry.is_current && (
                      <StatusBadge variant="info" size="sm">Current</StatusBadge>
                    )}
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    {formatTimestamp(entry.timestamp)}
                  </p>
                </div>

                {/* Decision */}
                <div className="flex-shrink-0">
                  <StatusBadge variant={config.variant} size="sm">
                    {config.label}
                  </StatusBadge>
                </div>

                {/* Confidence */}
                <div className="flex-shrink-0 text-center w-16">
                  <ScoreBadge value={entry.confidence_score} />
                  <p className="text-[10px] text-slate-400 mt-0.5">Confidence</p>
                </div>

                {/* Checks Summary */}
                <div className="flex-shrink-0 text-xs text-slate-500 dark:text-slate-400 w-24">
                  <span className="text-green-600">{entry.pass_count} pass</span>
                  {entry.fail_count > 0 && (
                    <span className="text-red-600"> / {entry.fail_count} fail</span>
                  )}
                </div>

                {/* Assumptions */}
                <div className="flex-shrink-0 text-xs w-20">
                  <span className={cn(
                    entry.assumption_count > 2
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-slate-500 dark:text-slate-400"
                  )}>
                    {entry.assumption_count} assumptions
                  </span>
                </div>

                {/* View Button */}
                {onViewRun && !entry.is_current && (
                  <button
                    onClick={() => onViewRun(entry.run_id)}
                    className="flex-shrink-0 p-1.5 rounded text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                    title="View this run"
                  >
                    <Eye className="h-4 w-4" />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
