import { Fragment, useMemo, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { cn } from "../lib/utils";
import {
  usePipelineClaims,
  usePipelineRuns,
  usePromptConfigs,
  useAuditLog,
} from "../hooks/usePipelineData";
import {
  startPipelineEnhanced,
  cancelPipeline,
  deletePipelineRun,
} from "../api/client";
import { useAuth } from "../context/AuthContext";
import { useBatch } from "../context/BatchContext";
import type {
  PipelineClaimOption,
  PromptConfig,
  AuditEntry,
  PipelineBatchStatus,
} from "../types";

// Types
type Stage = "ingest" | "classify" | "extract";
type BatchStatus = "running" | "success" | "partial" | "failed" | "queued" | "completed" | "cancelled" | "pending";
type TabId = "new-batch" | "batches" | "config";

// Helper to map backend status to UI status
function mapStatus(status: PipelineBatchStatus): BatchStatus {
  const mapping: Record<PipelineBatchStatus, BatchStatus> = {
    pending: "queued",
    running: "running",
    completed: "success",
    failed: "failed",
    cancelled: "failed",
  };
  return mapping[status] || "failed";
}

// Helper to format relative time
function formatRelativeTime(isoTime?: string): string {
  if (!isoTime) return "-";
  try {
    const date = new Date(isoTime);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSecs = Math.floor(diffMs / 1000);
    const diffMins = Math.floor(diffSecs / 60);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) return `${diffDays}d ago`;
    if (diffHours > 0) return `${diffHours}h ago`;
    if (diffMins > 0) return `${diffMins}m ago`;
    return "just now";
  } catch {
    return "-";
  }
}

// Helper to format duration
function formatDuration(seconds?: number): string {
  if (!seconds) return "-";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins > 0) return `${mins}m ${secs}s`;
  return `${secs}s`;
}

// Default stages for new runs
const DEFAULT_STAGES: Stage[] = ["ingest", "classify", "extract"];

// Status badge component
function StatusBadge({ status }: { status: BatchStatus }) {
  const styles: Record<BatchStatus, string> = {
    running: "bg-info/10 text-info",
    queued: "bg-warning/10 text-warning-foreground",
    pending: "bg-warning/10 text-warning-foreground",
    success: "bg-success/10 text-success",
    completed: "bg-success/10 text-success",
    partial: "bg-accent/10 text-accent-foreground",
    failed: "bg-destructive/10 text-destructive",
    cancelled: "bg-destructive/10 text-destructive",
  };
  const labels: Record<BatchStatus, string> = {
    running: "RUNNING",
    queued: "QUEUED",
    pending: "QUEUED",
    success: "SUCCESS",
    completed: "SUCCESS",
    partial: "PARTIAL",
    failed: "FAILED",
    cancelled: "CANCELLED",
  };
  return (
    <span className={cn("px-2 py-0.5 rounded-full text-[10px] font-medium", styles[status])}>
      {labels[status]}
    </span>
  );
}

