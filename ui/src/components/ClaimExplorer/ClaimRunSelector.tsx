import { useState } from "react";
import { ChevronDown, Clock, Check, Copy, CheckCircle } from "lucide-react";
import type { ClaimRunManifest } from "../../types";
import { cn } from "../../lib/utils";

const MAX_RUNS_DISPLAY = 5;

interface ClaimRunSelectorProps {
  runs: ClaimRunManifest[];
  selectedRunId: string | null;
  onSelect: (runId: string) => void;
  loading?: boolean;
}

/**
 * Dropdown selector for choosing a claim run version.
 * Shows the claim run ID with timestamp and stages completed.
 */
export function ClaimRunSelector({
  runs,
  selectedRunId,
  onSelect,
  loading,
}: ClaimRunSelectorProps) {
  const [copied, setCopied] = useState(false);
  const selectedRun = runs.find((r) => r.claim_run_id === selectedRunId);

  // Limit to MAX_RUNS_DISPLAY most recent runs
  const displayedRuns = runs.slice(0, MAX_RUNS_DISPLAY);

  const handleCopy = async () => {
    if (!selectedRunId) return;
    try {
      await navigator.clipboard.writeText(selectedRunId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error("Failed to copy:", err);
    }
  };

  // Format timestamp for display
  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      return new Intl.DateTimeFormat("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
    } catch {
      return dateStr;
    }
  };

  // Shorten run ID for display
  const shortenRunId = (runId: string) => {
    if (runId.length <= 24) return runId;
    return `${runId.slice(0, 16)}...${runId.slice(-6)}`;
  };

  if (runs.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        No claim runs available
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground">
        Claim Run:
      </span>
      <div className="relative">
        <select
          value={selectedRunId || ""}
          onChange={(e) => onSelect(e.target.value)}
          disabled={loading}
          className={cn(
            "appearance-none bg-card border border-border",
            "rounded-md pl-3 pr-8 py-1.5 text-sm font-mono",
            "text-foreground",
            "focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent",
            "disabled:opacity-50 disabled:cursor-not-allowed",
            "cursor-pointer"
          )}
        >
          {displayedRuns.map((run, index) => (
            <option key={run.claim_run_id} value={run.claim_run_id}>
              {shortenRunId(run.claim_run_id)}
              {index === 0 ? " (latest)" : ""}
            </option>
          ))}
        </select>
        <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none" />
      </div>
      <button
        onClick={handleCopy}
        disabled={!selectedRunId}
        className={cn(
          "p-1.5 rounded-md transition-colors",
          "hover:bg-muted text-muted-foreground hover:text-foreground",
          "disabled:opacity-50 disabled:cursor-not-allowed"
        )}
        title={copied ? "Copied!" : "Copy claim run ID"}
      >
        {copied ? (
          <CheckCircle className="h-4 w-4 text-success" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </button>
      {selectedRun && (
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {formatDate(selectedRun.created_at)}
          </span>
          {selectedRun.stages_completed.length > 0 && (
            <span className="flex items-center gap-1">
              <Check className="h-3 w-3 text-success" />
              {selectedRun.stages_completed.length} stages
            </span>
          )}
        </div>
      )}
    </div>
  );
}
