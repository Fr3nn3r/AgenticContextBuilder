/**
 * Pipeline progress display with per-document status.
 *
 * Features:
 * - Per-document phase status with icons
 * - Progress bar for overall completion
 * - Error display with details
 * - Timing information
 */

import { cn } from '../lib/utils';
import type { DocPipelinePhase, DocProgress, PipelineRunStatus } from '../types';

export interface PipelineProgressProps {
  runId: string;
  status: PipelineRunStatus;
  docs: Record<string, DocProgress>;
  summary?: {
    total: number;
    success: number;
    failed: number;
  };
  onCancel?: () => void;
  isConnected?: boolean;
}

export function PipelineProgress({
  runId,
  status,
  docs,
  summary,
  onCancel,
  isConnected = true,
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
    <div className="border rounded-lg overflow-hidden bg-white">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50 border-b">
        <div className="flex items-center gap-3">
          <StatusBadge status={status} />
          <span className="text-sm text-gray-500">Run: {runId}</span>
          {!isConnected && isRunning && (
            <span className="text-xs text-yellow-600 bg-yellow-50 px-2 py-0.5 rounded">
              Reconnecting...
            </span>
          )}
        </div>
        {isRunning && onCancel && (
          <button
            onClick={onCancel}
            className="px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded transition-colors"
          >
            Cancel
          </button>
        )}
      </div>

      {/* Progress Bar */}
      {isRunning && (
        <div className="px-4 py-3 border-b">
          <div className="flex items-center justify-between text-sm text-gray-600 mb-2">
            <span>Processing documents</span>
            <span>
              {completedCount} / {totalCount}
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      )}

      {/* Summary (when complete) */}
      {isComplete && summary && (
        <div className="px-4 py-3 border-b bg-gray-50">
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1.5">
              <CheckCircleIcon className="w-4 h-4 text-green-500" />
              <span>{summary.success} succeeded</span>
            </div>
            {summary.failed > 0 && (
              <div className="flex items-center gap-1.5">
                <XCircleIcon className="w-4 h-4 text-red-500" />
                <span>{summary.failed} failed</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Document List */}
      <div className="divide-y max-h-80 overflow-y-auto">
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
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <PhaseIcon phase={doc.phase} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{doc.filename}</p>
        <p className="text-xs text-gray-500">
          {doc.claim_id} &middot; {getPhaseLabel(doc.phase)}
        </p>
        {doc.error && (
          <p className="text-xs text-red-600 mt-1">{doc.error}</p>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: PipelineRunStatus }) {
  const config: Record<string, { label: string; color: string }> = {
    pending: { label: 'Pending', color: 'bg-gray-100 text-gray-700' },
    running: { label: 'Running', color: 'bg-blue-100 text-blue-700' },
    started: { label: 'Running', color: 'bg-blue-100 text-blue-700' },
    completed: { label: 'Completed', color: 'bg-green-100 text-green-700' },
    failed: { label: 'Failed', color: 'bg-red-100 text-red-700' },
    cancelled: { label: 'Cancelled', color: 'bg-yellow-100 text-yellow-700' },
  };

  const { label, color } = config[status] || { label: status, color: 'bg-gray-100 text-gray-700' };

  return (
    <span className={cn('px-2 py-1 text-xs font-medium rounded', color)}>
      {label}
    </span>
  );
}

function PhaseIcon({ phase }: { phase: DocPipelinePhase }) {
  switch (phase) {
    case 'pending':
      return <ClockIcon className="w-5 h-5 text-gray-400" />;
    case 'ingesting':
      return <SpinnerIcon className="w-5 h-5 text-blue-500" />;
    case 'classifying':
      return <SpinnerIcon className="w-5 h-5 text-blue-500" />;
    case 'extracting':
      return <SpinnerIcon className="w-5 h-5 text-blue-500" />;
    case 'done':
      return <CheckCircleIcon className="w-5 h-5 text-green-500" />;
    case 'failed':
      return <XCircleIcon className="w-5 h-5 text-red-500" />;
  }
}

function getPhaseLabel(phase: DocPipelinePhase): string {
  const labels: Record<DocPipelinePhase, string> = {
    pending: 'Waiting',
    ingesting: 'Ingesting...',
    classifying: 'Classifying...',
    extracting: 'Extracting...',
    done: 'Complete',
    failed: 'Failed',
  };
  return labels[phase];
}

// Icons

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={cn(className, 'animate-spin')} fill="none" viewBox="0 0 24 24">
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

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 20 20">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function XCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="currentColor" viewBox="0 0 20 20">
      <path
        fillRule="evenodd"
        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
        clipRule="evenodd"
      />
    </svg>
  );
}
