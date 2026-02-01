import { useState, useEffect, useCallback } from "react";
import {
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Send,
  CheckCircle2,
  Loader2,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useAuth } from "../../context/AuthContext";
import { submitAssessmentFeedback, getAssessmentFeedback } from "../../api/client";
import type { DecisionReadiness } from "./DecisionReadinessCard";
import type { AssessmentDecision } from "../../types";

interface WorkflowActionsPanelProps {
  claimId: string;
  readiness: DecisionReadiness;
  currentDecision: AssessmentDecision | null;
  onAction?: (action: "approve" | "reject" | "refer", reason: string) => void;
}

type FeedbackRating = "good" | "poor" | null;

/**
 * Feedback panel for users to rate assessment quality and provide comments.
 */
export function WorkflowActionsPanel({
  claimId,
  currentDecision,
}: WorkflowActionsPanelProps) {
  const { user } = useAuth();
  const [rating, setRating] = useState<FeedbackRating>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [previousFeedback, setPreviousFeedback] = useState<{
    rating: string;
    comment: string;
    username: string;
    submitted_at: string;
  } | null>(null);

  // Load existing feedback on mount or when claimId changes
  const loadFeedback = useCallback(async () => {
    if (!claimId) return;
    const feedback = await getAssessmentFeedback(claimId);
    if (feedback) {
      setPreviousFeedback(feedback);
      setRating(feedback.rating as FeedbackRating);
      setComment(feedback.comment);
      setSubmitted(true);
    }
  }, [claimId]);

  useEffect(() => {
    // Reset state when claimId changes
    setRating(null);
    setComment("");
    setSubmitted(false);
    setPreviousFeedback(null);
    loadFeedback();
  }, [loadFeedback]);

  const handleSubmit = async () => {
    if (!rating) return;
    setSubmitting(true);
    try {
      await submitAssessmentFeedback(claimId, {
        rating,
        comment,
        username: user?.username ?? "anonymous",
      });
      setPreviousFeedback({
        rating,
        comment,
        username: user?.username ?? "anonymous",
        submitted_at: new Date().toISOString(),
      });
      setSubmitted(true);
    } catch (err) {
      console.error("Failed to submit feedback:", err);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="bg-card rounded-lg border border-border overflow-hidden">
        <div className="px-4 py-3 border-b border-border bg-muted/50">
          <h3 className="text-sm font-semibold text-foreground">
            Assessment Feedback
          </h3>
        </div>
        <div className="p-6 text-center">
          <CheckCircle2 className="h-10 w-10 text-success mx-auto mb-3" />
          <p className="text-sm font-medium text-foreground">
            Thank you for your feedback!
          </p>
          {previousFeedback && (
            <p className="text-xs text-muted-foreground mt-1">
              Rated <span className="font-medium">{previousFeedback.rating}</span>
              {previousFeedback.username && <> by {previousFeedback.username}</>}
              {previousFeedback.comment && <> &mdash; &ldquo;{previousFeedback.comment}&rdquo;</>}
            </p>
          )}
          <button
            onClick={() => {
              setSubmitted(false);
            }}
            className="mt-4 text-xs text-primary hover:underline"
          >
            Update feedback
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-muted/50">
        <h3 className="text-sm font-semibold text-foreground">
          Assessment Feedback
        </h3>
      </div>

      <div className="p-4 space-y-4">
        {/* Rating Question */}
        <div>
          <p className="text-sm text-foreground mb-3">
            How well did this assessment perform?
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => setRating("good")}
              className={cn(
                "flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-lg font-medium transition-all",
                "border-2",
                rating === "good"
                  ? "bg-success/10 border-success text-success"
                  : "bg-muted border-border text-muted-foreground hover:border-success/50"
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
                  ? "bg-destructive/10 border-destructive text-destructive"
                  : "bg-muted border-border text-muted-foreground hover:border-destructive/50"
              )}
            >
              <ThumbsDown className={cn("h-5 w-5", rating === "poor" && "fill-current")} />
              Poor
            </button>
          </div>
        </div>

        {/* Comment Field */}
        <div>
          <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground mb-1.5">
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
              "bg-muted border-border",
              "text-foreground placeholder-muted-foreground",
              "focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary"
            )}
          />
        </div>

        {/* Submit Button */}
        <button
          onClick={handleSubmit}
          disabled={!rating || submitting}
          className={cn(
            "w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-colors",
            rating && !submitting
              ? "bg-primary text-primary-foreground hover:bg-primary/90"
              : "bg-muted text-muted-foreground cursor-not-allowed"
          )}
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              <Send className="h-4 w-4" />
              Submit Feedback
            </>
          )}
        </button>

        {/* Help Text */}
        <p className="text-xs text-muted-foreground text-center">
          Your feedback helps improve assessment accuracy over time.
        </p>
      </div>
    </div>
  );
}
