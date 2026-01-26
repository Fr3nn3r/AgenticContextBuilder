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
        "bg-white dark:bg-slate-900",
        isComplete && "border-green-300 dark:border-green-700",
        isError && "border-red-300 dark:border-red-700",
        isRunning && "border-blue-300 dark:border-blue-700"
      )}
    >
      {/* Header */}
      <div
        className={cn(
          "px-4 py-3 rounded-t-lg flex items-center justify-between",
          isComplete && "bg-green-50 dark:bg-green-900/30",
          isError && "bg-red-50 dark:bg-red-900/30",
          isRunning && "bg-blue-50 dark:bg-blue-900/30"
        )}
      >
        <div className="flex items-center gap-2">
          {isRunning && (
            <Loader2 className="h-4 w-4 animate-spin text-blue-600 dark:text-blue-400" />
          )}
          {isComplete && (
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
          )}
          {isError && (
            <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
          )}
          <span
            className={cn(
              "font-medium text-sm",
              isComplete && "text-green-700 dark:text-green-300",
              isError && "text-red-700 dark:text-red-300",
              isRunning && "text-blue-700 dark:text-blue-300"
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
            className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
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
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 mb-1">
              <span>Stage</span>
              <span
                className={cn(
                  progress.stageStatus === "running"
                    ? "text-blue-600 dark:text-blue-400"
                    : "text-slate-600 dark:text-slate-300"
                )}
              >
                {stageLabel}
              </span>
            </div>
            <div className="h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  "bg-blue-500 animate-pulse"
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
          <div className="flex items-center gap-2 p-2 bg-slate-50 dark:bg-slate-800 rounded">
            <ArrowUp className="h-4 w-4 text-green-500" />
            <div>
              <div className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {progress.inputTokens.toLocaleString()}
              </div>
              <div className="text-xs text-slate-500">Input tokens</div>
            </div>
          </div>
          <div className="flex items-center gap-2 p-2 bg-slate-50 dark:bg-slate-800 rounded">
            <ArrowDown className="h-4 w-4 text-blue-500" />
            <div>
              <div className="text-sm font-medium text-slate-700 dark:text-slate-200">
                {progress.outputTokens.toLocaleString()}
              </div>
              <div className="text-xs text-slate-500">Output tokens</div>
            </div>
          </div>
        </div>

        {/* Completion info */}
        {isComplete && progress.decision && (
          <div className="pt-2 border-t border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600 dark:text-slate-400">
                Decision:
              </span>
              <span
                className={cn(
                  "text-sm font-medium",
                  progress.decision === "APPROVE" &&
                    "text-green-600 dark:text-green-400",
                  progress.decision === "REJECT" &&
                    "text-red-600 dark:text-red-400",
                  progress.decision === "REFER_TO_HUMAN" &&
                    "text-amber-600 dark:text-amber-400"
                )}
              >
                {progress.decision}
              </span>
            </div>
            {onViewResult && (
              <button
                onClick={onViewResult}
                className="mt-2 w-full py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded transition-colors"
              >
                View Result
              </button>
            )}
          </div>
        )}

        {/* Error message */}
        {isError && progress.error && (
          <div className="p-2 bg-red-50 dark:bg-red-900/30 rounded text-sm text-red-600 dark:text-red-400">
            {progress.error}
          </div>
        )}
      </div>
    </div>
  );
}
