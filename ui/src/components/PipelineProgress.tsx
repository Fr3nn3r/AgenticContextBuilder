/**
 * Pipeline progress display with per-document stage stepper.
 *
 * Features:
 * - Per-document stage stepper showing: Pending -> Ingesting -> Classifying -> Extracting -> Done
 * - Visual progress indicators for each stage
 * - Clear indication of which stage failed
 * - Progress bar for overall completion
 * - Error display with stage context
 * - Grouped errors to reduce repetition
 */

import { useMemo, useState } from 'react';
import { cn } from '../lib/utils';
import type { DocPipelinePhase, DocProgress, PipelineBatchStatus } from '../types';

export interface PipelineProgressProps {
  batchId: string;
  status: PipelineBatchStatus;
  docs: Record<string, DocProgress>;
  claimIds?: string[];
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
  claimIds = [],
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

  // Group documents that share the same error message to reduce repetition
  const groupedErrors = useMemo(() => {
    const errorGroups: Record<string, string[]> = {};
    docList.forEach((doc) => {
      if (doc.error) {
        const key = `${doc.failed_at_stage || 'unknown'}::${doc.error}`;
        if (!errorGroups[key]) errorGroups[key] = [];
        errorGroups[key].push(doc.filename);
      }
    });
    return errorGroups;
  }, [docList]);

  const [copiedId, setCopiedId] = useState<string | null>(null);

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(text);
      setTimeout(() => setCopiedId(null), 1500);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="border border-border rounded-xl overflow-hidden bg-card shadow-sm">
      {/* Compact header bar: status + batch + claims + summary inline */}
      <div className="px-5 py-3 bg-muted/60 border-b border-border">
        <div className="flex items-center justify-between gap-4">
          {/* Left: status badge + IDs */}
          <div className="flex items-center gap-3 min-w-0 flex-wrap">
            <StatusBadge status={status} />
            <span className="text-border hidden sm:inline">|</span>
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Batch</span>
              <code className="text-xs font-mono text-foreground bg-background/80 px-1.5 py-0.5 rounded border border-border/50">
                {batchId}
              </code>
              <button
                onClick={() => copyToClipboard(batchId)}
                className="p-0.5 text-muted-foreground hover:text-foreground rounded transition-colors"
                title="Copy Batch ID"
              >
                {copiedId === batchId ? <CheckIcon className="w-3 h-3 text-green-500" /> : <CopyIcon className="w-3 h-3" />}
              </button>
            </div>
            {claimIds.length > 0 && (
              <>
                <span className="text-border hidden sm:inline">|</span>
                {claimIds.map((claimId) => (
                  <div key={claimId} className="flex items-center gap-1">
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Claim</span>
                    <code className="text-xs font-mono text-foreground bg-background/80 px-1.5 py-0.5 rounded border border-border/50">
                      {claimId}
                    </code>
                    <button
                      onClick={() => copyToClipboard(claimId)}
                      className="p-0.5 text-muted-foreground hover:text-foreground rounded transition-colors"
                      title={`Copy ${claimId}`}
                    >
                      {copiedId === claimId ? <CheckIcon className="w-3 h-3 text-green-500" /> : <CopyIcon className="w-3 h-3" />}
                    </button>
                  </div>
                ))}
              </>
            )}
          </div>

          {/* Right: summary counters or cancel */}
          <div className="flex items-center gap-3 shrink-0">
            {/* Connection indicators (inline when running) */}
            {isRunning && (
              <>
                {_isConnected && !isConnecting && !isReconnecting && (
                  <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                    <LiveDotIcon className="w-1.5 h-1.5" />
                    <span className="hidden sm:inline">Live</span>
                  </span>
                )}
                {isConnecting && (
                  <span className="text-xs text-blue-600 dark:text-blue-400 flex items-center gap-1">
                    <SpinnerIcon className="w-3 h-3 animate-spin" />
                    <span className="hidden sm:inline">Connecting</span>
                  </span>
                )}
                {isReconnecting && (
                  <span className="text-xs text-yellow-600 dark:text-yellow-400 flex items-center gap-1">
                    <SpinnerIcon className="w-3 h-3 animate-spin" />
                    <span className="hidden sm:inline">Reconnecting</span>
                  </span>
                )}
                {!_isConnected && !isConnecting && !isReconnecting && (
                  <span className="text-xs text-red-600 dark:text-red-400 flex items-center gap-1">
                    <DisconnectedIcon className="w-3 h-3" />
                    <span className="hidden sm:inline">Disconnected</span>
                  </span>
                )}
              </>
            )}

