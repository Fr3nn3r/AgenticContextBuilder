import { AlertCircle } from "lucide-react";
import { cn } from "../../lib/utils";
import type { AssessmentConfusionMatrix, AssessmentDecision } from "../../types";

interface ConfusionMatrixChartProps {
  matrix: AssessmentConfusionMatrix;
  className?: string;
}

const DECISION_ORDER: AssessmentDecision[] = ["APPROVE", "REJECT", "REFER_TO_HUMAN"];

const DECISION_LABELS: Record<AssessmentDecision, string> = {
  APPROVE: "Approve",
  REJECT: "Reject",
  REFER_TO_HUMAN: "Refer",
};

/**
 * 3x3 confusion matrix visualization for assessment decisions.
 * Rows = Actual, Columns = Predicted.
 * Diagonal cells are highlighted as correct predictions.
 */
export function ConfusionMatrixChart({ matrix, className }: ConfusionMatrixChartProps) {
  // Calculate per-bucket accuracy
  const bucketStats = DECISION_ORDER.map((decision) => {
    const row = matrix.matrix[decision] || {};
    const total = DECISION_ORDER.reduce((sum, d) => sum + (row[d] || 0), 0);
    const correct = row[decision] || 0;
    const accuracy = total > 0 ? Math.round((correct / total) * 100) : 0;
    return { decision, total, correct, accuracy };
  });

  // Check if REFER_TO_HUMAN is present in predictions
  const hasReferrals = DECISION_ORDER.some((actual) => {
    const row = matrix.matrix[actual] || {};
    return (row["REFER_TO_HUMAN"] || 0) > 0;
  });

  return (
    <div className={cn("bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700", className)}>
      <div className="p-4 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Decision Confusion Matrix
          </h3>
          <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
            <span>Total: {matrix.total_evaluated}</span>
            <span className={cn(
              "font-medium",
              matrix.decision_accuracy >= 80 ? "text-green-600 dark:text-green-400" :
              matrix.decision_accuracy >= 60 ? "text-amber-600 dark:text-amber-400" :
              "text-red-600 dark:text-red-400"
            )}>
              Accuracy: {matrix.decision_accuracy}%
            </span>
          </div>
        </div>
      </div>

      <div className="p-4">
        {/* Matrix Grid */}
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr>
                <th className="p-2"></th>
                <th className="p-2" colSpan={3}>
                  <div className="text-center text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
                    Predicted
                  </div>
                </th>
              </tr>
              <tr>
                <th className="p-2"></th>
                {DECISION_ORDER.map((decision) => (
                  <th
                    key={decision}
                    className="p-2 text-center font-medium text-slate-600 dark:text-slate-300 min-w-[80px]"
                  >
                    {DECISION_LABELS[decision]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {DECISION_ORDER.map((actual, rowIdx) => (
                <tr key={actual}>
                  {/* Row label - show "Actual" label only on first row */}
                  <td className="p-2 text-right font-medium text-slate-600 dark:text-slate-300 whitespace-nowrap">
                    {rowIdx === 1 && (
                      <span className="text-xs text-slate-400 dark:text-slate-500 mr-2 inline-block -rotate-90 origin-right">
                        Actual
                      </span>
                    )}
                    {DECISION_LABELS[actual]}
                  </td>
                  {DECISION_ORDER.map((predicted) => {
                    const value = matrix.matrix[actual]?.[predicted] || 0;
                    const isDiagonal = actual === predicted;
                    return (
                      <td
                        key={predicted}
                        className={cn(
                          "p-3 text-center border border-slate-200 dark:border-slate-700",
                          isDiagonal && value > 0 && "bg-green-100 dark:bg-green-900/30",
                          !isDiagonal && value > 0 && "bg-red-50 dark:bg-red-900/20"
                        )}
                      >
                        <span
                          className={cn(
                            "text-lg font-bold",
                            isDiagonal && value > 0 && "text-green-700 dark:text-green-300",
                            !isDiagonal && value > 0 && "text-red-600 dark:text-red-400",
                            value === 0 && "text-slate-300 dark:text-slate-600"
                          )}
                        >
                          {value}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Per-bucket accuracy */}
        <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-700">
          <h4 className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-2">
            Per-Class Accuracy
          </h4>
          <div className="flex gap-4">
            {bucketStats.map(({ decision, accuracy, total }) => (
              <div key={decision} className="flex items-center gap-2">
                <span className="text-xs text-slate-600 dark:text-slate-300">
                  {DECISION_LABELS[decision]}:
                </span>
                <span className={cn(
                  "text-xs font-medium",
                  accuracy >= 80 ? "text-green-600 dark:text-green-400" :
                  accuracy >= 60 ? "text-amber-600 dark:text-amber-400" :
                  "text-red-600 dark:text-red-400"
                )}>
                  {accuracy}%
                </span>
                <span className="text-xs text-slate-400">
                  ({total})
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Warning when REFER_TO_HUMAN is present */}
        {hasReferrals && (
          <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
            <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-amber-700 dark:text-amber-300">
              Some claims were referred to human review. These require manual decision before
              accuracy metrics can be finalized.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
