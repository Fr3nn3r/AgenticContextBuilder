/**
 * Pipeline progress display with per-document stage stepper.
 *
 * Features:
 * - Per-document stage stepper showing: Pending → Ingesting → Classifying → Extracting → Done
 * - Visual progress indicators for each stage
 * - Clear indication of which stage failed
 * - Progress bar for overall completion
 * - Error display with stage context
 */

import { cn } from '../lib/utils';
import type { DocPipelinePhase, DocProgress, PipelineBatchStatus } from '../types';

export interface PipelineProgressProps {
  batchId: string;
  status: PipelineBatchStatus;
  docs: Record<string, DocProgress>;
  summary?: {
    total: number;
    success: number;
    failed: number;
  };
  onCancel?: () => void;
  isConnected?: boolean;
  isConnecting?: boolean;
  isReconnecting?: boolean;
}

// Pipeline stages in order
const STAGES: DocPipelinePhase[] = ['pending', 'ingesting', 'classifying', 'extracting', 'done'];

// Stage display names
const STAGE_LABELS: Record<DocPipelinePhase, string> = {
  pending: 'Pending',
  ingesting: 'Ingest',
  classifying: 'Classify',
  extracting: 'Extract',
  done: 'Done',
  failed: 'Failed',
};

export function PipelineProgress({
  batchId,
  status,
  docs,
  summary,
  onCancel,
  isConnected: _isConnected = true,
  isConnecting = false,
  isReconnecting = false,
}: PipelineProgressProps) {
  const docList = Object.values(docs);
  const completedCount = docList.filter(
    (d) => d.phase === 'done' || d.phase === 'failed'
  ).length;
  const totalCount = docList.length;
  const progressPercent = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  const isRunning = status === 'running' || status === 'pending';
  const isComplete = status === 'completed' || status === 'failed' || status === 'cancelled';

  return (
    <div className="border border-border rounded-lg overflow-hidden bg-card shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-muted border-b border-border">
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          <span className="text-sm text-muted-foreground font-mono">Batch: {batchId}</span>
          {/* Connection status indicators */}
          {_isConnected && isRunning && !isConnecting && !isReconnecting && (
            <span className="text-xs text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/30 px-2 py-0.5 rounded flex items-center gap-1">
              <LiveDotIcon className="w-2 h-2" />
              Connected
            </span>
          )}
          {isConnecting && isRunning && (
            <span className="text-xs text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/30 px-2 py-0.5 rounded flex items-center gap-1">
              <SpinnerIcon className="w-3 h-3 animate-spin" />
              Connecting...
            </span>
          )}
          {isReconnecting && isRunning && (
            <span className="text-xs text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/30 px-2 py-0.5 rounded flex items-center gap-1">
              <SpinnerIcon className="w-3 h-3 animate-spin" />
              Reconnecting...
            </span>
          )}
        </div>
        {isRunning && onCancel && (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded transition-colors font-medium"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Overall Progress Bar (when running) */}
      {isRunning && (
        <div className="px-4 py-3 border-b border-border bg-blue-50/30 dark:bg-blue-900/10">
          <div className="flex items-center justify-between text-sm text-foreground mb-2">
            <span className="font-medium">Overall Progress</span>
            <span className="text-muted-foreground">
              {completedCount} of {totalCount} documents
            </span>
          </div>
          <div className="w-full bg-muted rounded-full h-2.5 overflow-hidden">
            <div
              className="bg-blue-500 h-2.5 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Summary (when complete) */}
      {isComplete && summary && (
        <div className="px-4 py-3 border-b border-border bg-muted">
          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <CheckIcon className="w-5 h-5 text-green-600 dark:text-green-400" />
              </div>
              <div>
                <div className="font-semibold text-green-700 dark:text-green-400">{summary.success}</div>
                <div className="text-xs text-muted-foreground">Succeeded</div>
              </div>
            </div>
            {summary.failed > 0 && (
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                  <XIcon className="w-5 h-5 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <div className="font-semibold text-red-700 dark:text-red-400">{summary.failed}</div>
                  <div className="text-xs text-muted-foreground">Failed</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Stage Legend */}
      <div className="px-4 py-2 border-b border-border bg-muted/50">
        <div className="flex items-center gap-1 text-xs text-muted-foreground">
          <span className="font-medium mr-2">Stages:</span>
          {STAGES.filter(s => s !== 'pending').map((stage, idx) => (
            <span key={stage} className="flex items-center gap-1">
              {idx > 0 && <span className="text-muted-foreground/50 mx-1">→</span>}
              {STAGE_LABELS[stage]}
            </span>
          ))}
        </div>
      </div>

      {/* Document List */}
      <div className="divide-y divide-border">
        {docList.map((doc) => (
          <DocumentProgressRow key={doc.doc_id} doc={doc} />
        ))}
      </div>
    </div>
  );
}

interface DocumentProgressRowProps {
  doc: DocProgress;
}

function DocumentProgressRow({ doc }: DocumentProgressRowProps) {
  const isFailed = doc.phase === 'failed';
  const failedAtStage = doc.failed_at_stage;

  return (
    <div className={cn(
      "px-4 py-3",
      isFailed && "bg-red-50/30 dark:bg-red-900/10"
    )}>
      {/* Document info */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-foreground truncate">{doc.filename}</p>
          <p className="text-xs text-muted-foreground font-mono">{doc.claim_id}</p>
        </div>
        <PhaseLabel phase={doc.phase} failedAtStage={failedAtStage} />
      </div>

      {/* Stage Stepper */}
      <div className="flex items-center gap-1">
        {STAGES.filter(s => s !== 'pending').map((stage, idx) => (
          <StageStep
            key={stage}
            stage={stage}
            currentPhase={doc.phase}
            failedAtStage={failedAtStage}
            isLast={idx === STAGES.length - 2}
          />
        ))}
      </div>

      {/* Error message */}
      {doc.error && (
        <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-xs text-red-700 dark:text-red-400">
          <div className="font-medium mb-0.5">
            Failed at {failedAtStage ? STAGE_LABELS[failedAtStage] : 'unknown'} stage:
          </div>
          {doc.error}
        </div>
      )}
    </div>
  );
}

interface StageStepProps {
  stage: DocPipelinePhase;
  currentPhase: DocPipelinePhase;
  failedAtStage?: DocPipelinePhase;
  isLast: boolean;
}

function StageStep({ stage, currentPhase, failedAtStage, isLast }: StageStepProps) {
  const stageIndex = STAGES.indexOf(stage);
  const currentIndex = STAGES.indexOf(currentPhase);
  const isFailed = currentPhase === 'failed';
  const failedIndex = failedAtStage ? STAGES.indexOf(failedAtStage) : -1;

  // Determine the state of this stage step
  let state: 'pending' | 'active' | 'completed' | 'failed';

  if (isFailed) {
    // Document failed
    if (stageIndex < failedIndex) {
      state = 'completed'; // Stages before failure completed
    } else if (stageIndex === failedIndex) {
      state = 'failed'; // This is where it failed
    } else {
      state = 'pending'; // Stages after failure never ran
    }
  } else if (currentPhase === 'done') {
    state = 'completed';
  } else if (stageIndex < currentIndex) {
    state = 'completed';
  } else if (stageIndex === currentIndex) {
    state = 'active';
  } else {
    state = 'pending';
  }

  return (
    <div className="flex items-center flex-1">
      {/* Stage circle */}
      <div className="flex flex-col items-center">
        <StageCircle state={state} />
        <span className={cn(
          "text-[10px] mt-1 whitespace-nowrap",
          state === 'completed' && "text-green-600 dark:text-green-400",
          state === 'active' && "text-blue-600 dark:text-blue-400 font-medium",
          state === 'failed' && "text-red-600 dark:text-red-400 font-medium",
          state === 'pending' && "text-muted-foreground"
        )}>
          {STAGE_LABELS[stage]}
        </span>
      </div>

      {/* Connector line */}
      {!isLast && (
        <div className={cn(
          "flex-1 h-0.5 mx-1 mt-[-12px]",
          state === 'completed' ? "bg-green-400" :
          state === 'active' ? "bg-blue-400" :
          state === 'failed' ? "bg-red-400" :
          "bg-muted"
        )} />
      )}
    </div>
  );
}

function StageCircle({ state }: { state: 'pending' | 'active' | 'completed' | 'failed' }) {
  const baseClasses = "w-6 h-6 rounded-full flex items-center justify-center transition-all";

  switch (state) {
    case 'completed':
      return (
        <div className={cn(baseClasses, "bg-green-500 text-white")}>
          <CheckIcon className="w-4 h-4" />
        </div>
      );
    case 'active':
      return (
        <div className={cn(baseClasses, "bg-blue-500 text-white")}>
          <SpinnerIcon className="w-4 h-4 animate-spin" />
        </div>
      );
    case 'failed':
      return (
        <div className={cn(baseClasses, "bg-red-500 text-white")}>
          <XIcon className="w-4 h-4" />
        </div>
      );
    default:
      return (
        <div className={cn(baseClasses, "bg-muted text-muted-foreground")}>
          <div className="w-2 h-2 rounded-full bg-muted-foreground" />
        </div>
      );
  }
}

function PhaseLabel({ phase, failedAtStage }: { phase: DocPipelinePhase; failedAtStage?: DocPipelinePhase }) {
  if (phase === 'failed') {
    const stageLabel = failedAtStage ? STAGE_LABELS[failedAtStage] : 'Unknown';
    return (
      <span className="px-2 py-1 text-xs font-medium rounded bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400">
        Failed at {stageLabel}
      </span>
    );
  }

  if (phase === 'done') {
    return (
      <span className="px-2 py-1 text-xs font-medium rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">
        Complete
      </span>
    );
  }

  if (phase === 'pending') {
    return (
      <span className="px-2 py-1 text-xs font-medium rounded bg-muted text-muted-foreground">
        Waiting
      </span>
    );
  }

  return (
    <span className="px-2 py-1 text-xs font-medium rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 flex items-center gap-1">
      <SpinnerIcon className="w-3 h-3 animate-spin" />
      {STAGE_LABELS[phase]}...
    </span>
  );
}

function StatusBadge({ status }: { status: PipelineBatchStatus }) {
  const config: Record<string, { label: string; color: string }> = {
    pending: { label: 'Pending', color: 'bg-muted text-muted-foreground' },
    running: { label: 'Running', color: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' },
    started: { label: 'Running', color: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' },
    completed: { label: 'Completed', color: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' },
    failed: { label: 'Failed', color: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400' },
    cancelled: { label: 'Cancelled', color: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400' },
  };

  const { label, color } = config[status] || { label: status, color: 'bg-muted text-muted-foreground' };

  return (
    <span className={cn('px-2.5 py-1 text-xs font-semibold rounded-full', color)}>
      {label}
    </span>
  );
}

// Icons

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24">
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function LiveDotIcon({ className }: { className?: string }) {
  return (
    <span className={cn("relative flex", className)}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
      <span className="relative inline-flex rounded-full h-full w-full bg-green-500" />
    </span>
  );
}
