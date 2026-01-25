import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  AlertOctagon,
  FileWarning,
} from "lucide-react";
import { cn } from "../../lib/utils";

export interface BlockingIssue {
  type: "missing_evidence" | "failed_check" | "inconclusive_check" | "conflict" | "quality_gate";
  description: string;
  field?: string;
  docId?: string;
  checkNumber?: number;
}

export interface DecisionReadiness {
  readinessPct: number;
  blockingIssues: BlockingIssue[];
  criticalAssumptions: number;
  canAutoApprove: boolean;
  canAutoReject: boolean;
}

interface MetricsSummary {
  totalChecks: number;
  passedChecks: number;
  failedChecks: number;
  inconclusiveChecks: number;
  assumptions: number;
  criticalAssumptions: number;
}

interface DecisionReadinessCardProps {
  readiness: DecisionReadiness;
  metrics: MetricsSummary;
  hasAssessment: boolean;
}

const ISSUE_TYPE_CONFIG: Record<
  BlockingIssue["type"],
  { icon: typeof AlertTriangle; color: string; label: string }
> = {
  missing_evidence: {
    icon: FileWarning,
    color: "text-amber-500",
    label: "Missing",
  },
  failed_check: {
    icon: XCircle,
    color: "text-red-500",
    label: "Failed",
  },
  inconclusive_check: {
    icon: HelpCircle,
    color: "text-amber-500",
    label: "Inconclusive",
  },
  conflict: {
    icon: AlertOctagon,
    color: "text-orange-500",
    label: "Conflict",
  },
  quality_gate: {
    icon: AlertTriangle,
    color: "text-red-500",
    label: "Quality",
  },
};

/**
 * Shows decision readiness percentage and blocking issues.
 * All data comes from real backend sources.
 */
export function DecisionReadinessCard({
  readiness,
  metrics,
  hasAssessment,
}: DecisionReadinessCardProps) {
  const { readinessPct, blockingIssues, criticalAssumptions } = readiness;

  // Determine status color based on readiness
  const getProgressColor = () => {
    if (readinessPct >= 90) return "bg-green-500";
    if (readinessPct >= 70) return "bg-amber-500";
    return "bg-red-500";
  };

  // Determine status text
  const getStatusText = () => {
    if (!hasAssessment) return "No assessment run yet";
    if (readiness.canAutoApprove) return "Ready for approval";
    if (readiness.canAutoReject) return "Eligible for rejection";
    if (readinessPct >= 70) return "Needs attention";
    return "Requires human review";
  };

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Decision Readiness
        </h3>
      </div>

      <div className="p-4 space-y-4">
        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-2xl font-bold text-slate-700 dark:text-slate-200">
              {readinessPct}%
            </span>
            <span
              className={cn(
                "text-sm font-medium px-2 py-1 rounded-full",
                readiness.canAutoApprove
                  ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300"
                  : readiness.canAutoReject
                  ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300"
                  : "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300"
              )}
            >
              {getStatusText()}
            </span>
          </div>
          <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
            <div
              className={cn("h-full transition-all duration-500", getProgressColor())}
              style={{ width: `${readinessPct}%` }}
            />
          </div>
        </div>

        {/* Key Metrics Row */}
        <div className="grid grid-cols-5 gap-2 pt-2">
          <MetricBox
            label="Checks"
            value={metrics.totalChecks}
            subValue={null}
            color="text-slate-600 dark:text-slate-300"
          />
          <MetricBox
            label="Passed"
            value={metrics.passedChecks}
            subValue={null}
            color="text-green-600 dark:text-green-400"
            icon={<CheckCircle2 className="h-3.5 w-3.5" />}
          />
          <MetricBox
            label="Failed"
            value={metrics.failedChecks}
            subValue={null}
            color="text-red-600 dark:text-red-400"
            icon={<XCircle className="h-3.5 w-3.5" />}
          />
          <MetricBox
            label="Unknown"
            value={metrics.inconclusiveChecks}
            subValue={null}
            color="text-amber-600 dark:text-amber-400"
            icon={<HelpCircle className="h-3.5 w-3.5" />}
          />
          <MetricBox
            label="Assumed"
            value={metrics.assumptions}
            subValue={
              criticalAssumptions > 0 ? `${criticalAssumptions} critical` : null
            }
            color={
              criticalAssumptions > 0
                ? "text-amber-600 dark:text-amber-400"
                : "text-slate-600 dark:text-slate-400"
            }
            icon={<AlertTriangle className="h-3.5 w-3.5" />}
          />
        </div>

        {/* Blocking Issues */}
        {blockingIssues.length > 0 && (
          <div className="pt-2 border-t border-slate-200 dark:border-slate-700">
            <h4 className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-2">
              Blocking Issues ({blockingIssues.length})
            </h4>
            <div className="space-y-1.5 max-h-32 overflow-y-auto">
              {blockingIssues.slice(0, 5).map((issue, idx) => {
                const config = ISSUE_TYPE_CONFIG[issue.type];
                const Icon = config.icon;
                return (
                  <div
                    key={`${issue.type}-${idx}`}
                    className="flex items-start gap-2 text-sm"
                  >
                    <Icon className={cn("h-4 w-4 flex-shrink-0 mt-0.5", config.color)} />
                    <span className="text-slate-600 dark:text-slate-300 line-clamp-1">
                      {issue.description}
                    </span>
                  </div>
                );
              })}
              {blockingIssues.length > 5 && (
                <p className="text-xs text-slate-500 dark:text-slate-400 pl-6">
                  +{blockingIssues.length - 5} more issues
                </p>
              )}
            </div>
          </div>
        )}

        {/* Critical Assumptions Warning */}
        {criticalAssumptions > 0 && (
          <div className="bg-amber-50 dark:bg-amber-900/20 rounded-lg p-3 border border-amber-200 dark:border-amber-800">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-amber-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-amber-700 dark:text-amber-300">
                  {criticalAssumptions} high-impact assumption
                  {criticalAssumptions > 1 ? "s" : ""}
                </p>
                <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                  This claim cannot be auto-approved. Verify assumptions or refer to
                  human reviewer.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* No Assessment State */}
        {!hasAssessment && (
          <div className="bg-slate-50 dark:bg-slate-800/50 rounded-lg p-3 border border-slate-200 dark:border-slate-700">
            <div className="flex items-start gap-2">
              <HelpCircle className="h-4 w-4 text-slate-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
                  No assessment available
                </p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Run an assessment to evaluate this claim against policy rules.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

interface MetricBoxProps {
  label: string;
  value: number;
  subValue: string | null;
  color: string;
  icon?: React.ReactNode;
}

function MetricBox({ label, value, subValue, color, icon }: MetricBoxProps) {
  return (
    <div className="text-center">
      <div className={cn("text-lg font-semibold flex items-center justify-center gap-1", color)}>
        {icon}
        {value}
      </div>
      <div className="text-[10px] text-slate-500 dark:text-slate-400 uppercase">
        {label}
      </div>
      {subValue && (
        <div className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
          {subValue}
        </div>
      )}
    </div>
  );
}
