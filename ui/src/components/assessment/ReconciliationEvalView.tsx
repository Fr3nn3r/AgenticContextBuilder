import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, ExternalLink, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";
import { cn } from "../../lib/utils";
import { formatTimestamp } from "../../lib/formatters";
import type {
  ReconciliationEvaluation,
  ReconciliationClaimResult,
  ReconciliationGateStatus,
  FactFrequency,
} from "../../types";
import { getLatestReconciliationEval } from "../../api/client";
import { MetricCard, MetricCardRow, StatusBadge } from "../shared";

const GATE_LABELS: Record<ReconciliationGateStatus, string> = {
  pass: "Pass",
  warn: "Warn",
  fail: "Fail",
};

const GATE_ICONS: Record<ReconciliationGateStatus, typeof CheckCircle2> = {
  pass: CheckCircle2,
  warn: AlertTriangle,
  fail: XCircle,
};

const GATE_COLORS: Record<ReconciliationGateStatus, string> = {
  pass: "text-green-500",
  warn: "text-amber-500",
  fail: "text-red-500",
};

/**
 * Reconciliation gate evaluation view with summary metrics and per-claim results.
 */
export function ReconciliationEvalView() {
  const navigate = useNavigate();
  const [evaluation, setEvaluation] = useState<ReconciliationEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<ReconciliationGateStatus | "all">("all");

  useEffect(() => {
    loadEvaluation();
  }, []);

  async function loadEvaluation() {
    setLoading(true);
    setError(null);
    try {
      const data = await getLatestReconciliationEval();
      setEvaluation(data);
    } catch (err) {
      console.error("Reconciliation evaluation API error:", err);
      setError("Failed to load reconciliation evaluation");
    } finally {
      setLoading(false);
    }
  }

  // Filter results
  const filteredResults = evaluation?.results.filter((r) => {
    if (filterStatus !== "all" && r.gate_status !== filterStatus) return false;
    return true;
  }) || [];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
          <p className="text-sm text-slate-500">Loading reconciliation evaluation...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>
        <button
          onClick={loadEvaluation}
          className="px-4 py-2 bg-slate-100 dark:bg-slate-800 rounded-lg text-sm hover:bg-slate-200 dark:hover:bg-slate-700"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!evaluation) {
    return (
      <div className="p-8 text-center bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
        <div className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="h-6 w-6 text-slate-400" />
        </div>
        <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
          No Reconciliation Evaluation
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
          Run reconciliation on claims and then generate an evaluation.
        </p>
        <code className="text-xs bg-slate-100 dark:bg-slate-800 px-2 py-1 rounded">
          python -m context_builder.cli reconcile-eval
        </code>
      </div>
    );
  }

  const { summary, top_missing_facts, top_conflicts, results } = evaluation;

  return (
    <div className="space-y-6">
      {/* Eval metadata */}
      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
        <span>Run ID: {evaluation.run_id || "Multiple runs"}</span>
        <span>Generated: {formatTimestamp(evaluation.evaluated_at)}</span>
      </div>

      {/* KPI Cards */}
      <MetricCardRow columns={5}>
        <MetricCard
          label="Total Claims"
          value={summary.total_claims}
          subtext="reconciled"
        />
        <MetricCard
          label="Pass Rate"
          value={summary.pass_rate_percent}
          variant={summary.pass_rate >= 0.8 ? "success" : summary.pass_rate >= 0.5 ? "warning" : "error"}
        />
        <MetricCard
          label="Passed"
          value={summary.passed}
          variant="success"
        />
        <MetricCard
          label="Warned"
          value={summary.warned}
          variant="warning"
        />
        <MetricCard
          label="Failed"
          value={summary.failed}
          variant="error"
        />
      </MetricCardRow>

      {/* Secondary KPIs */}
      <MetricCardRow columns={4}>
        <MetricCard
          label="Avg Facts"
          value={summary.avg_fact_count.toFixed(1)}
          subtext="per claim"
        />
        <MetricCard
          label="Avg Conflicts"
          value={summary.avg_conflicts.toFixed(1)}
          subtext="per claim"
          variant={summary.avg_conflicts > 2 ? "warning" : "default"}
        />
        <MetricCard
          label="Total Conflicts"
          value={summary.total_conflicts}
          variant={summary.total_conflicts > 5 ? "warning" : "default"}
        />
        <MetricCard
          label="Avg Missing"
          value={summary.avg_missing_critical.toFixed(1)}
          subtext="critical facts"
          variant={summary.avg_missing_critical > 0 ? "warning" : "default"}
        />
      </MetricCardRow>

      {/* Top Issues Row */}
      <div className="grid grid-cols-2 gap-4">
        {/* Top Missing Facts */}
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Top Missing Critical Facts
            </h3>
          </div>
          <div className="p-4">
            {top_missing_facts.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-4">
                No missing critical facts
              </p>
            ) : (
              <div className="space-y-2">
                {top_missing_facts.slice(0, 5).map((fact) => (
                  <FactFrequencyRow key={fact.fact_name} fact={fact} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Top Conflicts */}
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Top Conflicting Facts
            </h3>
          </div>
          <div className="p-4">
            {top_conflicts.length === 0 ? (
              <p className="text-sm text-slate-500 dark:text-slate-400 text-center py-4">
                No conflicts detected
              </p>
            ) : (
              <div className="space-y-2">
                {top_conflicts.slice(0, 5).map((fact) => (
                  <FactFrequencyRow key={fact.fact_name} fact={fact} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Results Table */}
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Per-Claim Results ({filteredResults.length})
          </h3>
          <div className="flex items-center gap-3">
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value as ReconciliationGateStatus | "all")}
              className="text-xs border border-slate-300 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-800"
            >
              <option value="all">All Statuses</option>
              <option value="pass">Pass</option>
              <option value="warn">Warn</option>
              <option value="fail">Fail</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Claim ID</th>
                <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Gate</th>
                <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Facts</th>
                <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Conflicts</th>
                <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Missing</th>
                <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Coverage</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Reasons</th>
                <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300 w-16"></th>
              </tr>
            </thead>
            <tbody>
              {filteredResults.map((result, idx) => (
                <ResultRow
                  key={`${result.claim_id}-${idx}`}
                  result={result}
                  onViewClaim={() => navigate(`/claims/explorer?claim=${result.claim_id}`)}
                />
              ))}
              {filteredResults.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500 dark:text-slate-400">
                    No results match the current filter
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

interface FactFrequencyRowProps {
  fact: FactFrequency;
}

function FactFrequencyRow({ fact }: FactFrequencyRowProps) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="font-mono text-xs text-slate-700 dark:text-slate-200">
        {fact.fact_name}
      </span>
      <span className="text-xs text-slate-500 dark:text-slate-400">
        {fact.count} claim{fact.count !== 1 ? "s" : ""}
      </span>
    </div>
  );
}

interface ResultRowProps {
  result: ReconciliationClaimResult;
  onViewClaim: () => void;
}

function ResultRow({ result, onViewClaim }: ResultRowProps) {
  const GateIcon = GATE_ICONS[result.gate_status];
  const gateColor = GATE_COLORS[result.gate_status];

  return (
    <tr
      className={cn(
        "border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50",
        result.gate_status === "fail" && "bg-red-50/50 dark:bg-red-900/10",
        result.gate_status === "warn" && "bg-amber-50/50 dark:bg-amber-900/10"
      )}
    >
      <td className="px-4 py-2 font-mono text-xs text-slate-700 dark:text-slate-200">
        {result.claim_id}
      </td>
      <td className="px-4 py-2 text-center">
        <div className="flex items-center justify-center gap-1">
          <GateIcon className={cn("h-4 w-4", gateColor)} />
          <span className="text-xs">{GATE_LABELS[result.gate_status]}</span>
        </div>
      </td>
      <td className="px-4 py-2 text-center text-xs text-slate-600 dark:text-slate-300">
        {result.fact_count}
      </td>
      <td className="px-4 py-2 text-center">
        <span className={cn(
          "text-xs",
          result.conflict_count > 2 && "text-red-600 dark:text-red-400 font-medium",
          result.conflict_count > 0 && result.conflict_count <= 2 && "text-amber-600 dark:text-amber-400",
          result.conflict_count === 0 && "text-slate-500 dark:text-slate-400"
        )}>
          {result.conflict_count}
        </span>
      </td>
      <td className="px-4 py-2 text-center">
        <span className={cn(
          "text-xs",
          result.missing_critical_count > 0 && "text-red-600 dark:text-red-400 font-medium",
          result.missing_critical_count === 0 && "text-slate-500 dark:text-slate-400"
        )}>
          {result.missing_critical_count}
        </span>
      </td>
      <td className="px-4 py-2 text-center">
        <span className={cn(
          "text-xs",
          result.provenance_coverage >= 0.8 && "text-green-600 dark:text-green-400",
          result.provenance_coverage >= 0.5 && result.provenance_coverage < 0.8 && "text-amber-600 dark:text-amber-400",
          result.provenance_coverage < 0.5 && "text-slate-500 dark:text-slate-400"
        )}>
          {(result.provenance_coverage * 100).toFixed(0)}%
        </span>
      </td>
      <td className="px-4 py-2">
        <span className="text-xs text-slate-500 dark:text-slate-400 truncate block max-w-[200px]" title={result.reasons.join(", ")}>
          {result.reasons.join(", ") || "-"}
        </span>
      </td>
      <td className="px-4 py-2">
        <button
          onClick={onViewClaim}
          className="text-blue-600 dark:text-blue-400 hover:underline text-xs flex items-center gap-1"
        >
          <ExternalLink className="h-3 w-3" />
          View
        </button>
      </td>
    </tr>
  );
}
