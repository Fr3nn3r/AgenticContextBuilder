import { useMemo, useState } from "react";
import { cn } from "../lib/utils";

// Types
type Stage = "ingest" | "classify" | "extract";
type RunStatus = "running" | "success" | "partial" | "failed" | "queued";
type TabId = "new-run" | "runs" | "config";

interface ClaimOption {
  claim_id: string;
  doc_count: number;
  last_run?: string;
}

interface RecentRun {
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
  last_log?: string;
  errors: Array<{ doc: string; stage: string; message: string }>;
  claims: string[];
  timings: { ingest: string; classify: string; extract: string };
  reuse: { ingestion: number; classification: number };
}

interface PromptConfig {
  id: string;
  name: string;
  model: string;
  temperature: number;
  max_tokens: number;
  is_default: boolean;
}

interface AuditEntry {
  timestamp: string;
  user: string;
  action: string;
}

// Mock Data
const CLAIM_OPTIONS: ClaimOption[] = [
  { claim_id: "claim_001", doc_count: 6, last_run: "2d ago" },
  { claim_id: "claim_002", doc_count: 3, last_run: undefined },
  { claim_id: "claim_003", doc_count: 9, last_run: "1h ago" },
  { claim_id: "claim_004", doc_count: 4, last_run: "5d ago" },
  { claim_id: "claim_005", doc_count: 2, last_run: undefined },
];

const PROMPT_CONFIGS: PromptConfig[] = [
  { id: "generic_v1", name: "generic_extraction_v1", model: "gpt-4o", temperature: 0.2, max_tokens: 4096, is_default: true },
  { id: "fast_v1", name: "fast_extraction_v1", model: "gpt-4o-mini", temperature: 0.1, max_tokens: 2048, is_default: false },
];

const RECENT_RUNS: RecentRun[] = [
  {
    run_id: "run_20260113_090000_abc123",
    friendly_name: "crisp-falcon-47",
    status: "failed",
    prompt_config: "generic_extraction_v1 (gpt-4o)",
    claims_count: 2,
    docs_total: 9,
    docs_processed: 7,
    started_at: "2h ago",
    completed_at: "2h ago",
    duration: "4m 12s",
    stage_progress: { ingest: 100, classify: 100, extract: 78 },
    cost_estimate: "$1.20",
    last_log: "extract: 7/9 docs processed",
    errors: [
      { doc: "doc_003.pdf", stage: "extraction", message: "Timeout after 30s" },
      { doc: "doc_007.pdf", stage: "extraction", message: "Missing policy_number" },
    ],
    claims: ["claim_001 (6 docs)", "claim_002 (3 docs)"],
    timings: { ingest: "1m 12s", classify: "38s", extract: "2m 22s" },
    reuse: { ingestion: 3, classification: 0 },
  },
  {
    run_id: "run_20260113_080000_def456",
    friendly_name: "amber-tiger-46",
    status: "success",
    prompt_config: "generic_extraction_v1 (gpt-4o)",
    claims_count: 3,
    docs_total: 15,
    docs_processed: 15,
    started_at: "5h ago",
    completed_at: "5h ago",
    duration: "6m 45s",
    stage_progress: { ingest: 100, classify: 100, extract: 100 },
    cost_estimate: "$2.34",
    last_log: "extract: 15/15 docs processed",
    errors: [],
    claims: ["claim_003 (9 docs)", "claim_004 (4 docs)", "claim_005 (2 docs)"],
    timings: { ingest: "2m 10s", classify: "1m 05s", extract: "3m 30s" },
    reuse: { ingestion: 0, classification: 0 },
  },
  {
    run_id: "run_20260113_095000_ghi789",
    friendly_name: "swift-eagle-48",
    status: "running",
    prompt_config: "generic_extraction_v1 (gpt-4o)",
    claims_count: 2,
    docs_total: 10,
    docs_processed: 6,
    started_at: "10m ago",
    stage_progress: { ingest: 100, classify: 80, extract: 20 },
    last_log: "classify: 8/10 docs processed",
    errors: [],
    claims: ["claim_001 (6 docs)", "claim_004 (4 docs)"],
    timings: { ingest: "1m 30s", classify: "ongoing", extract: "ongoing" },
    reuse: { ingestion: 4, classification: 2 },
  },
  {
    run_id: "run_20260113_100000_jkl012",
    friendly_name: "quiet-panda-49",
    status: "queued",
    prompt_config: "fast_extraction_v1 (gpt-4o-mini)",
    claims_count: 1,
    docs_total: 3,
    docs_processed: 0,
    started_at: "5m ago",
    stage_progress: { ingest: 0, classify: 0, extract: 0 },
    last_log: "queued - waiting for capacity",
    errors: [],
    claims: ["claim_002 (3 docs)"],
    timings: { ingest: "-", classify: "-", extract: "-" },
    reuse: { ingestion: 0, classification: 0 },
  },
  {
    run_id: "run_20260112_150000_mno345",
    friendly_name: "bold-raven-45",
    status: "partial",
    prompt_config: "generic_extraction_v1 (gpt-4o)",
    claims_count: 2,
    docs_total: 8,
    docs_processed: 6,
    started_at: "1d ago",
    completed_at: "1d ago",
    duration: "3m 55s",
    stage_progress: { ingest: 100, classify: 100, extract: 75 },
    cost_estimate: "$1.85",
    last_log: "extract: 6/8 docs processed",
    errors: [
      { doc: "doc_015.pdf", stage: "extraction", message: "OCR confidence below threshold" },
      { doc: "doc_018.pdf", stage: "classification", message: "Unknown document type" },
    ],
    claims: ["claim_003 (5 docs)", "claim_005 (3 docs)"],
    timings: { ingest: "1m 05s", classify: "45s", extract: "2m 05s" },
    reuse: { ingestion: 2, classification: 1 },
  },
];

