import { useState, useCallback, useEffect } from "react";
import {
  Loader2,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRightCircle,
  ShieldAlert,
  Clock,
  Mail,
  ChevronDown,
  Copy,
  CheckCircle,
} from "lucide-react";
import { getAssessmentHistory, getHistoricalAssessment } from "../../api/client";
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
  onEvidenceClick?: (ref: string) => void;
}

const DECISION_CONFIG: Record<AssessmentDecision, {
  icon: typeof CheckCircle2;
  label: string;
  description: string;
  iconBg: string;
  textColor: string;
  borderColor: string;
  gradient: string;
  accentBar: string;
}> = {
  APPROVE: {
    icon: CheckCircle2,
    label: "Approved",
    description: "Claim has been approved for payment",
    iconBg: "bg-success/20",
    textColor: "text-success",
    borderColor: "border-success/30",
    gradient: "gradient-success",
    accentBar: "bg-success",
  },
  REJECT: {
    icon: XCircle,
    label: "Rejected",
    description: "Claim has been rejected",
    iconBg: "bg-destructive/20",
    textColor: "text-destructive",
    borderColor: "border-destructive/30",
    gradient: "gradient-destructive",
    accentBar: "bg-destructive",
  },
  REFER_TO_HUMAN: {
    icon: ArrowRightCircle,
    label: "Referred to Human",
    description: "Claim requires manual review",
    iconBg: "bg-warning/20",
    textColor: "text-warning",
    borderColor: "border-warning/30",
    gradient: "gradient-warning",
    accentBar: "bg-warning",
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
  onEvidenceClick,
}: ClaimAssessmentTabProps) {
  const { progress, startAssessment, isRunning, reset } = useAssessmentWebSocket();
  const [showDraftModal, setShowDraftModal] = useState(false);
  const [copied, setCopied] = useState(false);

  // Assessment history state
  type AssessmentHistoryEntry = {
    run_id: string;
    timestamp: string;
    decision: "APPROVE" | "REJECT" | "REFER_TO_HUMAN";
    confidence_score: number;
    is_current: boolean;
  };
  const [assessmentHistory, setAssessmentHistory] = useState<AssessmentHistoryEntry[]>([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState<string | null>(null);
  const [displayedAssessment, setDisplayedAssessment] = useState<ClaimAssessment | null>(assessment);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Reusable function to load assessment history
  const loadHistory = useCallback(async () => {
    if (!claimId) return;
    try {
      const history = await getAssessmentHistory(claimId);
      setAssessmentHistory(history);
    } catch (err) {
      console.warn("Failed to load assessment history:", err);
    }
  }, [claimId]);

  // Sync displayedAssessment with prop when assessment changes
  useEffect(() => {
    setDisplayedAssessment(assessment);
    // Reset to current when assessment prop changes
    if (assessment) {
      setSelectedAssessmentId(null);
    }
  }, [assessment]);

  // Fetch assessment history on mount AND when assessment prop changes
  useEffect(() => {
    loadHistory();
  }, [loadHistory, assessment]);

  // Handle selecting a historical assessment
  const handleSelectAssessment = useCallback(async (runId: string | null) => {
    if (runId === null) {
      // Selecting "current" - use prop assessment
      setSelectedAssessmentId(null);
      setDisplayedAssessment(assessment);
      return;
    }

    setSelectedAssessmentId(runId);
    setHistoryLoading(true);
    try {
      const historicalAssessment = await getHistoricalAssessment(claimId, runId);
      if (historicalAssessment) {
        setDisplayedAssessment(historicalAssessment);
      }
    } catch (err) {
      console.warn("Failed to load historical assessment:", err);
    } finally {
      setHistoryLoading(false);
    }
  }, [claimId, assessment]);

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
    // Also refresh history to show the new assessment
    loadHistory();
  }, [reset, onRefreshAssessment, loadHistory]);

  const handleDismissProgress = useCallback(() => {
    reset();
    if (progress.status === "completed") {
      if (onRefreshAssessment) {
        onRefreshAssessment();
      }
      // Also refresh history to show the new assessment
      loadHistory();
    }
  }, [reset, progress.status, onRefreshAssessment, loadHistory]);

  // Copy assessment ID to clipboard
  const handleCopyId = useCallback(async () => {
    const currentId = selectedAssessmentId || assessmentHistory.find(h => h.is_current)?.run_id;
    if (!currentId) return;
    try {
      await navigator.clipboard.writeText(currentId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  }, [selectedAssessmentId, assessmentHistory]);

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
  if (!displayedAssessment) {
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

  const decisionConfig = DECISION_CONFIG[displayedAssessment.decision];
  const DecisionIcon = decisionConfig.icon;

  // Count check results
  const passCount = displayedAssessment.checks.filter((c) => c.result === "PASS").length;
  const failedChecks = displayedAssessment.checks.filter((c) => c.result === "FAIL");
  const failCount = failedChecks.length;
  const inconclusiveCount = displayedAssessment.checks.filter((c) => c.result === "INCONCLUSIVE").length;

  // Count high-impact assumptions
  const criticalAssumptions = displayedAssessment.assumptions.filter((a) => a.impact === "high").length;

  // Generate decision description - include rejection reason for REJECT
  const getDecisionDescription = () => {
    if (displayedAssessment.decision === "REJECT" && failedChecks.length > 0) {
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

  // Shorten run ID for display (matching ClaimRunSelector)
  const shortenRunId = (runId: string) => {
    if (runId.length <= 24) return runId;
    return `${runId.slice(0, 16)}...${runId.slice(-6)}`;
  };

  // Get current assessment entry for timestamp display
  const currentEntry = assessmentHistory.find(h =>
    selectedAssessmentId ? h.run_id === selectedAssessmentId : h.is_current
  );

  return (
    <div className="p-4 space-y-4">
      {/* Header Bar - Assessment selector and actions on one line */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Assessment:</span>
          {assessmentHistory.length > 0 ? (
            <>
              <div className="relative">
                <select
                  value={selectedAssessmentId ?? ""}
                  onChange={(e) => handleSelectAssessment(e.target.value || null)}
                  disabled={historyLoading}
                  className={cn(
                    "appearance-none bg-card border border-border",
                    "rounded-md pl-3 pr-8 py-1.5 text-sm font-mono",
                    "text-foreground",
                    "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
                    "disabled:opacity-50 disabled:cursor-not-allowed",
                    "cursor-pointer"
                  )}
                >
                  {assessmentHistory.map((entry, index) => (
                    <option key={entry.run_id} value={entry.is_current ? "" : entry.run_id}>
                      {shortenRunId(entry.run_id)}{index === 0 ? " (latest)" : ""}
                    </option>
                  ))}
                </select>
                <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
              </div>
              <button
                onClick={handleCopyId}
                disabled={!currentEntry}
                className={cn(
                  "p-1.5 rounded-md transition-colors",
                  "hover:bg-muted text-muted-foreground hover:text-foreground",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
                title={copied ? "Copied!" : "Copy assessment ID"}
              >
                {copied ? (
                  <CheckCircle className="h-4 w-4 text-success" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </button>
              {historyLoading && (
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
              )}
              {currentEntry && (
                <span className="flex items-center gap-1 text-xs text-muted-foreground">
                  <Clock className="h-3 w-3" />
                  {formatTimestamp(currentEntry.timestamp)}
                </span>
              )}
            </>
          ) : (
            <span className="text-sm text-muted-foreground">No assessments</span>
          )}
        </div>
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

      {/* Decision Banner */}
      <div className={cn(
        "rounded-lg border overflow-hidden shadow-sm relative",
        decisionConfig.borderColor
      )}>
        {/* Left accent bar */}
        <div className={cn(
          "absolute left-0 top-0 bottom-0 w-1",
          decisionConfig.accentBar
        )} />

        {/* Main content with gradient */}
        <div className={cn("p-6 pl-5", decisionConfig.gradient)}>
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4">
              <div className={cn(
                "w-12 h-12 rounded-full flex items-center justify-center",
                decisionConfig.iconBg
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
                {displayedAssessment.assessed_at && (
                  <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    Assessed {formatTimestamp(displayedAssessment.assessed_at)}
                  </p>
                )}
                {displayedAssessment.decision_rationale && (
                  <p className={cn(
                    "text-sm mt-2 italic",
                    displayedAssessment.decision === "REJECT"
                      ? "text-destructive font-medium"
                      : "text-muted-foreground"
                  )}>
                    "{displayedAssessment.decision_rationale}"
                  </p>
                )}
              </div>
            </div>

            {/* Confidence Score */}
            <div className="text-right">
              <div className="text-2xl font-bold text-foreground">
                <ScoreBadge value={displayedAssessment.confidence_score} />
              </div>
              <p className="text-xs text-muted-foreground">Confidence</p>
            </div>
          </div>
        </div>

        {/* Quick Stats section - neutral background */}
        <div className="px-6 py-4 border-t border-border bg-muted/30 grid grid-cols-2 md:grid-cols-5 gap-4">
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
              {displayedAssessment.assumptions.length}
            </div>
            <div className="text-xs text-muted-foreground">Assumptions</div>
          </div>
          {displayedAssessment.payout !== undefined && (
            <div className="text-center">
              <div className="text-lg font-semibold text-foreground">
                {displayedAssessment.currency || displayedAssessment.payout_breakdown?.currency || "CHF"}{" "}
                {displayedAssessment.payout.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">Payout</div>
            </div>
          )}
        </div>
      </div>

      {/* Payout Breakdown */}
      {displayedAssessment.payout_breakdown && displayedAssessment.decision !== "REJECT" && (
        <PayoutBreakdownCard breakdown={displayedAssessment.payout_breakdown} />
      )}

      {/* Fraud Indicators (if any) */}
      {displayedAssessment.fraud_indicators.length > 0 && (
        <div className="bg-destructive/10 rounded-lg border border-destructive/30 p-4">
          <div className="flex items-center gap-2 mb-3">
            <ShieldAlert className="h-5 w-5 text-destructive" />
            <h3 className="font-semibold text-destructive">
              Fraud Indicators ({displayedAssessment.fraud_indicators.length})
            </h3>
          </div>
          <div className="space-y-2">
            {displayedAssessment.fraud_indicators.map((indicator, idx) => (
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
      {displayedAssessment.recommendations.length > 0 && displayedAssessment.decision !== "APPROVE" && (
        <div className="bg-info/10 rounded-lg border border-info/30 p-4">
          <h3 className="font-semibold text-info mb-2">Recommendations</h3>
          <ul className="list-disc list-inside space-y-1">
            {displayedAssessment.recommendations.map((rec, idx) => (
              <li key={idx} className="text-sm text-info">{rec}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Checks Panel */}
      {displayedAssessment.checks.length > 0 && (
        <ChecksReviewPanel
          checks={displayedAssessment.checks}
          onEvidenceClick={onEvidenceClick}
        />
      )}

      {/* Assumptions Panel */}
      {displayedAssessment.assumptions.length > 0 && (
        <AssumptionsPane assumptions={displayedAssessment.assumptions} />
      )}

      {/* Assessment Feedback */}
      <WorkflowActionsPanel
        readiness={{ readinessPct: 0, blockingIssues: [], criticalAssumptions: 0, canAutoApprove: false, canAutoReject: false }}
        currentDecision={displayedAssessment.decision}
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
