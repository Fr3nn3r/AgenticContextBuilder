import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { cn } from "../../lib/utils";
import { formatDocType, formatFieldName, formatTimestamp } from "../../lib/formatters";
import {
  MetricCardRow,
  DeltaMetricCard,
  ScoreBadge,
  BaselineBadge,
  PageLoadingSkeleton,
} from "../shared";
import { ChartCard, TrendAreaChart } from "../charts";
import {
  getInsightsRuns,
  compareRuns,
  getBaseline,
  setBaseline,
  clearBaseline,
  type RunInfo,
  type RunComparison,
} from "../../api/client";
import { EvolutionView } from "./EvolutionView";
import { AssessmentEvalView } from "../assessment";

type EvaluationTab = "compare" | "evolution" | "assessment";

export function EvaluationPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Tab state (persisted in URL)
  const activeTab = (searchParams.get("tab") as EvaluationTab) || "assessment";

  const setActiveTab = (tab: EvaluationTab) => {
    setSearchParams({ tab });
  };

  // Run state
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [baselineRunId, setBaselineRunId] = useState<string | null>(null);

  // Comparison state
  const [comparison, setComparison] = useState<RunComparison | null>(null);
  const [compareBaselineId, setCompareBaselineId] = useState<string | null>(null);
  const [compareCurrentId, setCompareCurrentId] = useState<string | null>(null);

  // UI state
  const [loading, setLoading] = useState(true);

  // Load runs and baseline on mount
  useEffect(() => {
    loadRuns();
    loadBaseline();
  }, []);

  // Load comparison when both runs selected
  useEffect(() => {
    if (compareBaselineId && compareCurrentId && compareBaselineId !== compareCurrentId) {
      loadComparison(compareBaselineId, compareCurrentId);
    } else {
      setComparison(null);
    }
  }, [compareBaselineId, compareCurrentId]);

  async function loadRuns() {
    try {
      setLoading(true);
      const runsData = await getInsightsRuns();
      setRuns(runsData);

      // Auto-select latest run for comparison if none selected
      if (runsData.length > 0) {
        setCompareCurrentId(runsData[0].run_id);
      }
    } catch (err) {
      console.error("Failed to load runs:", err);
    } finally {
      setLoading(false);
    }
  }

  async function loadBaseline() {
    try {
      const data = await getBaseline();
      setBaselineRunId(data.baseline_run_id);
      setCompareBaselineId(data.baseline_run_id);
    } catch {
      // Ignore
    }
  }

  async function loadComparison(baselineId: string, currentId: string) {
    try {
      const data = await compareRuns(baselineId, currentId);
      setComparison(data);
    } catch (err) {
      console.error("Failed to compare runs:", err);
      setComparison(null);
    }
  }

  async function handleSetBaseline(runId: string) {
    try {
      await setBaseline(runId);
      setBaselineRunId(runId);
      setCompareBaselineId(runId);
    } catch (err) {
      console.error("Failed to set baseline:", err);
    }
  }

  async function handleClearBaseline() {
    try {
      await clearBaseline();
      setBaselineRunId(null);
    } catch (err) {
      console.error("Failed to clear baseline:", err);
    }
  }

  function handleViewRun(runId: string) {
    navigate(`/batches/${runId}/metrics`);
  }

  // Transform runs for trend chart (reverse to show oldest first)
  const trendData = [...runs].reverse().map(run => ({
    run_id: run.run_id,
    timestamp: run.timestamp,
    accuracy: run.accuracy_rate || 0,
    presence: run.presence_rate || 0,
    evidence: run.evidence_rate || 0,
  }));

  if (loading && activeTab === "compare") {
    return <PageLoadingSkeleton message="Loading evaluation data..." />;
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Evaluation</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Track assessment accuracy and quality metrics
          </p>
        </div>
        <div className="flex items-center gap-2">
          {activeTab === "compare" && baselineRunId && (
            <>
              <span className="text-xs text-success bg-success/10 px-2 py-1 rounded flex items-center gap-1">
                <BaselineBadge />
                {baselineRunId}
              </span>
              <button
                onClick={handleClearBaseline}
                className="text-xs px-2 py-1 text-muted-foreground hover:text-foreground"
              >
                Clear Baseline
              </button>
            </>
          )}
        </div>
      </div>

      {/* Tab Navigation - Pipeline Evolution and Compare Runs hidden for now */}
      <div className="flex items-center gap-1 border-b">
        <button
          onClick={() => setActiveTab("assessment")}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
            activeTab === "assessment"
              ? "border-foreground text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground"
          )}
        >
          Assessment
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === "evolution" ? (
        <EvolutionView />
      ) : activeTab === "assessment" ? (
        <AssessmentEvalView />
      ) : (
        <CompareRunsView
          runs={runs}
          baselineRunId={baselineRunId}
          comparison={comparison}
          compareBaselineId={compareBaselineId}
          compareCurrentId={compareCurrentId}
          trendData={trendData}
          setCompareBaselineId={setCompareBaselineId}
          setCompareCurrentId={setCompareCurrentId}
          handleSetBaseline={handleSetBaseline}
          handleViewRun={handleViewRun}
        />
      )}
    </div>
  );
}