// Progress bar component
function ProgressBar({ value, className }: { value: number; className?: string }) {
  return (
    <div className={cn("h-1.5 bg-muted rounded-full overflow-hidden", className)}>
      <div
        className={cn(
          "h-full rounded-full transition-all",
          value === 100 ? "bg-success" : value > 0 ? "bg-info" : "bg-muted-foreground/30"
        )}
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

// UI-specific batch type (derived from EnhancedPipelineRun)
interface UIBatch {
  batch_id: string;
  friendly_name: string;
  status: BatchStatus;
  prompt_config: string;
  claims_count: number;
  docs_total: number;
  docs_processed: number;
  started_at: string;
  completed_at?: string;
  duration?: string;
  stage_progress: { ingest: number; classify: number; extract: number };
  cost_estimate?: string;
  errors: Array<{ doc: string; stage: string; message: string }>;
  claims: string[];
  timings: { ingest: string; classify: string; extract: string };
  reuse: { ingestion: number; classification: number };
}

// New Batch Tab
function NewBatchTab({
  claims,
  selectedClaims,
  onToggleClaim,
  stages,
  onToggleStage,
  onApplyPreset,
  promptConfig,
  promptConfigs,
  onPromptConfigChange,
  forceOverwrite,
  onForceOverwriteChange,
  computeMetrics,
  onComputeMetricsChange,
  dryRun,
  onDryRunChange,
  activeBatches,
  onStartBatch,
  isStartingBatch,
  isLoading,
  canExecute,
}: {
  claims: PipelineClaimOption[];
  selectedClaims: string[];
  onToggleClaim: (id: string) => void;
  stages: Stage[];
  onToggleStage: (stage: Stage) => void;
  onApplyPreset: (preset: "full" | "classify_extract" | "extract_only") => void;
  promptConfig: string;
  promptConfigs: PromptConfig[];
  onPromptConfigChange: (id: string) => void;
  forceOverwrite: boolean;
  onForceOverwriteChange: (v: boolean) => void;
  computeMetrics: boolean;
  onComputeMetricsChange: (v: boolean) => void;
  dryRun: boolean;
  onDryRunChange: (v: boolean) => void;
  activeBatches: UIBatch[];
  onStartBatch: () => void;
  isStartingBatch: boolean;
  isLoading: boolean;
  canExecute: boolean;
}) {
  const [search, setSearch] = useState("");

  const filteredClaims = useMemo(() => {
    if (!search.trim()) return claims;
    const q = search.toLowerCase();
    return claims.filter((c) => c.claim_id.toLowerCase().includes(q));
  }, [claims, search]);

  const selectedDocCount = selectedClaims
    .map((id) => claims.find((c) => c.claim_id === id)?.doc_count || 0)
    .reduce((sum, count) => sum + count, 0);

  const unprocessedClaims = claims.filter((c) => !c.last_run);
  const canStartRun = selectedClaims.length > 0 && stages.length > 0 && canExecute;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Claims Selection */}
      <div className="bg-card border rounded-xl p-5">
        <h3 className="text-sm font-medium text-foreground mb-3">Select Claims</h3>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search claims..."
          className="w-full px-3 py-2 text-sm border rounded-lg bg-background mb-3"
        />
        <div className="max-h-52 overflow-auto border rounded-lg divide-y">
          {isLoading ? (
            <div className="px-3 py-4 text-sm text-muted-foreground text-center">Loading claims...</div>
          ) : filteredClaims.length === 0 ? (
            <div className="px-3 py-4 text-sm text-muted-foreground text-center">No claims match</div>
          ) : (
            filteredClaims.map((claim) => (
              <label
                key={claim.claim_id}
                className="flex items-center justify-between px-3 py-2.5 hover:bg-muted/50 cursor-pointer"
              >
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    checked={selectedClaims.includes(claim.claim_id)}
                    onChange={() => onToggleClaim(claim.claim_id)}
                    className="rounded border-input"
                  />
                  <span className="text-sm font-medium text-foreground">{claim.claim_id}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>{claim.doc_count} docs</span>
                  <span className={cn(claim.last_run ? "text-muted-foreground" : "text-warning-foreground")}>
                    {claim.last_run ? `last: ${claim.last_run}` : "never processed"}
                  </span>
                </div>
              </label>
            ))
          )}
        </div>
        <div className="flex items-center justify-between mt-3 text-xs">
          <span className="text-muted-foreground">
            Selected: {selectedClaims.length} claims · {selectedDocCount} docs
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => claims.forEach((c) => !selectedClaims.includes(c.claim_id) && onToggleClaim(c.claim_id))}
              className="text-info hover:underline"
            >
              Select all
            </button>
            <button
              onClick={() => unprocessedClaims.forEach((c) => !selectedClaims.includes(c.claim_id) && onToggleClaim(c.claim_id))}
              className="text-info hover:underline"
            >
              Select unprocessed
            </button>
            <button
              onClick={() => selectedClaims.forEach((id) => onToggleClaim(id))}
              className="text-muted-foreground hover:underline"
            >
              Clear
            </button>
          </div>
        </div>
      </div>

      {/* Stages */}
      <div className="bg-card border rounded-xl p-5">
        <h3 className="text-sm font-medium text-foreground mb-3">Stages</h3>
        <div className="flex flex-wrap gap-2">
          {(["ingest", "classify", "extract"] as Stage[]).map((stage) => (
            <button
              key={stage}
              onClick={() => onToggleStage(stage)}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium transition-colors",
                stages.includes(stage)
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              )}
            >
              {stage}
            </button>
          ))}
        </div>
        <div className="flex gap-3 mt-3 text-xs">
          <span className="text-muted-foreground/70">Presets:</span>
          <button onClick={() => onApplyPreset("full")} className="text-info hover:underline">
            Full
          </button>
          <button onClick={() => onApplyPreset("classify_extract")} className="text-info hover:underline">
            Classify + Extract
          </button>
          <button onClick={() => onApplyPreset("extract_only")} className="text-info hover:underline">
            Extract Only
          </button>
        </div>
        {stages.includes("extract") && !stages.includes("classify") && (
          <div className="mt-3 text-xs text-warning-foreground bg-warning/10 px-3 py-2 rounded-lg">
            Extract-only runs require existing classification outputs.
          </div>
        )}
      </div>

      {/* Prompt Config */}
      <div className="bg-card border rounded-xl p-5">
        <h3 className="text-sm font-medium text-foreground mb-3">Prompt Config</h3>
        <select
          value={promptConfig}
          onChange={(e) => onPromptConfigChange(e.target.value)}
          className="w-full px-3 py-2 text-sm border rounded-lg bg-background"
        >
          {promptConfigs.map((cfg) => (
            <option key={cfg.id} value={cfg.id}>
              {cfg.name} ({cfg.model}){cfg.is_default ? " - default" : ""}
            </option>
          ))}
        </select>
        <button className="mt-2 text-xs text-info hover:underline">View prompt details</button>
      </div>

      {/* Options */}
      <div className="bg-card border rounded-xl p-5">
        <h3 className="text-sm font-medium text-foreground mb-3">Options</h3>
        <div className="flex flex-wrap gap-6">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={forceOverwrite}
              onChange={(e) => onForceOverwriteChange(e.target.checked)}
              className="rounded border-input"
            />
            <span className="text-foreground">Force overwrite</span>
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={computeMetrics}
              onChange={(e) => onComputeMetricsChange(e.target.checked)}
              className="rounded border-input"
            />
            <span className="text-foreground">Compute metrics</span>
          </label>
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={dryRun}
              onChange={(e) => onDryRunChange(e.target.checked)}
              className="rounded border-input"
            />
            <span className="text-foreground">Dry run</span>
          </label>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        <button
          onClick={onStartBatch}
          className={cn(
            "flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
            canStartRun && !isStartingBatch
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-muted text-muted-foreground cursor-not-allowed"
          )}
          disabled={!canStartRun || isStartingBatch}
          title={!canExecute ? "You don't have permission to run pipelines" : undefined}
        >
          {isStartingBatch ? "Starting..." : "Start Batch"}
        </button>
        <button className="px-4 py-3 rounded-lg border text-sm font-medium text-foreground hover:bg-muted/50">
          Preview
        </button>
      </div>

      {/* Active Batches */}
      {activeBatches.length > 0 && (
        <div className="bg-info/5 border border-info/20 rounded-xl p-4">
          <h3 className="text-sm font-medium text-info mb-3">
            Active Batches ({activeBatches.length})
          </h3>
          <div className="space-y-2">
            {activeBatches.map((batch) => (
              <div
                key={batch.batch_id}
                className="flex items-center justify-between bg-card rounded-lg px-3 py-2 border"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-foreground">{batch.friendly_name}</span>
                  <StatusBadge status={batch.status} />
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-24">
                    <ProgressBar
                      value={
                        (batch.stage_progress.ingest + batch.stage_progress.classify + batch.stage_progress.extract) / 3
                      }
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {Math.round(
                      (batch.stage_progress.ingest + batch.stage_progress.classify + batch.stage_progress.extract) / 3
                    )}%
                  </span>
                  <button className="text-xs text-info hover:underline">View</button>
                  {batch.status === "queued" && (
                    <button className="text-xs text-destructive hover:underline">Cancel</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Chevron Icon component
function ChevronIcon({ expanded, className }: { expanded: boolean; className?: string }) {
  return (
    <svg
      className={cn(
        "w-4 h-4 transition-transform duration-200",
        expanded && "rotate-90",
        className
      )}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
    </svg>
  );
}

// Batches Tab
function BatchesTab({
  batches,
  onSelectBatch,
  selectedBatchId,
  onCancelBatch,
  onDeleteBatch,
  onViewDocuments,
  onExportSummary,
  isLoading,
}: {
  batches: UIBatch[];
  onSelectBatch: (id: string | null) => void;
  selectedBatchId: string | null;
  onCancelBatch: (batchId: string) => void;
  onDeleteBatch: (batchId: string) => void;
  onViewDocuments: (batchId: string) => void;
  onExportSummary: (batch: UIBatch) => void;
  isLoading: boolean;
}) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [timeFilter, setTimeFilter] = useState("7d");
  const [needsAttention, setNeedsAttention] = useState(false);

  const filteredBatches = useMemo(() => {
    let result = batches;
    if (statusFilter !== "all") {
      result = result.filter((b) => b.status === statusFilter);
    }
    if (needsAttention) {
      result = result.filter((b) => b.status === "failed" || b.status === "partial");
    }
    return result;
  }, [batches, statusFilter, needsAttention]);

  const selectedBatch = batches.find((b) => b.batch_id === selectedBatchId);

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="bg-card border rounded-xl p-4 flex flex-wrap items-center gap-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border rounded-lg bg-background"
        >
          <option value="all">All statuses</option>
          <option value="running">Running</option>
          <option value="queued">Queued</option>
          <option value="success">Success</option>
          <option value="partial">Partial</option>
          <option value="failed">Failed</option>
        </select>
        <select
          value={timeFilter}
          onChange={(e) => setTimeFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border rounded-lg bg-background"
        >
          <option value="24h">Last 24 hours</option>
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
          <option value="all">All time</option>
        </select>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={needsAttention}
            onChange={(e) => setNeedsAttention(e.target.checked)}
            className="rounded border-input"
          />
          <span className="text-foreground">Needs attention only</span>
        </label>
        <button
          onClick={() => {
            setStatusFilter("all");
            setTimeFilter("7d");
            setNeedsAttention(false);
          }}
          className="text-sm text-muted-foreground hover:underline ml-auto"
        >
          Clear filters
        </button>
      </div>

      {/* Batches Table */}
      <div className="bg-card border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground text-xs">
            <tr>
              <th className="w-8 px-2"></th>
              <th className="text-left px-4 py-3 font-medium">Batch</th>
              <th className="text-left px-4 py-3 font-medium">Status</th>
              <th className="text-left px-4 py-3 font-medium">Scope</th>
              <th className="text-left px-4 py-3 font-medium">Started</th>
              <th className="text-left px-4 py-3 font-medium">Duration</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  Loading batches...
                </td>
              </tr>
            ) : filteredBatches.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  No batches match the current filters
                </td>
              </tr>
            ) : (
              filteredBatches.map((batch) => {
                const isSelected = selectedBatchId === batch.batch_id;
                const isRunning = batch.status === "running" || batch.status === "queued";
                return (
                  <Fragment key={batch.batch_id}>
                    <tr
                      onClick={() => onSelectBatch(isSelected ? null : batch.batch_id)}
                      className={cn(
                        "border-t cursor-pointer transition-colors group",
                        isSelected ? "bg-accent/5" : "hover:bg-muted/30"
                      )}
                    >
                      <td className="px-2 py-3">
                        <ChevronIcon
                          expanded={isSelected}
                          className="text-muted-foreground group-hover:text-foreground"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-foreground">{batch.friendly_name}</div>
                        <div className="text-xs text-muted-foreground font-mono mt-0.5">{batch.batch_id}</div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={batch.status} />
                        {batch.errors.length > 0 && (
                          <span className="text-xs text-destructive ml-2">
                            {batch.errors.length} error{batch.errors.length > 1 ? "s" : ""}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-foreground">
                        {batch.claims_count} claim{batch.claims_count !== 1 ? "s" : ""}, {batch.docs_total} doc{batch.docs_total !== 1 ? "s" : ""}
                        {isRunning && batch.docs_processed > 0 && (
                          <span className="text-info text-xs ml-1">({batch.docs_processed} done)</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{batch.started_at}</td>
                      <td className="px-4 py-3 text-muted-foreground">{batch.duration || "—"}</td>
                    </tr>
                    {isSelected && selectedBatch && (
                      <tr className="border-t">
                        <td colSpan={6} className="p-0">
                          <div className="bg-muted/40 border-l-4 border-primary/30 px-6 py-4">
                            <BatchDetailsPanel
                              batch={selectedBatch}
                              onDeleteBatch={onDeleteBatch}
                              onCancelBatch={onCancelBatch}
                              onViewDocuments={onViewDocuments}
                              onExportSummary={onExportSummary}
                            />
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Batch Details Panel
function BatchDetailsPanel({
  batch,
  onDeleteBatch,
  onCancelBatch,
  onViewDocuments,
  onExportSummary,
}: {
  batch: UIBatch;
  onDeleteBatch: (batchId: string) => void;
  onCancelBatch: (batchId: string) => void;
  onViewDocuments: (batchId: string) => void;
  onExportSummary: (batch: UIBatch) => void;
}) {
  const [showAllClaims, setShowAllClaims] = useState(false);
  const isRunning = batch.status === "running" || batch.status === "queued";
  const maxClaimsToShow = 8;
  const hasMoreClaims = batch.claims.length > maxClaimsToShow;
  const displayedClaims = showAllClaims ? batch.claims : batch.claims.slice(0, maxClaimsToShow);

  // Check if we have actual timing data (not just dashes)
  const hasTimingData = batch.timings.ingest || batch.timings.classify || batch.timings.extract;
  const hasReuseData = batch.reuse.ingestion > 0 || batch.reuse.classification > 0;

  return (
    <div className="space-y-4">
      {/* Compact Stats Row - Model + Claims inline */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Model:</span>
          <span className="text-sm font-medium text-foreground">{batch.prompt_config}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Claims:</span>
          <div className="flex flex-wrap items-center gap-1">
            {displayedClaims.map((claim) => (
              <span
                key={claim}
                className="px-2 py-0.5 bg-muted/80 text-xs text-foreground rounded font-mono"
                title={claim}
              >
                {claim.length > 20 ? `${claim.slice(0, 20)}...` : claim}
              </span>
            ))}
            {hasMoreClaims && !showAllClaims && (
              <button
                onClick={() => setShowAllClaims(true)}
                className="px-2 py-0.5 text-xs text-info hover:underline"
              >
                +{batch.claims.length - maxClaimsToShow} more
              </button>
            )}
            {hasMoreClaims && showAllClaims && (
              <button
                onClick={() => setShowAllClaims(false)}
                className="px-2 py-0.5 text-xs text-muted-foreground hover:underline"
              >
                Show less
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Progress bars for running batches */}
      {isRunning && (
        <div className="bg-card border rounded-lg p-4">
          <h4 className="text-xs font-medium text-muted-foreground mb-3">Progress</h4>
          <div className="space-y-3">
            {(["ingest", "classify", "extract"] as const).map((stage) => {
              const progress = batch.stage_progress[stage];
              return (
                <div key={stage} className="flex items-center gap-4">
                  <span className="w-16 text-xs text-muted-foreground capitalize">{stage}</span>
                  <div className="flex-1">
                    <ProgressBar value={progress} />
                  </div>
                  <span className="w-12 text-xs text-muted-foreground text-right">
                    {progress}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Stage Timings - only show if we have actual data */}
      {!isRunning && (hasTimingData || hasReuseData) && (
        <div className="flex items-center gap-6 text-sm">
          <span className="text-xs text-muted-foreground">Stage timings:</span>
          {(["ingest", "classify", "extract"] as const).map((stage) => {
            const timing = batch.timings[stage];
            const reuse = stage === "ingest" ? batch.reuse.ingestion : stage === "classify" ? batch.reuse.classification : 0;
            if (!timing && reuse === 0) return null;
            return (
              <div key={stage} className="flex items-center gap-1.5">
                <span className="text-xs text-muted-foreground capitalize">{stage}:</span>
                {timing && <span className="text-xs font-medium text-foreground">{timing}</span>}
                {reuse > 0 && (
                  <span className="text-xs text-info">({reuse} reused)</span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Errors */}
      {batch.errors.length > 0 && (
        <div className="bg-destructive/5 border border-destructive/20 rounded-lg p-3">
          <h4 className="text-xs font-medium text-destructive mb-2">
            Errors ({batch.errors.length})
          </h4>
          <ul className="space-y-1 max-h-24 overflow-auto">
            {batch.errors.map((err, idx) => (
              <li key={idx} className="text-xs text-destructive">
                <span className="font-medium">{err.doc}</span>
                <span className="text-destructive/60 mx-1">·</span>
                <span className="text-destructive/80">{err.stage}</span>
                <span className="text-destructive/60 mx-1">·</span>
                <span>{err.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Actions - consolidated here only */}
      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-border/50">
        <button
          onClick={() => onViewDocuments(batch.batch_id)}
          className="px-3 py-1.5 bg-primary text-primary-foreground text-xs font-medium rounded-lg hover:bg-primary/90 transition-colors"
        >
          View Documents
        </button>
        {(batch.status === "failed" || batch.status === "partial") && (
          <button className="px-3 py-1.5 bg-warning/10 text-warning-foreground text-xs font-medium rounded-lg hover:bg-warning/20 transition-colors">
            Retry Failed
          </button>
        )}
        {isRunning && (
          <button
            onClick={() => onCancelBatch(batch.batch_id)}
            className="px-3 py-1.5 bg-warning/10 text-warning-foreground text-xs font-medium rounded-lg hover:bg-warning/20 transition-colors"
          >
            Cancel
          </button>
        )}
        <button
          onClick={() => onExportSummary(batch)}
          className="px-3 py-1.5 border text-xs font-medium rounded-lg text-muted-foreground hover:bg-muted/50 transition-colors"
        >
          Export Summary
        </button>
        <button
          onClick={() => onDeleteBatch(batch.batch_id)}
          className="px-3 py-1.5 border text-xs font-medium rounded-lg text-destructive hover:bg-destructive/10 transition-colors"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

// Config Tab
function ConfigTab({
  configs,
  auditEntries,
  isLoading,
  onRefreshConfigs,
  onRefreshAudit,
  onSetDefault,
}: {
  configs: PromptConfig[];
  auditEntries: AuditEntry[];
  isLoading: boolean;
  onRefreshConfigs: () => void;
  onRefreshAudit: () => void;
  onSetDefault: (id: string) => void;
}) {
  const [auditFilter, setAuditFilter] = useState<"all" | "runs" | "configs">("all");

  // Filter audit entries based on selection
  const filteredAuditEntries = useMemo(() => {
    if (auditFilter === "all") return auditEntries;
    return auditEntries.filter((entry) => {
      const action = entry.action?.toLowerCase() || "";
      if (auditFilter === "runs") {
        return action.includes("run") || action.includes("batch") || action.includes("pipeline");
      }
      if (auditFilter === "configs") {
        return action.includes("config") || action.includes("prompt");
      }
      return true;
    });
  }, [auditEntries, auditFilter]);

  // Format audit timestamp for display
  const formatAuditTime = (isoTime: string): string => {
    try {
      const date = new Date(isoTime);
      return date.toLocaleString("en-US", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoTime;
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Prompt Configs */}
      <div className="bg-card border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-foreground">Prompt Configs</h3>
          <button
            onClick={onRefreshConfigs}
            className="text-xs text-muted-foreground hover:underline"
          >
            Refresh
          </button>
        </div>
        {isLoading ? (
          <div className="text-sm text-muted-foreground text-center py-4">Loading...</div>
        ) : configs.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-4">No configs found</div>
        ) : (
          <div className="space-y-3">
            {configs.map((cfg) => (
              <div
                key={cfg.id}
                className={cn(
                  "border rounded-lg p-4",
                  cfg.is_default && "border-info/30 bg-info/5"
                )}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="text-sm font-medium text-foreground">
                      {cfg.name}
                      {cfg.is_default && (
                        <span className="ml-2 text-xs text-info bg-info/10 px-2 py-0.5 rounded-full">
                          default
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      Model: {cfg.model} · Temp: {cfg.temperature} · Max tokens: {cfg.max_tokens}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <button className="text-xs text-info hover:underline">View</button>
                    <button className="text-xs text-muted-foreground hover:underline">Edit</button>
                    {!cfg.is_default && (
                      <button
                        onClick={() => onSetDefault(cfg.id)}
                        className="text-xs text-muted-foreground hover:underline"
                      >
                        Set as default
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        <button className="mt-4 text-sm text-info hover:underline">+ Add new config</button>
      </div>

      {/* Audit Log */}
      <div className="bg-card border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-foreground">Audit Log</h3>
          <div className="flex gap-2">
            <select
              value={auditFilter}
              onChange={(e) => setAuditFilter(e.target.value as "all" | "runs" | "configs")}
              className="px-2 py-1 text-xs border rounded-lg bg-background"
            >
              <option value="all">All actions</option>
              <option value="runs">Runs</option>
              <option value="configs">Configs</option>
            </select>
            <button
              onClick={onRefreshAudit}
              className="text-xs text-muted-foreground hover:underline"
            >
              Refresh
            </button>
          </div>
        </div>
        {filteredAuditEntries.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-4">No audit entries</div>
        ) : (
          <div className="space-y-2">
            {filteredAuditEntries.map((entry, idx) => (
              <div key={idx} className="text-xs text-muted-foreground flex gap-2">
                <span className="text-muted-foreground/70 w-28 flex-shrink-0">
                  {formatAuditTime(entry.timestamp)}
                </span>
                <span className="text-muted-foreground/70 w-16 flex-shrink-0">{entry.user}</span>
                <span className="text-foreground">{entry.action}</span>
              </div>
            ))}
          </div>
        )}
        <button className="mt-4 text-xs text-info hover:underline">View full audit log</button>
      </div>
    </div>
  );
}

// Main Component
export function PipelineControlCenter() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabId>("batches");
  const [selectedClaims, setSelectedClaims] = useState<string[]>([]);
  const [stages, setStages] = useState<Stage[]>(DEFAULT_STAGES);
  const [promptConfig, setPromptConfig] = useState<string>("");
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [computeMetrics, setComputeMetrics] = useState(true);
  const [dryRun, setDryRun] = useState(false);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [isStartingBatch, setIsStartingBatch] = useState(false);
  const [batchToDelete, setBatchToDelete] = useState<string | null>(null);

  // Permission check
  const { canEdit } = useAuth();
  const canExecutePipeline = canEdit("pipeline");

  // Batch context - for syncing with Batches screen
  const { refreshRuns: refreshBatchContext } = useBatch();

  // Data hooks
  const { claims, isLoading: claimsLoading, refetch: refetchClaims } = usePipelineClaims();
  const { runs: batches, isLoading: batchesLoading, refetch: refetchBatches } = usePipelineRuns();
  const { configs, isLoading: configsLoading, refetch: refetchConfigs, setDefault: setDefaultConfig } = usePromptConfigs();
  const { entries: auditEntries, isLoading: auditLoading, refetch: refetchAudit } = useAuditLog({ limit: 50 });

  // Set default prompt config when configs load
  useMemo(() => {
    if (configs.length > 0 && !promptConfig) {
      const defaultConfig = configs.find((c) => c.is_default) || configs[0];
      setPromptConfig(defaultConfig.id);
    }
  }, [configs, promptConfig]);

  // Transform batches to UI format
  const transformedBatches: UIBatch[] = useMemo(() => {
    return batches.map((batch) => ({
      batch_id: batch.run_id,
      friendly_name: batch.friendly_name,
      status: mapStatus(batch.status) as BatchStatus,
      prompt_config: batch.prompt_config || batch.model,
      claims_count: batch.claims_count,
      docs_total: batch.docs_total,
      docs_processed: batch.docs_processed,
      started_at: formatRelativeTime(batch.started_at),
      completed_at: batch.completed_at ? formatRelativeTime(batch.completed_at) : undefined,
      duration: formatDuration(batch.duration_seconds),
      stage_progress: batch.stage_progress,
      cost_estimate: batch.cost_estimate_usd ? `$${batch.cost_estimate_usd.toFixed(2)}` : undefined,
      errors: batch.errors,
      claims: batch.claim_ids.map((id) => id),
      timings: batch.stage_timings as { ingest: string; classify: string; extract: string },
      reuse: batch.reuse as { ingestion: number; classification: number },
    }));
  }, [batches]);

  const activeBatches = useMemo(
    () => transformedBatches.filter((b) => b.status === "running" || b.status === "queued"),
    [transformedBatches]
  );

  // Handlers
  const handleStartBatch = useCallback(async () => {
    if (selectedClaims.length === 0) return;

    setIsStartingBatch(true);
    try {
      const selectedConfig = configs.find((c) => c.id === promptConfig);
      await startPipelineEnhanced({
        claim_ids: selectedClaims,
        model: selectedConfig?.model || "gpt-4o",
        stages,
        prompt_config_id: promptConfig,
        force_overwrite: forceOverwrite,
        compute_metrics: computeMetrics,
        dry_run: dryRun,
      });
      // Refresh data and clear selection
      await Promise.all([refetchBatches(), refetchClaims(), refetchAudit()]);
      setSelectedClaims([]);
    } catch (error) {
      console.error("Failed to start batch:", error);
    } finally {
      setIsStartingBatch(false);
    }
  }, [selectedClaims, stages, promptConfig, forceOverwrite, computeMetrics, dryRun, configs, refetchBatches, refetchClaims, refetchAudit]);

  const handleCancelBatch = useCallback(async (batchId: string) => {
    try {
      await cancelPipeline(batchId);
      await Promise.all([refetchBatches(), refetchAudit()]);
    } catch (error) {
      console.error("Failed to cancel batch:", error);
    }
  }, [refetchBatches, refetchAudit]);

  const handleDeleteBatch = useCallback((batchId: string) => {
    setBatchToDelete(batchId);
  }, []);

  const confirmDeleteBatch = useCallback(async () => {
    if (!batchToDelete) return;
    try {
      await deletePipelineRun(batchToDelete);
      // Refresh both Pipeline Control Center and Batches screen
      await Promise.all([refetchBatches(), refetchAudit(), refreshBatchContext()]);
      if (selectedBatchId === batchToDelete) {
        setSelectedBatchId(null);
      }
    } catch (error) {
      console.error("Failed to delete batch:", error);
    } finally {
      setBatchToDelete(null);
    }
  }, [batchToDelete, refetchBatches, refetchAudit, refreshBatchContext, selectedBatchId]);

  const handleSetDefault = useCallback(async (configId: string) => {
    try {
      await setDefaultConfig(configId);
      await refetchAudit();
    } catch (error) {
      console.error("Failed to set default config:", error);
    }
  }, [setDefaultConfig, refetchAudit]);

  const handleViewDocuments = useCallback((batchId: string) => {
    navigate(`/batches?run_id=${encodeURIComponent(batchId)}`);
  }, [navigate]);

  const handleExportSummary = useCallback((batch: UIBatch) => {
    // Create export data
    const exportData = {
      batch_id: batch.batch_id,
      friendly_name: batch.friendly_name,
      status: batch.status,
      prompt_config: batch.prompt_config,
      claims_count: batch.claims_count,
      docs_total: batch.docs_total,
      docs_processed: batch.docs_processed,
      started_at: batch.started_at,
      completed_at: batch.completed_at,
      duration: batch.duration,
      claims: batch.claims,
      timings: batch.timings,
      reuse: batch.reuse,
      cost_estimate: batch.cost_estimate,
      errors: batch.errors,
      exported_at: new Date().toISOString(),
    };

    // Create download
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${batch.friendly_name || batch.batch_id}-summary.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, []);

  function toggleClaim(claimId: string) {
    setSelectedClaims((prev) =>
      prev.includes(claimId) ? prev.filter((id) => id !== claimId) : [...prev, claimId]
    );
  }

  function toggleStage(stage: Stage) {
    setStages((prev) => (prev.includes(stage) ? prev.filter((s) => s !== stage) : [...prev, stage]));
  }

  function applyPreset(preset: "full" | "classify_extract" | "extract_only") {
    if (preset === "full") setStages(["ingest", "classify", "extract"]);
    if (preset === "classify_extract") setStages(["classify", "extract"]);
    if (preset === "extract_only") setStages(["extract"]);
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: "new-batch", label: "New Batch" },
    { id: "batches", label: "Batches" },
    { id: "config", label: "Config" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Tabs */}
      <div className="border-b bg-card px-6">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                activeTab === tab.id
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              {tab.label}
              {tab.id === "batches" && activeBatches.length > 0 && (
                <span className="ml-2 px-1.5 py-0.5 text-xs bg-info/10 text-info rounded-full">
                  {activeBatches.length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto bg-background p-6">
        {activeTab === "new-batch" && (
          <NewBatchTab
            claims={claims}
            selectedClaims={selectedClaims}
            onToggleClaim={toggleClaim}
            stages={stages}
            onToggleStage={toggleStage}
            onApplyPreset={applyPreset}
            promptConfig={promptConfig}
            promptConfigs={configs}
            onPromptConfigChange={setPromptConfig}
            forceOverwrite={forceOverwrite}
            onForceOverwriteChange={setForceOverwrite}
            computeMetrics={computeMetrics}
            onComputeMetricsChange={setComputeMetrics}
            dryRun={dryRun}
            onDryRunChange={setDryRun}
            activeBatches={activeBatches}
            onStartBatch={handleStartBatch}
            isStartingBatch={isStartingBatch}
            isLoading={claimsLoading || configsLoading}
            canExecute={canExecutePipeline}
          />
        )}
        {activeTab === "batches" && (
          <BatchesTab
            batches={transformedBatches}
            onSelectBatch={setSelectedBatchId}
            selectedBatchId={selectedBatchId}
            onCancelBatch={handleCancelBatch}
            onDeleteBatch={handleDeleteBatch}
            onViewDocuments={handleViewDocuments}
            onExportSummary={handleExportSummary}
            isLoading={batchesLoading}
          />
        )}
        {activeTab === "config" && (
          <ConfigTab
            configs={configs}
            auditEntries={auditEntries}
            isLoading={configsLoading || auditLoading}
            onRefreshConfigs={refetchConfigs}
            onRefreshAudit={refetchAudit}
            onSetDefault={handleSetDefault}
          />
        )}
      </div>

      {/* Delete Confirmation Modal */}
      {batchToDelete && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg p-6 max-w-md mx-4 shadow-lg border border-border">
            <h3 className="text-lg font-semibold mb-2">Delete Batch?</h3>
            <p className="text-muted-foreground mb-4">
              This will permanently delete the batch, its extraction results, and all
              claims created in this batch. Labels you've added will be preserved.
              This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setBatchToDelete(null)}
                className="px-4 py-2 border border-border rounded-lg hover:bg-muted/50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDeleteBatch}
                className="px-4 py-2 bg-destructive text-white rounded-lg hover:bg-destructive/90"
              >
                Delete Batch
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