const AUDIT_LOG: AuditEntry[] = [
  { timestamp: "22:12", user: "admin", action: "Started run crisp-falcon-47" },
  { timestamp: "22:08", user: "admin", action: "Deleted run amber-tiger-44" },
  { timestamp: "21:59", user: "admin", action: "Cancelled run swift-eagle-43" },
  { timestamp: "21:45", user: "admin", action: "Created config fast_extraction_v1" },
  { timestamp: "20:30", user: "admin", action: "Started run amber-tiger-46" },
];

const DEFAULT_STAGES: Stage[] = ["ingest", "classify", "extract"];

// Status badge component
function StatusBadge({ status }: { status: RunStatus }) {
  const styles: Record<RunStatus, string> = {
    running: "bg-info/10 text-info",
    queued: "bg-warning/10 text-warning-foreground",
    success: "bg-success/10 text-success",
    partial: "bg-accent/10 text-accent-foreground",
    failed: "bg-destructive/10 text-destructive",
  };
  const labels: Record<RunStatus, string> = {
    running: "RUNNING",
    queued: "QUEUED",
    success: "SUCCESS",
    partial: "PARTIAL",
    failed: "FAILED",
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

// New Run Tab
function NewRunTab({
  claims,
  selectedClaims,
  onToggleClaim,
  stages,
  onToggleStage,
  onApplyPreset,
  promptConfig,
  onPromptConfigChange,
  forceOverwrite,
  onForceOverwriteChange,
  computeMetrics,
  onComputeMetricsChange,
  dryRun,
  onDryRunChange,
  activeRuns,
}: {
  claims: ClaimOption[];
  selectedClaims: string[];
  onToggleClaim: (id: string) => void;
  stages: Stage[];
  onToggleStage: (stage: Stage) => void;
  onApplyPreset: (preset: "full" | "classify_extract" | "extract_only") => void;
  promptConfig: string;
  onPromptConfigChange: (id: string) => void;
  forceOverwrite: boolean;
  onForceOverwriteChange: (v: boolean) => void;
  computeMetrics: boolean;
  onComputeMetricsChange: (v: boolean) => void;
  dryRun: boolean;
  onDryRunChange: (v: boolean) => void;
  activeRuns: RecentRun[];
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
          {filteredClaims.map((claim) => (
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
          ))}
          {filteredClaims.length === 0 && (
            <div className="px-3 py-4 text-sm text-muted-foreground text-center">No claims match</div>
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
          {PROMPT_CONFIGS.map((cfg) => (
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
          className={cn(
            "flex-1 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
            canStartRun
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-muted text-muted-foreground cursor-not-allowed"
          )}
          disabled={!canStartRun}
        >
          Start Run
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
}: {
  runs: RecentRun[];
  onSelectRun: (id: string | null) => void;
  selectedRunId: string | null;
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
            {filteredRuns.map((run) => {
              const isSelected = selectedRunId === run.run_id;
              const overallProgress = Math.round(
                (run.stage_progress.ingest + run.stage_progress.classify + run.stage_progress.extract) / 3
              );
              return (
                <>
                  <tr
                    key={run.run_id}
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
                      {run.status === "running" && run.last_log && (
                        <div className="text-xs text-muted-foreground mt-0.5">{run.last_log}</div>
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
                        <button className="text-destructive hover:underline">Delete</button>
                        {(run.status === "running" || run.status === "queued") && (
                          <button className="text-warning-foreground hover:underline">Cancel</button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {isSelected && selectedRun && (
                    <tr key={`${run.run_id}-details`} className="border-t bg-muted/20">
                      <td colSpan={6} className="px-4 py-4">
                        <RunDetailsPanel run={selectedRun} />
                      </td>
                    </tr>
                  )}
                </>
              );
            })}
            {filteredRuns.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                  No runs match the current filters
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Run Details Panel
function RunDetailsPanel({ run }: { run: RecentRun }) {
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
        <button className="px-3 py-1.5 border text-xs rounded-lg text-destructive hover:bg-destructive/10">
          Delete
        </button>
      </div>
    </div>
  );
}

// Config Tab
function ConfigTab() {
  return (
    <div className="space-y-6 max-w-3xl">
      {/* Prompt Configs */}
      <div className="bg-card border rounded-xl p-5">
        <h3 className="text-sm font-medium text-foreground mb-4">Prompt Configs</h3>
        <div className="space-y-3">
          {PROMPT_CONFIGS.map((cfg) => (
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
                    <button className="text-xs text-muted-foreground hover:underline">Set as default</button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
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
            <select className="px-2 py-1 text-xs border rounded-lg bg-background">
              <option>Last 7 days</option>
              <option>Last 30 days</option>
              <option>All time</option>
            </select>
          </div>
        </div>
        <div className="space-y-2">
          {AUDIT_LOG.map((entry, idx) => (
            <div key={idx} className="text-xs text-muted-foreground flex gap-2">
              <span className="text-muted-foreground/70 w-12">{entry.timestamp}</span>
              <span className="text-muted-foreground/70 w-12">{entry.user}</span>
              <span className="text-foreground">{entry.action}</span>
            </div>
          ))}
        </div>
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
  const [promptConfig, setPromptConfig] = useState("generic_v1");
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [computeMetrics, setComputeMetrics] = useState(true);
  const [dryRun, setDryRun] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  const activeRuns = RECENT_RUNS.filter((r) => r.status === "running" || r.status === "queued");

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
            claims={CLAIM_OPTIONS}
            selectedClaims={selectedClaims}
            onToggleClaim={toggleClaim}
            stages={stages}
            onToggleStage={toggleStage}
            onApplyPreset={applyPreset}
            promptConfig={promptConfig}
            onPromptConfigChange={setPromptConfig}
            forceOverwrite={forceOverwrite}
            onForceOverwriteChange={setForceOverwrite}
            computeMetrics={computeMetrics}
            onComputeMetricsChange={setComputeMetrics}
            dryRun={dryRun}
            onDryRunChange={setDryRun}
            activeRuns={activeRuns}
          />
        )}
        {activeTab === "runs" && (
          <RunsTab
            runs={RECENT_RUNS}
            onSelectRun={setSelectedRunId}
            selectedRunId={selectedRunId}
          />
        )}
        {activeTab === "config" && <ConfigTab />}
      </div>
    </div>
  );
}