// =============================================================================
// COMPARE RUNS VIEW (extracted from original)
// =============================================================================

interface CompareRunsViewProps {
  runs: RunInfo[];
  baselineRunId: string | null;
  comparison: RunComparison | null;
  compareBaselineId: string | null;
  compareCurrentId: string | null;
  trendData: Array<{ run_id: string; timestamp?: string | null; accuracy: number; presence: number; evidence: number }>;
  setCompareBaselineId: (id: string | null) => void;
  setCompareCurrentId: (id: string | null) => void;
  handleSetBaseline: (id: string) => void;
  handleViewRun: (id: string) => void;
}

function CompareRunsView({
  runs,
  baselineRunId,
  comparison,
  compareBaselineId,
  compareCurrentId,
  trendData,
  setCompareBaselineId,
  setCompareCurrentId,
  handleSetBaseline,
  handleViewRun,
}: CompareRunsViewProps) {
  return (
    <div className="space-y-6">
      {/* Run Comparison Selectors */}
      <div className="bg-card rounded-lg border shadow-sm p-4">
        <h2 className="text-sm font-semibold mb-3">Compare Runs</h2>
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-foreground">Baseline:</label>
            <select
              value={compareBaselineId || ""}
              onChange={(e) => setCompareBaselineId(e.target.value || null)}
              className="border rounded px-3 py-1.5 text-sm min-w-[200px] bg-background"
            >
              <option value="">Select baseline...</option>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id} ({formatTimestamp(run.timestamp)})
                </option>
              ))}
            </select>
          </div>
          <span className="text-muted-foreground">vs</span>
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-foreground">Current:</label>
            <select
              value={compareCurrentId || ""}
              onChange={(e) => setCompareCurrentId(e.target.value || null)}
              className="border rounded px-3 py-1.5 text-sm min-w-[200px] bg-background"
            >
              <option value="">Select current...</option>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id} ({formatTimestamp(run.timestamp)})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Trend Chart */}
      {trendData.length > 1 && (
        <ChartCard title="Accuracy Trend Over Time" height="h-[250px]">
          <TrendAreaChart data={trendData} />
        </ChartCard>
      )}

      {/* Comparison Results */}
      {comparison && (
        <>
          {/* KPI Deltas */}
          <div className="bg-card rounded-lg border shadow-sm p-4">
            <h3 className="text-sm font-semibold mb-3">KPI Changes</h3>
            <MetricCardRow columns={5}>
              {Object.entries(comparison.overview_deltas).map(([key, val]) => (
                <DeltaMetricCard
                  key={key}
                  label={formatKpiLabel(key)}
                  baseline={val.baseline}
                  current={val.current}
                  delta={val.delta}
                  isPercent={key.includes("presence") || key.includes("accuracy") || key.includes("evidence")}
                />
              ))}
            </MetricCardRow>
          </div>

          {/* Doc Type Deltas */}
          {comparison.doc_type_deltas.length > 0 && (
            <div className="bg-card rounded-lg border shadow-sm p-4">
              <h3 className="text-sm font-semibold mb-3">Doc Type Changes</h3>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-left p-2 font-medium">Doc Type</th>
                    <th className="text-right p-2 font-medium">Presence Change</th>
                    <th className="text-right p-2 font-medium">Accuracy Change</th>
                    <th className="text-right p-2 font-medium">Evidence Change</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.doc_type_deltas.map((dt) => (
                    <tr key={dt.doc_type} className="border-b">
                      <td className="p-2 font-medium">{formatDocType(dt.doc_type)}</td>
                      <td className="p-2 text-right"><DeltaBadge delta={dt.presence_delta} /></td>
                      <td className="p-2 text-right"><DeltaBadge delta={dt.accuracy_delta} /></td>
                      <td className="p-2 text-right"><DeltaBadge delta={dt.evidence_delta} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Priority Changes */}
          {comparison.priority_changes.length > 0 && (
            <div className="bg-card rounded-lg border shadow-sm p-4">
              <h3 className="text-sm font-semibold mb-3">Priority List Changes</h3>
              <div className="space-y-2">
                {comparison.priority_changes.map((change, idx) => (
                  <div
                    key={idx}
                    className={cn(
                      "flex items-center gap-2 text-sm px-3 py-2 rounded",
                      change.status === "improved" ? "bg-success/10" : "bg-destructive/10"
                    )}
                  >
                    <span className={change.status === "improved" ? "text-success" : "text-destructive"}>
                      {change.status === "improved" ? "↑" : "↓"}
                    </span>
                    <span className="font-medium">{formatDocType(change.doc_type)}</span>
                    <span className="text-muted-foreground/70">·</span>
                    <span>{formatFieldName(change.field_name)}</span>
                    {change.delta !== undefined && (
                      <span className="text-muted-foreground ml-auto">
                        {change.delta > 0 ? `+${change.delta}` : change.delta} affected
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {!comparison && compareBaselineId && compareCurrentId && compareBaselineId !== compareCurrentId && (
        <div className="text-center text-muted-foreground py-8">Loading comparison...</div>
      )}

      {(!compareBaselineId || !compareCurrentId || compareBaselineId === compareCurrentId) && !comparison && (
        <div className="bg-card rounded-lg border shadow-sm p-8 text-center text-muted-foreground">
          Select two different runs above to compare their metrics
        </div>
      )}

      {/* Run History Table */}
      <div className="bg-card rounded-lg border shadow-sm">
        <div className="p-4 border-b">
          <h3 className="text-sm font-semibold">Run History</h3>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="text-left p-3 font-medium">Batch ID</th>
              <th className="text-left p-3 font-medium">Timestamp</th>
              <th className="text-left p-3 font-medium">Model</th>
              <th className="text-right p-3 font-medium">Docs</th>
              <th className="text-right p-3 font-medium">Labeled</th>
              <th className="text-right p-3 font-medium">Presence</th>
              <th className="text-right p-3 font-medium">Accuracy</th>
              <th className="text-right p-3 font-medium">Evidence</th>
              <th className="text-left p-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                key={run.run_id}
                className={cn(
                  "border-b hover:bg-muted/50",
                  run.run_id === baselineRunId && "bg-success/5"
                )}
              >
                <td className="p-3 font-mono text-xs">
                  {run.run_id}
                  {run.run_id === baselineRunId && <span className="ml-2"><BaselineBadge /></span>}
                </td>
                <td className="p-3 text-muted-foreground">{formatTimestamp(run.timestamp)}</td>
                <td className="p-3 text-muted-foreground">{run.model || "-"}</td>
                <td className="p-3 text-right">{run.docs_count}</td>
                <td className="p-3 text-right">{run.labeled_count}</td>
                <td className="p-3 text-right"><ScoreBadge value={run.presence_rate} /></td>
                <td className="p-3 text-right"><ScoreBadge value={run.accuracy_rate} /></td>
                <td className="p-3 text-right"><ScoreBadge value={run.evidence_rate} /></td>
                <td className="p-3">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleViewRun(run.run_id)}
                      className="text-xs text-accent-foreground hover:text-accent"
                    >
                      View
                    </button>
                    {run.run_id !== baselineRunId && (
                      <button
                        onClick={() => handleSetBaseline(run.run_id)}
                        className="text-xs text-muted-foreground hover:text-foreground"
                      >
                        Set Baseline
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={9} className="p-4 text-center text-muted-foreground">
                  No runs found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// =============================================================================
// Helper Components
// =============================================================================

function formatKpiLabel(key: string): string {
  const labels: Record<string, string> = {
    required_field_presence_rate: "Presence",
    required_field_accuracy: "Accuracy",
    evidence_rate: "Evidence",
    docs_reviewed: "Reviewed",
    docs_doc_type_wrong: "Type Wrong",
  };
  return labels[key] || key;
}

function DeltaBadge({ delta }: { delta: number }) {
  if (delta === 0) return <span className="text-muted-foreground/70">-</span>;
  const isPositive = delta > 0;
  return (
    <span className={cn("font-medium", isPositive ? "text-success" : "text-destructive")}>
      {isPositive ? "+" : ""}{delta}%
    </span>
  );
}
