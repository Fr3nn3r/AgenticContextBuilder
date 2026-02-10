/**
 * Per-claim assessment progress stepper.
 *
 * Shows the assessment pipeline stages for each claim after extraction:
 * Reconcile -> Enrich -> Screen -> Process -> Decide
 *
 * Matches compact horizontal layout from PipelineProgress.tsx.
 */

import { cn } from '../lib/utils';
import type { AssessmentPhase, ClaimAssessmentProgress } from '../types';

export interface AssessmentProgressProps {
  claims: Record<string, ClaimAssessmentProgress>;
  phase: 'idle' | 'running' | 'complete';
  onRetry?: (claimIds: string[]) => void;
  isRetrying?: boolean;
}

// Assessment stages in display order
const ASSESSMENT_STAGES: AssessmentPhase[] = [
  'reconciliation',
  'enrichment',
  'screening',
  'processing',
  'decision',
];

const STAGE_LABELS: Record<string, string> = {
  reconciliation: 'Reconcile',
  enrichment: 'Enrich',
  screening: 'Screen',
  processing: 'Process',
  decision: 'Decide',
};

export function AssessmentProgress({ claims, phase, onRetry, isRetrying }: AssessmentProgressProps) {
  const claimList = Object.values(claims);

  if (claimList.length === 0) return null;

  const completedCount = claimList.filter(
    (c) => c.phase === 'complete'
  ).length;
  const errorCount = claimList.filter(
    (c) => c.phase === 'error'
  ).length;
  const failedClaimIds = claimList
    .filter((c) => c.phase === 'error')
    .map((c) => c.claim_id);

  return (
    <div className="border border-border rounded-xl overflow-hidden bg-card shadow-sm">
      {/* Compact header: status badge + title + counters inline */}
      <div className="px-5 py-3 bg-muted/60 border-b border-border">
        <div className="flex items-center justify-between gap-4">
          {/* Left: status + title */}
          <div className="flex items-center gap-3 min-w-0">
            <AssessmentStatusBadge phase={phase} hasErrors={errorCount > 0} />
            <span className="text-xs font-medium text-foreground">
              Claim Assessment
            </span>
          </div>

          {/* Right: counters + retry button */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="flex items-center gap-2">
              {completedCount > 0 && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 px-2 py-0.5 rounded-full">
                  <CheckIcon className="w-3 h-3" />
                  {completedCount}
                </span>
              )}
              {errorCount > 0 && (
                <span className="inline-flex items-center gap-1 text-xs font-medium text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full">
                  <XIcon className="w-3 h-3" />
                  {errorCount}
                </span>
              )}
              {phase === 'running' && completedCount === 0 && errorCount === 0 && (
                <span className="text-xs text-muted-foreground tabular-nums">
                  0/{claimList.length}
                </span>
              )}
            </div>

            {/* Retry button when there are errors and assessment is done */}
            {errorCount > 0 && phase === 'complete' && onRetry && (
              <button
                onClick={() => onRetry(failedClaimIds)}
                disabled={isRetrying}
                className={cn(
                  "px-2.5 py-1 text-xs font-medium rounded-md border transition-colors",
                  isRetrying
                    ? "text-muted-foreground bg-muted border-border cursor-not-allowed"
                    : "text-purple-700 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-800 hover:bg-purple-100 dark:hover:bg-purple-900/40"
                )}
              >
                {isRetrying ? (
                  <span className="flex items-center gap-1">
                    <SpinnerIcon className="w-3 h-3 animate-spin" />
                    Retrying
                  </span>
                ) : (
                  <span className="flex items-center gap-1">
                    <RetryIcon className="w-3 h-3" />
                    Retry Failed
                  </span>
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Per-claim rows */}
      <div className="divide-y divide-border/60">
        {claimList.map((claim) => (
          <ClaimAssessmentRow key={claim.claim_id} claim={claim} />
        ))}
      </div>

      {/* Grouped errors at bottom */}
      {errorCount > 0 && (
        <div className="border-t border-border bg-red-50/40 dark:bg-red-900/5 px-5 py-3">
          <div className="space-y-2">
            {claimList
              .filter((c) => c.phase === 'error' && c.error)
              .map((claim) => (
                <div key={claim.claim_id} className="flex items-center gap-1.5 text-xs">
                  <XCircleIcon className="w-3.5 h-3.5 shrink-0 text-red-600 dark:text-red-400" />
                  <code className="font-mono text-red-600 dark:text-red-400 shrink-0">{claim.claim_id}:</code>
                  <span className="text-red-700 dark:text-red-400 truncate">{claim.error}</span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ClaimAssessmentRow({ claim }: { claim: ClaimAssessmentProgress }) {
  const isError = claim.phase === 'error';
  const isComplete = claim.phase === 'complete';

  return (
    <div
      className={cn(
        'px-5 py-3 transition-colors',
        isError && 'bg-red-50/30 dark:bg-red-900/5',
        isComplete && 'bg-green-50/20 dark:bg-green-900/5'
      )}
    >
      <div className="flex items-center gap-4">
        {/* Claim ID - left column */}
        <div className="w-48 shrink-0 min-w-0">
          <code className="text-sm font-mono text-foreground truncate block">{claim.claim_id}</code>
        </div>

        {/* Stage stepper - center */}
        <div className="flex items-center gap-0.5 flex-1 min-w-0">
          {ASSESSMENT_STAGES.map((stage, idx) => (
            <AssessmentStageStep
              key={stage}
              stage={stage}
              currentPhase={claim.phase}
              failedAtStage={claim.failed_at_stage}
              isLast={idx === ASSESSMENT_STAGES.length - 1}
            />
          ))}
        </div>

        {/* Decision badge - right column */}
        <div className="shrink-0">
          <DecisionBadge claim={claim} />
        </div>
      </div>
    </div>
  );
}

function AssessmentStatusBadge({ phase, hasErrors }: { phase: 'idle' | 'running' | 'complete'; hasErrors: boolean }) {
  if (phase === 'running') {
    return (
      <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md border bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 border-purple-200/50 dark:border-purple-800/50">
        Assessing
      </span>
    );
  }

  if (phase === 'complete' && hasErrors) {
    return (
      <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md border bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-200/50 dark:border-red-800/50">
        Failed
      </span>
    );
  }

  if (phase === 'complete') {
    return (
      <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md border bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-200/50 dark:border-green-800/50">
        Assessed
      </span>
    );
  }

  return (
    <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md border bg-muted text-muted-foreground border-border/50">
      Pending
    </span>
  );
}

function DecisionBadge({ claim }: { claim: ClaimAssessmentProgress }) {
  if (claim.phase === 'error') {
    return (
      <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border border-red-200/50 dark:border-red-800/50">
        Error
      </span>
    );
  }

  if (claim.phase === 'complete' && claim.decision) {
    const colorMap: Record<string, string> = {
      APPROVE: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-200/50 dark:border-green-800/50',
      REJECT: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-200/50 dark:border-red-800/50',
      DENY: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-200/50 dark:border-red-800/50',
      REFER_TO_HUMAN: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 border-yellow-200/50 dark:border-yellow-800/50',
      REFER: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 border-yellow-200/50 dark:border-yellow-800/50',
    };
    const color = colorMap[claim.decision] || 'bg-muted text-muted-foreground border-border/50';
    return (
      <span className={cn('px-2 py-0.5 text-[11px] font-semibold rounded-md border', color)}>
        {claim.decision}
      </span>
    );
  }

  if (claim.phase === 'pending') {
    return (
      <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-muted text-muted-foreground border border-border/50">
        Waiting
      </span>
    );
  }

  // Running
  return (
    <span className="px-2 py-0.5 text-[11px] font-medium rounded-md bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 border border-purple-200/50 dark:border-purple-800/50 flex items-center gap-1">
      <SpinnerIcon className="w-2.5 h-2.5 animate-spin" />
      {STAGE_LABELS[claim.phase] || claim.phase}
    </span>
  );
}

interface AssessmentStageStepProps {
  stage: AssessmentPhase;
  currentPhase: AssessmentPhase;
  failedAtStage?: AssessmentPhase;
  isLast: boolean;
}

function AssessmentStageStep({ stage, currentPhase, failedAtStage, isLast }: AssessmentStageStepProps) {
  const stageIndex = ASSESSMENT_STAGES.indexOf(stage);
  const currentIndex = ASSESSMENT_STAGES.indexOf(currentPhase);

  let state: 'pending' | 'active' | 'completed' | 'failed';

  if (currentPhase === 'error') {
    const failedIndex = failedAtStage ? ASSESSMENT_STAGES.indexOf(failedAtStage) : -1;
    if (failedIndex >= 0) {
      if (stageIndex < failedIndex) {
        state = 'completed';
      } else if (stageIndex === failedIndex) {
        state = 'failed';
      } else {
        state = 'pending';
      }
    } else {
      // No failed_at_stage info -- mark first stage as failed
      state = stageIndex === 0 ? 'failed' : 'pending';
    }
  } else if (currentPhase === 'complete') {
    state = 'completed';
  } else if (currentPhase === 'pending') {
    state = 'pending';
  } else if (stageIndex < currentIndex) {
    state = 'completed';
  } else if (stageIndex === currentIndex) {
    state = 'active';
  } else {
    state = 'pending';
  }

  // Connector after active/failed should appear pending
  let connectorState = state;
  if (state === 'failed' || state === 'active') {
    connectorState = 'pending';
  }

  return (
    <div className="flex items-center flex-1">
      <div className="flex flex-col items-center">
        <StageCircle state={state} />
        <span
          className={cn(
            'text-[10px] mt-0.5 whitespace-nowrap leading-none',
            state === 'completed' && 'text-green-600 dark:text-green-400',
            state === 'active' && 'text-purple-600 dark:text-purple-400 font-medium',
            state === 'failed' && 'text-red-600 dark:text-red-400 font-medium',
            state === 'pending' && 'text-muted-foreground/60'
          )}
        >
          {STAGE_LABELS[stage]}
        </span>
      </div>
      {!isLast && (
        <div
          className={cn(
            'flex-1 h-px mx-0.5 mt-[-10px]',
            connectorState === 'completed'
              ? 'bg-green-400 dark:bg-green-500/60'
              : connectorState === 'active'
                ? 'bg-purple-400'
                : connectorState === 'failed'
                  ? 'bg-red-400'
                  : 'bg-border'
          )}
        />
      )}
    </div>
  );
}

function StageCircle({ state }: { state: 'pending' | 'active' | 'completed' | 'failed' }) {
  const baseClasses = 'w-5 h-5 rounded-full flex items-center justify-center transition-all';

  switch (state) {
    case 'completed':
      return (
        <div className={cn(baseClasses, 'bg-green-500 dark:bg-green-600 text-white')}>
          <CheckIcon className="w-3 h-3" />
        </div>
      );
    case 'active':
      return (
        <div className={cn(baseClasses, 'bg-purple-500 text-white shadow-sm shadow-purple-500/30')}>
          <SpinnerIcon className="w-3 h-3 animate-spin" />
        </div>
      );
    case 'failed':
      return (
        <div className={cn(baseClasses, 'bg-red-500 text-white')}>
          <XIcon className="w-3 h-3" />
        </div>
      );
    default:
      return (
        <div className={cn(baseClasses, 'bg-muted/80 border border-border')}>
          <div className="w-1.5 h-1.5 rounded-full bg-muted-foreground/30" />
        </div>
      );
  }
}

// Icons (matching PipelineProgress.tsx style)

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
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

function RetryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  );
}
