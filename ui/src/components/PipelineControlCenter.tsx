import { Fragment, useMemo, useState, useCallback } from "react";
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
import type {
  PipelineClaimOption,
  PromptConfig,
  AuditEntry,
  PipelineBatchStatus,
} from "../types";

// Types
type Stage = "ingest" | "classify" | "extract";
type RunStatus = "running" | "success" | "partial" | "failed" | "queued" | "completed" | "cancelled" | "pending";
type TabId = "new-run" | "runs" | "config";

// Helper to map backend status to UI status
function mapStatus(status: PipelineBatchStatus): RunStatus {
  const mapping: Record<PipelineBatchStatus, RunStatus> = {
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
function StatusBadge({ status }: { status: RunStatus }) {
  const styles: Record<RunStatus, string> = {
    running: "bg-info/10 text-info",
    queued: "bg-warning/10 text-warning-foreground",
    pending: "bg-warning/10 text-warning-foreground",
    success: "bg-success/10 text-success",
    completed: "bg-success/10 text-success",
    partial: "bg-accent/10 text-accent-foreground",
    failed: "bg-destructive/10 text-destructive",
    cancelled: "bg-destructive/10 text-destructive",
  };
  const labels: Record<RunStatus, string> = {
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

// UI-specific run type (derived from EnhancedPipelineRun)
interface UIRun {
  run_id: string;
  friendly_name: string;
  status: RunStatus;
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

// New Run Tab
function NewRunTab({
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
  activeRuns,
  onStartRun,
  isStartingRun,
  isLoading,
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
  activeRuns: UIRun[];
  onStartRun: () => void;
  isStartingRun: boolean;
  isLoading: boolean;
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
  const canStartRun = selectedClaims.length > 0 && stages.length > 0;

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
          onClick={onStartRun}
          className={cn(
            "flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
            canStartRun && !isStartingRun
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-muted text-muted-foreground cursor-not-allowed"
          )}
          disabled={!canStartRun || isStartingRun}
        >
          {isStartingRun ? "Starting..." : "Start Run"}
        </button>
        <button className="px-4 py-3 rounded-lg border text-sm font-medium text-foreground hover:bg-muted/50">
          Preview
        </button>
      </div>

      {/* Active Runs */}
      {activeRuns.length > 0 && (
        <div className="bg-info/5 border border-info/20 rounded-xl p-4">
          <h3 className="text-sm font-medium text-info mb-3">
            Active Runs ({activeRuns.length})
          </h3>
          <div className="space-y-2">
            {activeRuns.map((run) => (
              <div
                key={run.run_id}
                className="flex items-center justify-between bg-card rounded-lg px-3 py-2 border"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-foreground">{run.friendly_name}</span>
                  <StatusBadge status={run.status} />
                </div>
                <div className="flex items-center gap-4">
                  <div className="w-24">
                    <ProgressBar
                      value={
                        (run.stage_progress.ingest + run.stage_progress.classify + run.stage_progress.extract) / 3
                      }
                    />
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {Math.round(
                      (run.stage_progress.ingest + run.stage_progress.classify + run.stage_progress.extract) / 3
                    )}%
                  </span>
                  <button className="text-xs text-info hover:underline">View</button>
                  {run.status === "queued" && (
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

// Runs Tab
function RunsTab({
  runs,
  onSelectRun,
  selectedRunId,
  onCancelRun,
  onDeleteRun,
  isLoading,
}: {
  runs: UIRun[];
  onSelectRun: (id: string | null) => void;
  selectedRunId: string | null;
  onCancelRun: (runId: string) => void;
  onDeleteRun: (runId: string) => void;
  isLoading: boolean;
}) {
  const [statusFilter, setStatusFilter] = useState("all");
  const [timeFilter, setTimeFilter] = useState("7d");
  const [needsAttention, setNeedsAttention] = useState(false);

  const filteredRuns = useMemo(() => {
    let result = runs;
    if (statusFilter !== "all") {
      result = result.filter((r) => r.status === statusFilter);
    }
    if (needsAttention) {
      result = result.filter((r) => r.status === "failed" || r.status === "partial");
    }
    return result;
  }, [runs, statusFilter, needsAttention]);

  const selectedRun = runs.find((r) => r.run_id === selectedRunId);

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

      {/* Runs Table */}
      <div className="bg-card border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-muted-foreground text-xs">
            <tr>
              <th className="text-left px-4 py-3 font-medium">Run</th>
              <th className="text-left px-4 py-3 font-medium">Status</th>
              <th className="text-left px-4 py-3 font-medium">Progress</th>
              <th className="text-left px-4 py-3 font-medium">Started</th>
              <th className="text-left px-4 py-3 font-medium">Cost</th>
              <th className="text-left px-4 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  Loading runs...
                </td>
              </tr>
            ) : filteredRuns.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  No runs match the current filters
                </td>
              </tr>
            ) : (
              filteredRuns.map((run) => {
                const isSelected = selectedRunId === run.run_id;
                const overallProgress = Math.round(
                  (run.stage_progress.ingest + run.stage_progress.classify + run.stage_progress.extract) / 3
                );
                return (
                  <Fragment key={run.run_id}>
                    <tr
                      onClick={() => onSelectRun(isSelected ? null : run.run_id)}
                      className={cn(
                        "border-t cursor-pointer transition-colors",
                        isSelected ? "bg-accent/10" : "hover:bg-muted/30"
                      )}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium text-foreground">{run.friendly_name}</div>
                        {run.errors.length > 0 && (
                          <div className="text-xs text-destructive mt-0.5">
                            {run.errors.length} doc{run.errors.length > 1 ? "s" : ""} failed · {run.errors[0].message}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={run.status} />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-20">
                            <ProgressBar value={overallProgress} />
                          </div>
                          <span className="text-xs text-muted-foreground">{overallProgress}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{run.started_at}</td>
                      <td className="px-4 py-3 text-muted-foreground">{run.cost_estimate || "—"}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <button className="text-info hover:underline">Open</button>
                          <button
                            onClick={(e) => { e.stopPropagation(); onDeleteRun(run.run_id); }}
                            className="text-destructive hover:underline"
                          >
                            Delete
                          </button>
                          {(run.status === "running" || run.status === "queued") && (
                            <button
                              onClick={(e) => { e.stopPropagation(); onCancelRun(run.run_id); }}
                              className="text-warning-foreground hover:underline"
                            >
                              Cancel
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {isSelected && selectedRun && (
                      <tr className="border-t bg-muted/20">
                        <td colSpan={6} className="px-4 py-4">
                          <RunDetailsPanel run={selectedRun} onDeleteRun={onDeleteRun} />
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

// Run Details Panel
function RunDetailsPanel({ run, onDeleteRun }: { run: UIRun; onDeleteRun: (runId: string) => void }) {
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm font-medium text-foreground">
            Run: {run.friendly_name}
            <span className="text-muted-foreground font-normal ml-2">· Started {run.started_at}</span>
            {run.duration && <span className="text-muted-foreground font-normal ml-2">· Duration: {run.duration}</span>}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Config: {run.prompt_config}
          </div>
          <div className="text-xs text-muted-foreground">
            Claims: {run.claims.join(", ")} · Total: {run.docs_total} docs
          </div>
        </div>
      </div>

      {/* Stage Breakdown */}
      <div className="bg-card border rounded-lg p-4">
        <h4 className="text-xs font-medium text-muted-foreground mb-3">Stage Breakdown</h4>
        <div className="space-y-3">
          {(["ingest", "classify", "extract"] as const).map((stage) => {
            const progress = run.stage_progress[stage];
            const timing = run.timings[stage];
            const reuse = stage === "ingest" ? run.reuse.ingestion : stage === "classify" ? run.reuse.classification : 0;
            return (
              <div key={stage} className="flex items-center gap-4">
                <span className="w-16 text-xs text-muted-foreground">{stage}</span>
                <div className="flex-1">
                  <ProgressBar value={progress} />
                </div>
                <span className="w-12 text-xs text-muted-foreground text-right">
                  {progress === 100 ? "done" : `${progress}%`}
                </span>
                <span className="w-16 text-xs text-muted-foreground/70 text-right">{timing}</span>
                {reuse > 0 && (
                  <span className="text-xs text-info">[reused: {reuse}]</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Errors */}
      {run.errors.length > 0 && (
        <div className="bg-destructive/5 border border-destructive/20 rounded-lg p-4">
          <h4 className="text-xs font-medium text-destructive mb-2">Errors ({run.errors.length})</h4>
          <ul className="space-y-1.5">
            {run.errors.map((err, idx) => (
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

      {/* Actions */}
      <div className="flex flex-wrap gap-2">
        <button className="px-3 py-1.5 bg-primary text-primary-foreground text-xs rounded-lg hover:bg-primary/90">
          View Documents
        </button>
        {(run.status === "failed" || run.status === "partial") && (
          <button className="px-3 py-1.5 bg-warning/10 text-warning-foreground text-xs rounded-lg hover:bg-warning/20">
            Retry Failed
          </button>
        )}
        <button className="px-3 py-1.5 border text-xs rounded-lg text-muted-foreground hover:bg-muted/50">
          Export
        </button>
        <button
          onClick={() => onDeleteRun(run.run_id)}
          className="px-3 py-1.5 border text-xs rounded-lg text-destructive hover:bg-destructive/10"
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
            <select className="px-2 py-1 text-xs border rounded-lg bg-background">
              <option>All actions</option>
              <option>Runs</option>
              <option>Configs</option>
            </select>
            <button
              onClick={onRefreshAudit}
              className="text-xs text-muted-foreground hover:underline"
            >
              Refresh
            </button>
          </div>
        </div>
        {auditEntries.length === 0 ? (
          <div className="text-sm text-muted-foreground text-center py-4">No audit entries</div>
        ) : (
          <div className="space-y-2">
            {auditEntries.map((entry, idx) => (
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
  const [activeTab, setActiveTab] = useState<TabId>("new-run");
  const [selectedClaims, setSelectedClaims] = useState<string[]>([]);
  const [stages, setStages] = useState<Stage[]>(DEFAULT_STAGES);
  const [promptConfig, setPromptConfig] = useState<string>("");
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [computeMetrics, setComputeMetrics] = useState(true);
  const [dryRun, setDryRun] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [isStartingRun, setIsStartingRun] = useState(false);

  // Data hooks
  const { claims, isLoading: claimsLoading, refetch: refetchClaims } = usePipelineClaims();
  const { runs, isLoading: runsLoading, refetch: refetchRuns } = usePipelineRuns();
  const { configs, isLoading: configsLoading, refetch: refetchConfigs, setDefault: setDefaultConfig } = usePromptConfigs();
  const { entries: auditEntries, isLoading: auditLoading, refetch: refetchAudit } = useAuditLog({ limit: 50 });

  // Set default prompt config when configs load
  useMemo(() => {
    if (configs.length > 0 && !promptConfig) {
      const defaultConfig = configs.find((c) => c.is_default) || configs[0];
      setPromptConfig(defaultConfig.id);
    }
  }, [configs, promptConfig]);

  // Transform runs to UI format
  const transformedRuns = useMemo(() => {
    return runs.map((run) => ({
      run_id: run.run_id,
      friendly_name: run.friendly_name,
      status: mapStatus(run.status) as RunStatus,
      prompt_config: run.prompt_config || run.model,
      claims_count: run.claims_count,
      docs_total: run.docs_total,
      docs_processed: run.docs_processed,
      started_at: formatRelativeTime(run.started_at),
      completed_at: run.completed_at ? formatRelativeTime(run.completed_at) : undefined,
      duration: formatDuration(run.duration_seconds),
      stage_progress: run.stage_progress,
      cost_estimate: run.cost_estimate_usd ? `$${run.cost_estimate_usd.toFixed(2)}` : undefined,
      errors: run.errors,
      claims: run.claim_ids.map((id) => id),
      timings: run.stage_timings as { ingest: string; classify: string; extract: string },
      reuse: run.reuse as { ingestion: number; classification: number },
    }));
  }, [runs]);

  const activeRuns = useMemo(
    () => transformedRuns.filter((r) => r.status === "running" || r.status === "queued"),
    [transformedRuns]
  );

  // Handlers
  const handleStartRun = useCallback(async () => {
    if (selectedClaims.length === 0) return;

    setIsStartingRun(true);
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
      await Promise.all([refetchRuns(), refetchClaims(), refetchAudit()]);
      setSelectedClaims([]);
    } catch (error) {
      console.error("Failed to start run:", error);
    } finally {
      setIsStartingRun(false);
    }
  }, [selectedClaims, stages, promptConfig, forceOverwrite, computeMetrics, dryRun, configs, refetchRuns, refetchClaims, refetchAudit]);

  const handleCancelRun = useCallback(async (runId: string) => {
    try {
      await cancelPipeline(runId);
      await Promise.all([refetchRuns(), refetchAudit()]);
    } catch (error) {
      console.error("Failed to cancel run:", error);
    }
  }, [refetchRuns, refetchAudit]);

  const handleDeleteRun = useCallback(async (runId: string) => {
    try {
      await deletePipelineRun(runId);
      await Promise.all([refetchRuns(), refetchAudit()]);
      if (selectedRunId === runId) {
        setSelectedRunId(null);
      }
    } catch (error) {
      console.error("Failed to delete run:", error);
    }
  }, [refetchRuns, refetchAudit, selectedRunId]);

  const handleSetDefault = useCallback(async (configId: string) => {
    try {
      await setDefaultConfig(configId);
      await refetchAudit();
    } catch (error) {
      console.error("Failed to set default config:", error);
    }
  }, [setDefaultConfig, refetchAudit]);

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
    { id: "new-run", label: "New Run" },
    { id: "runs", label: "Runs" },
    { id: "config", label: "Config" },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b bg-card px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-foreground">Pipeline Control Center</h1>
          <p className="text-sm text-muted-foreground">Admin operations console</p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-1 rounded-full bg-muted text-muted-foreground">env: local</span>
          <span className="px-2 py-1 rounded-full bg-destructive/10 text-destructive">admin</span>
        </div>
      </div>

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
              {tab.id === "runs" && activeRuns.length > 0 && (
                <span className="ml-2 px-1.5 py-0.5 text-xs bg-info/10 text-info rounded-full">
                  {activeRuns.length}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto bg-background p-6">
        {activeTab === "new-run" && (
          <NewRunTab
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
            activeRuns={activeRuns}
            onStartRun={handleStartRun}
            isStartingRun={isStartingRun}
            isLoading={claimsLoading || configsLoading}
          />
        )}
        {activeTab === "runs" && (
          <RunsTab
            runs={transformedRuns}
            onSelectRun={setSelectedRunId}
            selectedRunId={selectedRunId}
            onCancelRun={handleCancelRun}
            onDeleteRun={handleDeleteRun}
            isLoading={runsLoading}
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
    </div>
  );
}
