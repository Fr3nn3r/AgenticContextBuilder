import { useState } from "react";
import {
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Send,
  CheckCircle2,
} from "lucide-react";
import { cn } from "../../lib/utils";
import type { DecisionReadiness } from "./DecisionReadinessCard";
import type { AssessmentDecision } from "../../types";

interface WorkflowActionsPanelProps {
  readiness: DecisionReadiness;
  currentDecision: AssessmentDecision | null;
  onAction?: (action: "approve" | "reject" | "refer", reason: string) => void;
}

type FeedbackRating = "good" | "poor" | null;

/**
 * Feedback panel for users to rate assessment quality and provide comments.
 */
export function WorkflowActionsPanel({
  currentDecision,
}: WorkflowActionsPanelProps) {
  const [rating, setRating] = useState<FeedbackRating>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = () => {
    if (!rating) return;

    // TODO: Send feedback to backend
    console.log("Assessment feedback:", { rating, comment, decision: currentDecision });
    setSubmitted(true);
  };

  if (submitted) {
    return (
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
            Assessment Feedback
          </h3>
        </div>
        <div className="p-6 text-center">
          <CheckCircle2 className="h-10 w-10 text-green-500 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Thank you for your feedback!
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Your input helps improve the assessment system.
          </p>
          <button
            onClick={() => {
              setSubmitted(false);
              setRating(null);
              setComment("");
            }}
            className="mt-4 text-xs text-blue-600 dark:text-blue-400 hover:underline"
          >
            Submit another response
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
        <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
          Assessment Feedback
        </h3>
      </div>

      <div className="p-4 space-y-4">
        {/* Rating Question */}
        <div>
          <p className="text-sm text-slate-600 dark:text-slate-300 mb-3">
            How well did this assessment perform?
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => setRating("good")}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all",
                "border-2",
                rating === "good"
                  ? "bg-green-50 dark:bg-green-900/30 border-green-500 text-green-700 dark:text-green-300"
                  : "bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-green-300 dark:hover:border-green-700"
              )}
            >
              <ThumbsUp className={cn("h-5 w-5", rating === "good" && "fill-current")} />
              Good
            </button>
            <button
              onClick={() => setRating("poor")}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all",
                "border-2",
                rating === "poor"
                  ? "bg-red-50 dark:bg-red-900/30 border-red-500 text-red-700 dark:text-red-300"
                  : "bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-400 hover:border-red-300 dark:hover:border-red-700"
              )}
            >
              <ThumbsDown className={cn("h-5 w-5", rating === "poor" && "fill-current")} />
              Poor
            </button>
          </div>
        </div>

        {/* Comment Field */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-medium text-slate-500 dark:text-slate-400 mb-1.5">
            <MessageSquare className="h-3.5 w-3.5" />
            Comments (optional)
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder={
              rating === "poor"
                ? "What could be improved? Wrong decision, missing info, etc."
                : "Any additional comments about this assessment..."
            }
            rows={3}
            className={cn(
              "w-full px-3 py-2 text-sm rounded-lg border transition-colors resize-none",
              "bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700",
              "text-slate-700 dark:text-slate-200 placeholder-slate-400 dark:placeholder-slate-500",
              "focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500"
            )}
          />
        </div>

        {/* Submit Button */}
        <button
          onClick={handleSubmit}
          disabled={!rating}
          className={cn(
            "w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors",
            rating
              ? "bg-blue-600 text-white hover:bg-blue-700"
              : "bg-slate-100 dark:bg-slate-800 text-slate-400 dark:text-slate-500 cursor-not-allowed"
          )}
        >
          <Send className="h-4 w-4" />
          Submit Feedback
        </button>

        {/* Help Text */}
        <p className="text-xs text-slate-500 dark:text-slate-400 text-center">
          Your feedback helps improve assessment accuracy over time.
        </p>
      </div>
    </div>
  );
}
