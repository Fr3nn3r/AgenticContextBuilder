import { ArrowUp, ArrowDown, Loader2, CheckCircle2, XCircle, X } from "lucide-react";
import { cn } from "../../lib/utils";
import type { AssessmentProgress } from "../../hooks/useAssessmentWebSocket";

interface AssessmentProgressCardProps {
  progress: AssessmentProgress;
  onDismiss?: () => void;
  onViewResult?: () => void;
}

const STAGE_LABELS: Record<string, string> = {
  reconciliation: "Reconciling Facts",
  processing: "Processing Assessment",
  "processing:assessment": "Running Assessment",
};

/**
 * Floating progress card shown in bottom-right corner during assessment runs.
 * Shows stage progress and token counts with up/down arrows.
 */
export function AssessmentProgressCard({
  progress,
  onDismiss,
  onViewResult,
}: AssessmentProgressCardProps) {
  // Don't show if idle
  if (progress.status === "idle") {
    return null;
  }

  const isRunning = progress.status === "connecting" || progress.status === "running";
  const isComplete = progress.status === "completed";
  const isError = progress.status === "error";

  const stageLabel = progress.stage
    ? STAGE_LABELS[progress.stage] || progress.stage
    : "Starting...";

  return (
    <div
      className={cn(
        "fixed bottom-4 right-4 z-50",
        "w-80 rounded-lg shadow-lg border",
        "bg-card",
        isComplete && "border-success/50",
        isError && "border-destructive/50",
        isRunning && "border-info/50"
      )}
    >
      {/* Header */}
      <div
        className={cn(
          "px-4 py-3 rounded-t-lg flex items-center justify-between",
          isComplete && "bg-success/10",
          isError && "bg-destructive/10",
          isRunning && "bg-info/10"
        )}
      >
        <div className="flex items-center gap-2">
          {isRunning && (
            <Loader2 className="h-4 w-4 animate-spin text-info" />
          )}
          {isComplete && (
            <CheckCircle2 className="h-4 w-4 text-success" />
          )}
          {isError && (
            <XCircle className="h-4 w-4 text-destructive" />
          )}
          <span
            className={cn(
              "font-medium text-sm",
              isComplete && "text-success",
              isError && "text-destructive",
              isRunning && "text-info"
            )}
          >
            {isRunning && "Running Assessment..."}
            {isComplete && "Assessment Complete"}
            {isError && "Assessment Failed"}
          </span>
        </div>
        {(isComplete || isError) && onDismiss && (
          <button
            onClick={onDismiss}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Body */}
      <div className="p-4 space-y-3">
        {/* Stage progress */}
        {isRunning && (
          <div>
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>Stage</span>
              <span
                className={cn(
                  progress.stageStatus === "running"
                    ? "text-info"
                    : "text-foreground"
                )}
              >
                {stageLabel}
              </span>
            </div>
            <div className="h-1.5 bg-muted rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  "bg-info animate-pulse"
                )}
                style={{
                  width: progress.stage === "processing" ? "60%" : "30%",
                }}
              />
            </div>
          </div>
        )}

        {/* Token counts */}
        <div className="grid grid-cols-2 gap-3">
          <div className="flex items-center gap-2 p-2 bg-muted/50 rounded">
            <ArrowUp className="h-4 w-4 text-success" />
            <div>
              <div className="text-sm font-medium text-foreground">
                {progress.inputTokens.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">Input tokens</div>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 bg-muted/50 rounded">
            <ArrowDown className="h-4 w-4 text-info" />
            <div>
              <div className="text-sm font-medium text-foreground">
                {progress.outputTokens.toLocaleString()}
              </div>
              <div className="text-xs text-muted-foreground">Output tokens</div>
            </div>
          </div>
        </div>

        {/* Completion info */}
        {isComplete && progress.decision && (
          <div className="pt-2 border-t border-border">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Decision:
              </span>
              <span
                className={cn(
                  "text-sm font-medium",
                  progress.decision === "APPROVE" && "text-success",
                  progress.decision === "REJECT" && "text-destructive",
                  progress.decision === "REFER_TO_HUMAN" && "text-warning"
                )}
              >
                {progress.decision}
              </span>
            </div>
            {onViewResult && (
              <button
                onClick={onViewResult}
                className="mt-2 w-full py-2 text-sm font-medium text-primary-foreground bg-primary hover:bg-primary/90 rounded transition-colors"
              >
                View Result
              </button>
            )}
          </div>
        )}

        {/* Error message */}
        {isError && progress.error && (
          <div className="p-2 bg-destructive/10 rounded text-sm text-destructive">
            {progress.error}
          </div>
        )}
      </div>
    </div>
  );
}