            {/* Summary counters (when complete) */}
            {isComplete && summary && (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-2 py-0.5 rounded-full">
                  <CheckIcon className="w-3 h-3" />
                  {summary.success}
                </span>
                {summary.failed > 0 && (
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full">
                    <XIcon className="w-3 h-3" />
                    {summary.failed}
                  </span>
                )}
              </div>
            )}

            {isRunning && onCancel && (
              <button
                onClick={onCancel}
                className="px-2.5 py-1 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-md transition-colors font-medium border border-red-200 dark:border-red-800"
              >
                Cancel
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Overall Progress Bar (when running) */}
      {isRunning && (
        <div className="px-5 py-2.5 border-b border-border">
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-blue-500 h-1.5 rounded-full transition-all duration-500 ease-out"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
            <span className="text-xs text-muted-foreground tabular-nums shrink-0">
              {completedCount}/{totalCount}
            </span>
          </div>
        </div>
      )}

      {/* Document table */}
      <div className="divide-y divide-border/60">
        {docList.map((doc) => (
          <DocumentProgressRow key={doc.doc_id} doc={doc} />
        ))}
      </div>

      {/* Grouped error summary (when multiple docs share same error) */}
      {Object.keys(groupedErrors).length > 0 && (
        <div className="border-t border-border bg-red-50/40 dark:bg-red-900/5 px-5 py-3">
          <div className="space-y-2">
            {Object.entries(groupedErrors).map(([key, filenames]) => {
              const [stage, error] = key.split('::');
              const stageLabel = STAGE_LABELS[stage as DocPipelinePhase] || stage;
              return (
                <div key={key} className="flex items-center gap-1.5 text-xs">
                  <XCircleIcon className="w-3.5 h-3.5 shrink-0 text-red-600 dark:text-red-400" />
                  <span className="font-medium text-red-600 dark:text-red-400 shrink-0">{stageLabel}:</span>
                  <span className="text-red-700 dark:text-red-400 truncate">{error}</span>
                  {filenames.length > 1 && (
                    <span className="text-muted-foreground shrink-0">
                      ({filenames.length} files)
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

interface DocumentProgressRowProps {
  doc: DocProgress;
}

function DocumentProgressRow({ doc }: DocumentProgressRowProps) {
  const isFailed = doc.phase === 'failed';
  const isDone = doc.phase === 'done';
  const failedAtStage = doc.failed_at_stage;

  return (
    <div className={cn(
      "px-5 py-3 transition-colors",
      isFailed && "bg-red-50/30 dark:bg-red-900/5",
      isDone && "bg-green-50/20 dark:bg-green-900/5"
    )}>
      <div className="flex items-center gap-4">
        {/* File info - left column */}
        <div className="w-48 shrink-0 min-w-0">
          <p className="text-sm font-medium text-foreground truncate leading-tight">{doc.filename}</p>
          <p className="text-[10px] text-muted-foreground font-mono leading-tight mt-0.5">
            {doc.file_md5 ? doc.file_md5.slice(0, 12) : doc.doc_id.slice(0, 12)}
          </p>
        </div>

        {/* Stage Stepper - center, takes remaining space */}
        <div className="flex items-center gap-0.5 flex-1 min-w-0">
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

        {/* Phase label - right column */}
        <div className="shrink-0">
          <PhaseLabel phase={doc.phase} failedAtStage={failedAtStage} />
        </div>
      </div>
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

  // Determine connector state (line between this step and the next)
  let connectorState = state;
  if (state === 'failed' || state === 'active') {
    // The connector after the active/failed stage should appear pending
    connectorState = 'pending';
  }

  return (
    <div className="flex items-center flex-1">
      {/* Stage indicator */}
      <div className="flex flex-col items-center">
        <StageCircle state={state} />
        <span className={cn(
          "text-[10px] mt-0.5 whitespace-nowrap leading-none",
          state === 'completed' && "text-green-600 dark:text-green-400",
          state === 'active' && "text-blue-600 dark:text-blue-400 font-medium",
          state === 'failed' && "text-red-600 dark:text-red-400 font-medium",
          state === 'pending' && "text-muted-foreground/60"
        )}>
          {STAGE_LABELS[stage]}
        </span>
      </div>

      {/* Connector line */}
      {!isLast && (
        <div className={cn(
          "flex-1 h-px mx-0.5 mt-[-10px]",
          connectorState === 'completed' ? "bg-green-400 dark:bg-green-500/60" :
          connectorState === 'active' ? "bg-blue-400" :
          connectorState === 'failed' ? "bg-red-400" :
          "bg-border"
        )} />
      )}
    </div>
  );
}

function StageCircle({ state }: { state: 'pending' | 'active' | 'completed' | 'failed' }) {
  const baseClasses = "w-5 h-5 rounded-full flex items-center justify-center transition-all";

  switch (state) {
    case 'completed':
      return (
        <div className={cn(baseClasses, "bg-green-500 dark:bg-green-600 text-white")}>
          <CheckIcon className="w-3 h-3" />
        </div>
      );
    case 'active':
      return (
        <div className={cn(baseClasses, "bg-blue-500 text-white shadow-sm shadow-blue-500/30")}>
          <SpinnerIcon className="w-3 h-3 animate-spin" />
        </div>
      );
    case 'failed':
      return (
        <div className={cn(baseClasses, "bg-red-500 text-white")}>
          <XIcon className="w-3 h-3" />
        </div>
      );
    default:
      return (
        <div className={cn(baseClasses, "bg-muted/80 border border-border")}>
          <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30" />
        </div>
      );
  }
}

function PhaseLabel({ phase, failedAtStage }: { phase: DocPipelinePhase; failedAtStage?: DocPipelinePhase }) {
  if (phase === 'failed') {
    const stageLabel = failedAtStage ? STAGE_LABELS[failedAtStage] : 'Unknown';
    return (
      <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200/50 dark:border-red-800/50">
        Failed at {stageLabel}
      </span>
    );
  }

  if (phase === 'done') {
    return (
      <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border border-green-200/50 dark:border-green-800/50">
        Complete
      </span>
    );
  }

  if (phase === 'pending') {
    return (
      <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-muted text-muted-foreground border border-border/50">
        Waiting
      </span>
    );
  }

  return (
    <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 border border-blue-200/50 dark:border-blue-800/50 flex items-center gap-1">
      <SpinnerIcon className="w-2.5 h-2.5 animate-spin" />
      {STAGE_LABELS[phase]}
    </span>
  );
}

function StatusBadge({ status }: { status: PipelineBatchStatus }) {
  const config: Record<string, { label: string; color: string }> = {
    pending: { label: 'Pending', color: 'bg-muted text-muted-foreground border-border/50' },
    running: { label: 'Running', color: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 border-blue-200/50 dark:border-blue-800/50' },
    started: { label: 'Running', color: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 border-blue-200/50 dark:border-blue-800/50' },
    assessing: { label: 'Assessing', color: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 border-purple-200/50 dark:border-purple-800/50' },
    completed: { label: 'Completed', color: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-200/50 dark:border-green-800/50' },
    failed: { label: 'Failed', color: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-200/50 dark:border-red-800/50' },
    cancelled: { label: 'Cancelled', color: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 border-yellow-200/50 dark:border-yellow-800/50' },
  };

  const { label, color } = config[status] || { label: status, color: 'bg-muted text-muted-foreground border-border/50' };

  return (
    <span className={cn('px-2 py-0.5 text-[11px] font-semibold rounded-md border', color)}>
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

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function DisconnectedIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636a9 9 0 010 12.728M5.636 18.364a9 9 0 010-12.728" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 4l16 16" />
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

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
      />
    </svg>
  );
}
