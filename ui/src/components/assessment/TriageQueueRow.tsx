import { ExternalLink, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { cn } from "../../lib/utils";
import type { TriageQueueItem, TriagePriority, TriageReason, AssessmentDecision } from "../../types";
import { StatusBadge, ScoreBadge } from "../shared";

interface TriageQueueRowProps {
  item: TriageQueueItem;
  onReview: () => void;
  onQuickApprove?: () => void;
  onQuickReject?: () => void;
}

const PRIORITY_CONFIG: Record<TriagePriority, { label: string; color: string; variant: "error" | "warning" | "info" | "neutral" }> = {
  critical: { label: "Critical", color: "bg-red-500", variant: "error" },
  high: { label: "High", color: "bg-orange-500", variant: "warning" },
  medium: { label: "Medium", color: "bg-amber-500", variant: "info" },
  low: { label: "Low", color: "bg-slate-400", variant: "neutral" },
};

const REASON_LABELS: Record<TriageReason, string> = {
  low_confidence: "Low Confidence",
  high_impact_assumption: "High Impact Assumption",
  fraud_indicator: "Fraud Indicator",
  inconclusive_check: "Inconclusive Check",
  conflicting_evidence: "Conflicting Evidence",
};

const DECISION_LABELS: Record<AssessmentDecision, string> = {
  APPROVE: "Approve",
  REJECT: "Reject",
  REFER_TO_HUMAN: "Refer",
};

/**
 * Single row in the triage queue table.
 */
export function TriageQueueRow({ item, onReview, onQuickApprove, onQuickReject }: TriageQueueRowProps) {
  const priorityConfig = PRIORITY_CONFIG[item.priority];

  return (
    <tr className="border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50">
      {/* Priority */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <span className={cn("w-2.5 h-2.5 rounded-full", priorityConfig.color)} />
          <StatusBadge variant={priorityConfig.variant} size="sm">
            {priorityConfig.label}
          </StatusBadge>
        </div>
      </td>

      {/* Claim ID */}
      <td className="px-4 py-3">
        <span className="font-mono text-xs text-slate-700 dark:text-slate-200">
          {item.claim_id}
        </span>
      </td>

      {/* Decision */}
      <td className="px-4 py-3">
        <StatusBadge
          variant={
            item.decision === "APPROVE" ? "success" :
            item.decision === "REJECT" ? "error" : "warning"
          }
          size="sm"
        >
          {DECISION_LABELS[item.decision]}
        </StatusBadge>
      </td>

      {/* Confidence */}
      <td className="px-4 py-3 text-center">
        <ScoreBadge value={item.confidence_score} />
      </td>

      {/* Reasons */}
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-1">
          {item.reasons.slice(0, 2).map((reason) => (
            <span
              key={reason}
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300"
            >
              {REASON_LABELS[reason]}
            </span>
          ))}
          {item.reasons.length > 2 && (
            <span className="text-[10px] text-slate-400">
              +{item.reasons.length - 2} more
            </span>
          )}
        </div>
      </td>

      {/* Assumptions / Fraud indicators */}
      <td className="px-4 py-3 text-center">
        <div className="flex items-center justify-center gap-2">
          {item.assumption_count > 0 && (
            <span className={cn(
              "text-xs",
              item.assumption_count > 2 && "text-amber-600 dark:text-amber-400 font-medium"
            )}>
              {item.assumption_count} assumptions
            </span>
          )}
          {item.fraud_indicator_count > 0 && (
            <span className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400 font-medium">
              <AlertTriangle className="h-3 w-3" />
              {item.fraud_indicator_count} fraud
            </span>
          )}
        </div>
      </td>

      {/* Actions */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            onClick={onReview}
            className="flex items-center gap-1 px-2.5 py-1.5 rounded text-xs font-medium bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 hover:bg-blue-100 dark:hover:bg-blue-900/30"
          >
            <ExternalLink className="h-3 w-3" />
            Review
          </button>
          {onQuickApprove && (
            <button
              onClick={onQuickApprove}
              className="p-1.5 rounded text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20"
              title="Quick Approve"
            >
              <CheckCircle2 className="h-4 w-4" />
            </button>
          )}
          {onQuickReject && (
            <button
              onClick={onQuickReject}
              className="p-1.5 rounded text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
              title="Quick Reject"
            >
              <XCircle className="h-4 w-4" />
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
