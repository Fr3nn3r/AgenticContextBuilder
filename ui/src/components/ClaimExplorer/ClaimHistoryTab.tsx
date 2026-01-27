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
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading history...</p>
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

  if (history.length === 0) {
    return (
      <div className="p-4">
        <div className="bg-card rounded-lg border border-border p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
            <History className="h-6 w-6 text-muted-foreground" />
          </div>
          <h3 className="text-sm font-medium text-foreground mb-1">
            No Assessment History
          </h3>
          <p className="text-xs text-muted-foreground">
            Assessment runs for this claim will appear here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center gap-2">
          <History className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium text-foreground">
            Assessment History
          </h3>
          <span className="text-xs text-muted-foreground">
            ({history.length} runs)
          </span>
        </div>

        <div className="divide-y divide-border">
          {history.map((entry) => {
            const config = DECISION_CONFIG[entry.decision];
            const Icon = config.icon;

            return (
              <div
                key={entry.run_id}
                className={cn(
                  "px-4 py-3 flex items-center gap-4",
                  entry.is_current && "bg-info/10"
                )}
              >
                {/* Decision Icon */}
                <Icon className={cn(
                  "h-5 w-5 flex-shrink-0",
                  config.variant === "success" && "text-success",
                  config.variant === "error" && "text-destructive",
                  config.variant === "warning" && "text-warning"
                )} />

                {/* Main Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-foreground">
                      {entry.run_id}
                    </span>
                    {entry.is_current && (
                      <StatusBadge variant="info" size="sm">Current</StatusBadge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground mt-0.5">
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
                  <p className="text-[10px] text-muted-foreground mt-0.5">Confidence</p>
                </div>

                {/* Checks Summary */}
                <div className="flex-shrink-0 text-xs text-muted-foreground w-24">
                  <span className="text-success">{entry.pass_count} pass</span>
                  {entry.fail_count > 0 && (
                    <span className="text-destructive"> / {entry.fail_count} fail</span>
                  )}
                </div>

                {/* Assumptions */}
                <div className="flex-shrink-0 text-xs w-20">
                  <span className={cn(
                    entry.assumption_count > 2
                      ? "text-warning"
                      : "text-muted-foreground"
                  )}>
                    {entry.assumption_count} assumptions
                  </span>
                </div>

                {/* View Button */}
                {onViewRun && !entry.is_current && (
                  <button
                    onClick={() => onViewRun(entry.run_id)}
                    className="flex-shrink-0 p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted"
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
