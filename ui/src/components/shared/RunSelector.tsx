import { cn } from "../../lib/utils";

interface BaseRunInfo {
  run_id: string;
  timestamp: string | null;
  model?: string | null;
  docs_count?: number;
  docs_total?: number;
  claims_count?: number;
}

interface RunSelectorProps<T extends BaseRunInfo> {
  runs: T[];
  selectedRunId: string | null;
  onRunChange: (runId: string) => void;
  /** Show metadata inline (model, doc count) */
  showMetadata?: boolean;
  className?: string;
  /** Test ID for e2e tests */
  testId?: string;
}

/**
 * Format timestamp to human-readable format: "Jan 7 at 9:40 AM"
 */
export function formatRunLabel(timestamp: string | null): string {
  if (!timestamp) return "";

  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) return "";

    const month = date.toLocaleString("en-US", { month: "short" });
    const day = date.getDate();
    const time = date.toLocaleString("en-US", {
      hour: "numeric",
      minute: "2-digit",
      hour12: true
    });

    return `${month} ${day} at ${time}`;
  } catch {
    return "";
  }
}

/**
 * Shared run selector component with human-readable labels
 */
export function RunSelector<T extends BaseRunInfo>({
  runs,
  selectedRunId,
  onRunChange,
  showMetadata = false,
  className,
  testId,
}: RunSelectorProps<T>) {
  // Sort runs by timestamp descending (newest first)
  const sortedRuns = [...runs].sort((a, b) => {
    if (!a.timestamp && !b.timestamp) return 0;
    if (!a.timestamp) return 1;
    if (!b.timestamp) return -1;
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });

  const selectedRun = sortedRuns.find(r => r.run_id === selectedRunId);
  const docsCount = selectedRun?.docs_count ?? selectedRun?.docs_total ?? 0;

  return (
    <div className={cn("flex items-center gap-4", className)}>
      <div className="flex items-center gap-2">
        <label className="text-sm font-medium text-gray-700">Run:</label>
        <select
          data-testid={testId || "run-selector"}
          value={selectedRunId || ""}
          onChange={(e) => onRunChange(e.target.value)}
          className="border rounded-md px-3 py-1.5 text-sm min-w-[180px] bg-white"
        >
          {sortedRuns.map((run, idx) => {
            const label = formatRunLabel(run.timestamp);
            const isLatest = idx === 0;
            return (
              <option key={run.run_id} value={run.run_id}>
                {label || run.run_id}
                {isLatest ? " (Latest)" : ""}
              </option>
            );
          })}
        </select>
      </div>

      {showMetadata && selectedRun && (
        <div className="flex items-center gap-3 text-xs text-gray-500 border-l pl-4">
          {selectedRun.model && (
            <span>
              <strong>Model:</strong> {selectedRun.model}
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
