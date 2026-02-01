import { useState, useCallback, useEffect } from "react";
import {
  Loader2,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRightCircle,
  Clock,
  Mail,
  ChevronDown,
  Copy,
  CheckCircle,
  Wrench,
} from "lucide-react";
import { getAssessmentHistory, getHistoricalAssessment } from "../../api/client";
import { cn } from "../../lib/utils";
import type {
  ClaimAssessment,
  AssessmentDecision,
  CoverageAnalysisResult,
} from "../../types";
import { formatTimestamp } from "../../lib/formatters";
import { ScoreBadge } from "../shared";
import { ChecksReviewPanel } from "./ChecksReviewPanel";
import { WorkflowActionsPanel } from "./WorkflowActionsPanel";
import { PayoutBreakdownCard } from "./PayoutBreakdownCard";
import { AssessmentProgressCard } from "./AssessmentProgressCard";
import { CustomerDraftModal } from "./CustomerDraftModal";
import { useAssessmentWebSocket } from "../../hooks/useAssessmentWebSocket";

interface ClaimAssessmentTabProps {
  claimId: string;
  assessment: ClaimAssessment | null;
  coverageAnalysis: CoverageAnalysisResult | null;
  coverageLoading: boolean;
  loading: boolean;
  error: string | null;
  onRunAssessment?: () => Promise<void>;
  onRefreshAssessment?: () => Promise<void>;
  onEvidenceClick?: (ref: string) => void;
  resolvableRefs?: Set<string>;
}

// === Helpers ===

function formatCHF(value: number): string {
  return new Intl.NumberFormat("de-CH", {
    style: "currency",
    currency: "CHF",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function componentLabel(component: string): string {
  return component.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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
 * Assessment tab: decision, checks, coverage line items, and feedback.
 */
export function ClaimAssessmentTab({
  claimId,
  assessment,
  coverageAnalysis,
  coverageLoading,
  loading,
  error,
  onRunAssessment,
  onRefreshAssessment,
  onEvidenceClick,
  resolvableRefs,
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

  const loadHistory = useCallback(async () => {
    if (!claimId) return;
    try {
      const history = await getAssessmentHistory(claimId);
      setAssessmentHistory(history);
    } catch (err) {
      console.warn("Failed to load assessment history:", err);
    }
  }, [claimId]);

  useEffect(() => {
    setDisplayedAssessment(assessment);
    if (assessment) {
      setSelectedAssessmentId(null);
    }
  }, [assessment]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory, assessment]);

  const handleSelectAssessment = useCallback(async (runId: string | null) => {
    if (runId === null) {
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
      // WebSocket will track progress
    }
  }, [claimId, startAssessment]);

  const handleViewResult = useCallback(() => {
    reset();
    if (onRefreshAssessment) {
      onRefreshAssessment();
    }
    loadHistory();
  }, [reset, onRefreshAssessment, loadHistory]);

  const handleDismissProgress = useCallback(() => {
    reset();
    if (progress.status === "completed") {
      if (onRefreshAssessment) {
        onRefreshAssessment();
      }
      loadHistory();
    }
  }, [reset, progress.status, onRefreshAssessment, loadHistory]);

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

  const failedChecks = displayedAssessment.checks.filter((c) => c.result === "FAIL");

  const getDecisionDescription = () => {
    if (displayedAssessment.decision === "REJECT" && failedChecks.length > 0) {
      const reasons = failedChecks.map((c) => c.details).filter(Boolean);
      if (reasons.length >= 1) {
        return `Claim rejected: ${reasons[0]}`;
      }
      return "Claim has been rejected due to failed checks";
    }
    return decisionConfig.description;
  };

  const shortenRunId = (runId: string) => {
    if (runId.length <= 24) return runId;
    return `${runId.slice(0, 16)}...${runId.slice(-6)}`;
  };

  const currentEntry = assessmentHistory.find(h =>
    selectedAssessmentId ? h.run_id === selectedAssessmentId : h.is_current
  );

  // Coverage data
  const primaryRepair = coverageAnalysis?.primary_repair;
  const coveredLabor = coverageAnalysis?.line_items?.filter(
    (li) => li.item_type === "labor" && li.coverage_status === "covered"
  ) ?? [];

  return (
    <div className="p-4 space-y-4">
      {/* Header Bar - Assessment selector and actions */}
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
          disabled
          className={cn(
            "inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg transition-colors",
            "bg-muted text-muted-foreground cursor-not-allowed opacity-50"
          )}
          title="Coming soon"
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
        <div className={cn(
          "absolute left-0 top-0 bottom-0 w-1",
          decisionConfig.accentBar
        )} />

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
              </div>
            </div>

            <div className="text-right">
              <div className="text-2xl font-bold text-foreground">
                <ScoreBadge value={displayedAssessment.confidence_score} />
              </div>
              <p className="text-xs text-muted-foreground">Confidence</p>
            </div>
          </div>
        </div>

        {/* Lower section: Primary Repair + Covered Labor + Payout */}
        <div className="px-6 py-4 border-t border-border bg-muted/30">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {/* Primary Repair */}
            {primaryRepair && primaryRepair.component ? (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Wrench className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">Primary Repair</span>
                </div>
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-sm font-semibold text-foreground">
                    {componentLabel(primaryRepair.component)}
                  </span>
                  <span className={cn(
                    "text-[10px] px-1.5 py-0.5 rounded-full font-medium",
                    primaryRepair.is_covered ? "bg-success/15 text-success" : "bg-destructive/15 text-destructive"
                  )}>
                    {primaryRepair.is_covered ? "Covered" : "Not Covered"}
                  </span>
                </div>
                {primaryRepair.category && (
                  <span className="text-xs text-muted-foreground">{componentLabel(primaryRepair.category)}</span>
                )}
              </div>
            ) : (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <Wrench className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs text-muted-foreground">Primary Repair</span>
                </div>
                <span className="text-sm text-muted-foreground">
                  {coverageLoading ? "Loading..." : "N/A"}
                </span>
              </div>
            )}

            {/* Covered Labor */}
            {coveredLabor.length > 0 ? (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Covered Labor</div>
                <div className="text-sm font-semibold text-foreground">
                  {formatCHF(coveredLabor.reduce((sum, li) => sum + li.covered_amount, 0))}
                </div>
                <span className="text-xs text-muted-foreground">{coveredLabor.length} item{coveredLabor.length !== 1 ? "s" : ""}</span>
              </div>
            ) : (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Covered Labor</div>
                <span className="text-sm text-muted-foreground">None</span>
              </div>
            )}

            {/* Payout */}
            {displayedAssessment.payout !== undefined && (
              <div>
                <div className="text-xs text-muted-foreground mb-1">Payout</div>
                <div className="text-sm font-semibold text-foreground">
                  {displayedAssessment.currency || displayedAssessment.payout_breakdown?.currency || "CHF"}{" "}
                  {displayedAssessment.payout.toLocaleString()}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Payout Breakdown */}
      {displayedAssessment.payout_breakdown && displayedAssessment.decision !== "REJECT" && (
        <PayoutBreakdownCard breakdown={displayedAssessment.payout_breakdown} />
      )}

      {/* Checks Panel */}
      {displayedAssessment.checks.length > 0 && (
        <ChecksReviewPanel
          checks={displayedAssessment.checks}
          onEvidenceClick={onEvidenceClick}
          resolvableRefs={resolvableRefs}
        />
      )}

      {/* Assessment Feedback (at the very bottom) */}
      <WorkflowActionsPanel
        claimId={claimId}
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
