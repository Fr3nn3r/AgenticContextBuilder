import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, ExternalLink, CheckCircle2, XCircle, ArrowRightCircle } from "lucide-react";
import { cn } from "../../lib/utils";
import { formatTimestamp } from "../../lib/formatters";
import type { AssessmentEvaluation, AssessmentEvalResult, AssessmentDecision } from "../../types";
import { getLatestAssessmentEval } from "../../api/client";
import { MetricCard, MetricCardRow, ScoreBadge, StatusBadge } from "../shared";
import { ConfusionMatrixChart } from "./ConfusionMatrixChart";

const DECISION_LABELS: Record<AssessmentDecision, string> = {
  APPROVE: "Approve",
  REJECT: "Reject",
  REFER_TO_HUMAN: "Refer",
};

const DECISION_ICONS: Record<AssessmentDecision, typeof CheckCircle2> = {
  APPROVE: CheckCircle2,
  REJECT: XCircle,
  REFER_TO_HUMAN: ArrowRightCircle,
};


/**
 * Full assessment evaluation view with confusion matrix and per-claim results.
 */
export function AssessmentEvalView() {
  const navigate = useNavigate();
  const [evaluation, setEvaluation] = useState<AssessmentEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterDecision, setFilterDecision] = useState<AssessmentDecision | "all">("all");
  const [showOnlyErrors, setShowOnlyErrors] = useState(false);

  useEffect(() => {
    loadEvaluation();
  }, []);

  async function loadEvaluation() {
    setLoading(true);
    setError(null);
    try {
      const data = await getLatestAssessmentEval();
      setEvaluation(data);
    } catch (err) {
      console.error("Failed to load evaluation:", err);
      setError(err instanceof Error ? err.message : "Failed to load evaluation data");
    } finally {
      setLoading(false);
    }
  }

  // Filter results
  const filteredResults = evaluation?.results.filter((r) => {
    if (filterDecision !== "all" && r.predicted !== filterDecision) return false;
    if (showOnlyErrors && r.is_correct) return false;
    return true;
  }) || [];

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
          <p className="text-sm text-slate-500">Loading assessment evaluation...</p>
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
          <svg className="h-6 w-6 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        </div>
        <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
          No Evaluation Data
        </h3>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          Run an assessment evaluation to see results here.
        </p>
      </div>
    );
  }

  const { summary, confusion_matrix, results } = evaluation;

  return (
    <div className="space-y-6">
      {/* Eval metadata */}
      <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
        <span>Evaluation ID: {evaluation.eval_id}</span>
        <span>Generated: {formatTimestamp(evaluation.timestamp)}</span>
      </div>

      {/* KPI Cards */}
      <MetricCardRow columns={5}>
        <MetricCard
          label="Total Claims"
          value={summary.total_claims}
          subtext="evaluated"
        />
        <MetricCard
          label="Accuracy"
          value={`${summary.accuracy_rate}%`}
          variant={summary.accuracy_rate >= 80 ? "success" : summary.accuracy_rate >= 60 ? "warning" : "error"}
        />
        <MetricCard
          label="Approve Precision"
          value={`${summary.approve_precision}%`}
          variant={summary.approve_precision >= 80 ? "success" : summary.approve_precision >= 60 ? "warning" : "error"}
        />
        <MetricCard
          label="Reject Precision"
          value={`${summary.reject_precision}%`}
          variant={summary.reject_precision >= 80 ? "success" : summary.reject_precision >= 60 ? "warning" : "error"}
        />
        <MetricCard
          label="Refer Rate"
          value={`${summary.refer_rate}%`}
          subtext="sent to human"
          variant={summary.refer_rate > 30 ? "warning" : "default"}
        />
      </MetricCardRow>

      {/* Confusion Matrix */}
      <ConfusionMatrixChart matrix={confusion_matrix} />

      {/* Results Table - only shown when per-claim data is available */}
      {results.length > 0 ? (
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Per-Claim Results ({filteredResults.length})
            </h3>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-xs">
                <input
                  type="checkbox"
                  checked={showOnlyErrors}
                  onChange={(e) => setShowOnlyErrors(e.target.checked)}
                  className="rounded border-slate-300"
                />
                <span className="text-slate-600 dark:text-slate-300">Errors only</span>
              </label>
              <select
                value={filterDecision}
                onChange={(e) => setFilterDecision(e.target.value as AssessmentDecision | "all")}
                className="text-xs border border-slate-300 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-800"
              >
                <option value="all">All Decisions</option>
                <option value="APPROVE">Approve</option>
                <option value="REJECT">Reject</option>
                <option value="REFER_TO_HUMAN">Refer to Human</option>
              </select>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                  <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Claim ID</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Predicted</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Actual</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Result</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Confidence</th>
                  <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Assumptions</th>
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
                    <td colSpan={7} className="px-4 py-8 text-center text-slate-500 dark:text-slate-400">
                      No results match the current filters
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 p-6 text-center text-slate-500 dark:text-slate-400 text-sm">
          Per-claim results are not available for this evaluation run.
          Run a legacy assessment evaluation to see per-claim details.
        </div>
      )}
    </div>
  );
}

interface ResultRowProps {
  result: AssessmentEvalResult;
  onViewClaim: () => void;
}

function ResultRow({ result, onViewClaim }: ResultRowProps) {
  const PredictedIcon = DECISION_ICONS[result.predicted];
  const ActualIcon = DECISION_ICONS[result.actual];

  return (
    <tr
      className={cn(
        "border-b border-slate-100 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/50",
        !result.is_correct && "bg-red-50/50 dark:bg-red-900/10"
      )}
    >
      <td className="px-4 py-2 font-mono text-xs text-slate-700 dark:text-slate-200">
        {result.claim_id}
      </td>
      <td className="px-4 py-2 text-center">
        <div className="flex items-center justify-center gap-1">
          <PredictedIcon className={cn(
            "h-4 w-4",
            result.predicted === "APPROVE" && "text-green-500",
            result.predicted === "REJECT" && "text-red-500",
            result.predicted === "REFER_TO_HUMAN" && "text-amber-500"
          )} />
          <span className="text-xs">{DECISION_LABELS[result.predicted]}</span>
        </div>
      </td>
      <td className="px-4 py-2 text-center">
        <div className="flex items-center justify-center gap-1">
          <ActualIcon className={cn(
            "h-4 w-4",
            result.actual === "APPROVE" && "text-green-500",
            result.actual === "REJECT" && "text-red-500",
            result.actual === "REFER_TO_HUMAN" && "text-amber-500"
          )} />
          <span className="text-xs">{DECISION_LABELS[result.actual]}</span>
        </div>
      </td>
      <td className="px-4 py-2 text-center">
        <StatusBadge variant={result.is_correct ? "success" : "error"} size="sm">
          {result.is_correct ? "Correct" : "Error"}
        </StatusBadge>
      </td>
      <td className="px-4 py-2 text-center">
        <ScoreBadge value={result.confidence_score} />
      </td>
      <td className="px-4 py-2 text-center">
        <span className={cn(
          "text-xs",
          result.assumption_count > 2 && "text-amber-600 dark:text-amber-400 font-medium",
          result.assumption_count <= 2 && "text-slate-500 dark:text-slate-400"
        )}>
          {result.assumption_count}
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
