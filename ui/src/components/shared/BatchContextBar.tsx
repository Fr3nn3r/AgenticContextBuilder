import { useState } from "react";
import { cn } from "../../lib/utils";
import { formatTimestamp } from "../../lib/formatters";
import type { DetailedRunInfo } from "../../api/client";

interface BatchContextBarProps {
  batches: DetailedRunInfo[];
  selectedBatchId: string | null;
  onBatchChange: (batchId: string) => void;
  selectedBatch: DetailedRunInfo | null;
  className?: string;
}

export function BatchContextBar({
  batches,
  selectedBatchId,
  onBatchChange,
  selectedBatch,
  className,
}: BatchContextBarProps) {
  const [copiedId, setCopiedId] = useState(false);

  // Sort batches by run_id (descending - most recent first)
  const sortedBatches = [...batches].sort((a, b) =>
    b.run_id.localeCompare(a.run_id)
  );

  const handleCopyId = async () => {
    if (!selectedBatchId) return;
    try {
      await navigator.clipboard.writeText(selectedBatchId);
      setCopiedId(true);
      setTimeout(() => setCopiedId(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  return (
    <div
      className={cn(
        "bg-white border-b px-6 py-3 flex items-center justify-between",
        className
      )}
      data-testid="batch-context-bar"
    >
      <div className="flex items-center gap-4">
        {/* Batch selector */}
        <div className="flex items-center gap-2">
          <BatchIcon className="w-5 h-5 text-gray-500" />
          <select
            data-testid="batch-context-selector"
            value={selectedBatchId || ""}
            onChange={(e) => onBatchChange(e.target.value)}
            className="border rounded-md px-3 py-1.5 text-sm font-medium min-w-[200px] bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            {sortedBatches.map((batch) => (
              <option key={batch.run_id} value={batch.run_id}>
                {batch.run_id}
              </option>
            ))}
          </select>
        </div>

        {/* Batch metadata */}
        {selectedBatch && (
          <div className="flex items-center gap-4 text-sm text-gray-600 border-l pl-4">
            <span className="flex items-center gap-1">
              <ModelIcon className="w-4 h-4" />
              {selectedBatch.model}
            </span>
            <span className="flex items-center gap-1">
              <DocsIcon className="w-4 h-4" />
              {selectedBatch.docs_total} docs
            </span>
            {selectedBatch.timestamp && (
              <span className="flex items-center gap-1">
                <ClockIcon className="w-4 h-4" />
                {formatTimestamp(selectedBatch.timestamp)}
              </span>
            )}
            <StatusBadge status={selectedBatch.status} />
          </div>
        )}
      </div>

      {/* Copy ID button */}
      <button
        onClick={handleCopyId}
        disabled={!selectedBatchId}
        className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 disabled:opacity-50"
        title="Copy batch ID"
      >
        {copiedId ? (
          <>
            <CheckIcon className="w-4 h-4 text-green-600" />
            <span className="text-green-600">Copied!</span>
          </>
        ) : (
          <>
            <CopyIcon className="w-4 h-4" />
            <span>Copy ID</span>
          </>
        )}
      </button>
    </div>
  );
}

function StatusBadge({ status }: { status: "complete" | "partial" | "failed" }) {
  const config = {
    complete: { bg: "bg-green-100", text: "text-green-700", label: "Complete" },
    partial: { bg: "bg-yellow-100", text: "text-yellow-700", label: "Partial" },
    failed: { bg: "bg-red-100", text: "text-red-700", label: "Failed" },
  };
  const { bg, text, label } = config[status];

  return (
    <span className={cn("px-2 py-0.5 rounded-full text-xs font-medium", bg, text)}>
      {label}
    </span>
  );
}

// Icon components
function BatchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
      />
    </svg>
  );
}

function ModelIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
      />
    </svg>
  );
}

function DocsIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
      />
    </svg>
  );
}

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

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}
