import { cn } from "../../lib/utils";

interface BaseBatchInfo {
  batch_id: string;
  timestamp: string | null;
  model?: string | null;
  docs_count?: number;
  docs_total?: number;
  claims_count?: number;
}

interface BatchSelectorProps<T extends BaseBatchInfo> {
  batches: T[];
  selectedBatchId: string | null;
  onBatchChange: (batchId: string) => void;
  /** Show metadata inline (model, doc count) */
  showMetadata?: boolean;
  className?: string;
  /** Test ID for e2e tests */
  testId?: string;
}

/**
 * Shared batch selector component with alphabetically sorted batch IDs
 */
export function BatchSelector<T extends BaseBatchInfo>({
  batches,
  selectedBatchId,
  onBatchChange,
  showMetadata = false,
  className,
  testId,
}: BatchSelectorProps<T>) {
  // Sort batches by batch_id (descending - most recent first)
  const sortedBatches = [...batches].sort((a, b) =>
    b.batch_id.localeCompare(a.batch_id)
  );

  const selectedBatch = sortedBatches.find(b => b.batch_id === selectedBatchId);
  const docsCount = selectedBatch?.docs_count ?? selectedBatch?.docs_total ?? 0;

  return (
    <div className={cn("flex items-center gap-4", className)}>
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-foreground">Batch:</label>
        <select
          data-testid={testId || "batch-selector"}
          value={selectedBatchId || ""}
          onChange={(e) => onBatchChange(e.target.value)}
          className="border border-input rounded-md px-3 py-1.5 text-sm min-w-[180px] bg-background text-foreground"
        >
          {sortedBatches.map((batch) => (
            <option key={batch.batch_id} value={batch.batch_id}>
              {batch.batch_id}
            </option>
          ))}
        </select>
      </div>

      {showMetadata && selectedBatch && (
        <div className="flex items-center gap-3 text-xs text-muted-foreground border-l border-border pl-4">
          {selectedBatch.model && (
            <span>
              <strong>Model:</strong> {selectedBatch.model}
            </span>
          )}
          {docsCount > 0 && (
            <span>
              <strong>Docs:</strong> {docsCount}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
