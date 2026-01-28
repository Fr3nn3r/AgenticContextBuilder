import { useState, useCallback } from "react";
import {
  Loader2,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRightCircle,
  ShieldAlert,
  Clock,
  History,
  Mail,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { ClaimAssessment, AssessmentDecision } from "../../types";
import { formatTimestamp } from "../../lib/formatters";
import { StatusBadge, ScoreBadge } from "../shared";
import { AssumptionsPane } from "./AssumptionsPane";
import { ChecksReviewPanel } from "./ChecksReviewPanel";
import { WorkflowActionsPanel } from "./WorkflowActionsPanel";
import { PayoutBreakdownCard } from "./PayoutBreakdownCard";
import { AssessmentProgressCard } from "./AssessmentProgressCard";
import { CustomerDraftModal } from "./CustomerDraftModal";
import { useAssessmentWebSocket } from "../../hooks/useAssessmentWebSocket";

interface ClaimAssessmentTabProps {
  claimId: string;
  assessment: ClaimAssessment | null;
  loading: boolean;
  error: string | null;
  onRunAssessment?: () => Promise<void>;
  onRefreshAssessment?: () => Promise<void>;
  onRefreshHistory?: () => Promise<void>;
  onEvidenceClick?: (ref: string) => void;
  onViewHistory?: () => void;
}

const DECISION_CONFIG: Record<AssessmentDecision, {
  icon: typeof CheckCircle2;
  label: string;
  description: string;
  bgColor: string;
  textColor: string;
  borderColor: string;
}> = {
  APPROVE: {
    icon: CheckCircle2,
    label: "Approved",
    description: "Claim has been approved for payment",
    bgColor: "bg-success/10",
    textColor: "text-success",
    borderColor: "border-success/30",
  },
  REJECT: {
    icon: XCircle,
    label: "Rejected",
    description: "Claim has been rejected",
    bgColor: "bg-destructive/10",
    textColor: "text-destructive",
    borderColor: "border-destructive/30",
  },
  REFER_TO_HUMAN: {
    icon: ArrowRightCircle,
    label: "Referred to Human",
    description: "Claim requires manual review",
    bgColor: "bg-warning/10",
    textColor: "text-warning",
    borderColor: "border-warning/30",
  },
};

/**
 * Assessment tab showing decision, checks, assumptions, and run controls.
 */
export function ClaimAssessmentTab({
  claimId,
  assessment,
  loading,
  error,
  onRunAssessment,
  onRefreshAssessment,
  onRefreshHistory,
  onEvidenceClick,
  onViewHistory,
}: ClaimAssessmentTabProps) {
  const { progress, startAssessment, isRunning, reset } = useAssessmentWebSocket();
  const [showDraftModal, setShowDraftModal] = useState(false);

  const handleRunAssessment = useCallback(async () => {
    const runId = await startAssessment(claimId);
    if (runId) {
      // Assessment started - WebSocket will track progress
    }
  }, [claimId, startAssessment]);

  const handleViewResult = useCallback(() => {
    reset();
    if (onRefreshAssessment) {
      onRefreshAssessment();
    }
    if (onRefreshHistory) {
      onRefreshHistory();
    }
  }, [reset, onRefreshAssessment, onRefreshHistory]);

  const handleDismissProgress = useCallback(() => {
    reset();
    if (progress.status === "completed") {
      if (onRefreshAssessment) {
        onRefreshAssessment();
      }
      if (onRefreshHistory) {
        onRefreshHistory();
      }
    }
  }, [reset, progress.status, onRefreshAssessment, onRefreshHistory]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading assessment...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <div className="bg-card rounded-lg border border-destructive/30 p-6 text-center">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      </div>
    );
  }

  // No assessment yet
  if (!assessment) {
    return (
      <div className="p-4">
        <div className="bg-card rounded-lg border border-border p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
            <Play className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-medium text-foreground mb-2">
            No Assessment Yet
          </h3>
          <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
            Run an automated assessment to evaluate this claim against policy rules
            and generate a decision recommendation.
          </p>
          <button
            onClick={handleRunAssessment}
            disabled={isRunning || !onRunAssessment}
            className={cn(
              "inline-flex items-center gap-2 px-6 py-3 rounded-lg font-medium",
              "bg-primary text-primary-foreground hover:bg-primary/90",
              "disabled:opacity-50 disabled:cursor-not-allowed",
              "transition-colors"
            )}
          >
            {isRunning ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Running Assessment...
              </>
            ) : (
              <>
                <Play className="h-5 w-5" />
                Run Assessment
              </>
            )}
          </button>
        </div>
      </div>
    );
  }

  const decisionConfig = DECISION_CONFIG[assessment.decision];
  const DecisionIcon = decisionConfig.icon;

  // Count check results
  const passCount = assessment.checks.filter((c) => c.result === "PASS").length;
  const failedChecks = assessment.checks.filter((c) => c.result === "FAIL");
  const failCount = failedChecks.length;
  const inconclusiveCount = assessment.checks.filter((c) => c.result === "INCONCLUSIVE").length;

  // Count high-impact assumptions
  const criticalAssumptions = assessment.assumptions.filter((a) => a.impact === "high").length;

  // Generate decision description - include rejection reason for REJECT
  const getDecisionDescription = () => {
    if (assessment.decision === "REJECT" && failedChecks.length > 0) {
      const reasons = failedChecks.map((c) => c.details).filter(Boolean);
      if (reasons.length === 1) {
        return `Claim rejected: ${reasons[0]}`;
      } else if (reasons.length > 1) {
        return `Claim rejected: ${reasons[0]}`;
      }
      return "Claim has been rejected due to failed checks";
    }
    return decisionConfig.description;
  };

  return (
    <div className="p-4 space-y-4">
      {/* Action Bar */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-foreground">
          Assessment
        </h2>
        <div className="flex items-center gap-2">
          {onViewHistory && (
            <button
              onClick={onViewHistory}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-sm text-muted-foreground hover:text-foreground hover:bg-muted rounded-lg transition-colors"
            >
              <History className="h-4 w-4" />
              History
            </button>
          )}
          <button
            onClick={() => setShowDraftModal(true)}
            className={cn(
              "inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
              "bg-primary text-primary-foreground hover:bg-primary/90"
            )}
          >
            <Mail className="h-4 w-4" />
            View Customer Draft
          </button>
        </div>
      </div>

      {/* Decision Banner */}
      <div className={cn(
        "rounded-lg border p-6",
        decisionConfig.bgColor,
        decisionConfig.borderColor
      )}>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center",
              decisionConfig.bgColor
            )}>
              <DecisionIcon className={cn("h-7 w-7", decisionConfig.textColor)} />
            </div>
            <div>
              <h2 className={cn("text-xl font-bold", decisionConfig.textColor)}>
                {decisionConfig.label}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                {getDecisionDescription()}
              </p>
              {assessment.assessed_at && (
                <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  Assessed {formatTimestamp(assessment.assessed_at)}
                </p>
              )}
              {assessment.decision_rationale && (
                <p className={cn(
                  "text-sm mt-2 italic",
                  assessment.decision === "REJECT"
                    ? "text-destructive font-medium"
                    : "text-muted-foreground"
                )}>
                  "{assessment.decision_rationale}"
                </p>
              )}
            </div>
          </div>

          {/* Confidence Score */}
          <div className="text-right">
            <div className="text-2xl font-bold text-foreground">
              <ScoreBadge value={assessment.confidence_score} />
            </div>
            <p className="text-xs text-muted-foreground">Confidence</p>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="mt-4 pt-4 border-t border-border grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="text-center">
            <div className="text-lg font-semibold text-success">{passCount}</div>
            <div className="text-xs text-muted-foreground">Checks Passed</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-destructive">{failCount}</div>
            <div className="text-xs text-muted-foreground">Checks Failed</div>
          </div>
          <div className="text-center">
            <div className="text-lg font-semibold text-warning">{inconclusiveCount}</div>
            <div className="text-xs text-muted-foreground">Inconclusive</div>
          </div>
          <div className="text-center">
            <div className={cn(
              "text-lg font-semibold",
              criticalAssumptions > 0 ? "text-warning" : "text-muted-foreground"
            )}>
              {assessment.assumptions.length}
            </div>
            <div className="text-xs text-muted-foreground">Assumptions</div>
          </div>
          {assessment.payout !== undefined && (
            <div className="text-center">
              <div className="text-lg font-semibold text-foreground">
                {assessment.currency || assessment.payout_breakdown?.currency || "CHF"}{" "}
                {assessment.payout.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">Payout</div>
            </div>
          )}
        </div>
      </div>

      {/* Payout Breakdown */}
      {assessment.payout_breakdown && (
        <PayoutBreakdownCard breakdown={assessment.payout_breakdown} />
      )}

      {/* Fraud Indicators (if any) */}
      {assessment.fraud_indicators.length > 0 && (
        <div className="bg-destructive/10 rounded-lg border border-destructive/30 p-4">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert className="h-5 w-5 text-destructive" />
            <h3 className="font-semibold text-destructive">
              Fraud Indicators ({assessment.fraud_indicators.length})
            </h3>
          </div>
          <div className="space-y-2">
            {assessment.fraud_indicators.map((indicator, idx) => (
              <div key={idx} className="flex items-start gap-2 text-sm">
                <StatusBadge
                  variant={indicator.severity === "high" ? "error" : indicator.severity === "medium" ? "warning" : "neutral"}
                  size="sm"
                >
                  {indicator.severity}
                </StatusBadge>
                <div>
                  <span className="font-medium text-destructive">{indicator.indicator}</span>
                  {indicator.details && (
                    <p className="text-xs text-destructive/80 mt-0.5">{indicator.details}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations (if any) */}
      {assessment.recommendations.length > 0 && (
        <div className="bg-info/10 rounded-lg border border-info/30 p-4">
          <h3 className="font-semibold text-info mb-2">Recommendations</h3>
          <ul className="list-disc list-inside space-y-1">
            {assessment.recommendations.map((rec, idx) => (
              <li key={idx} className="text-sm text-info">{rec}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Checks Panel */}
      {assessment.checks.length > 0 && (
        <ChecksReviewPanel
          checks={assessment.checks}
          onEvidenceClick={onEvidenceClick}
        />
      )}

      {/* Assumptions Panel */}
      {assessment.assumptions.length > 0 && (
        <AssumptionsPane assumptions={assessment.assumptions} />
      )}

      {/* Assessment Feedback */}
      <WorkflowActionsPanel
        readiness={{ readinessPct: 0, blockingIssues: [], criticalAssumptions: 0, canAutoApprove: false, canAutoReject: false }}
        currentDecision={assessment.decision}
      />

      {/* Progress Card (floating) */}
      <AssessmentProgressCard
        progress={progress}
        onDismiss={handleDismissProgress}
        onViewResult={handleViewResult}
      />

      {/* Customer Draft Modal */}
      <CustomerDraftModal
        isOpen={showDraftModal}
        onClose={() => setShowDraftModal(false)}
        claimId={claimId}
      />
    </div>
  );
}
