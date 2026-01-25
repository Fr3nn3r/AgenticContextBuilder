import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, Users, RefreshCw } from "lucide-react";
import { cn } from "../../lib/utils";
import type { TriageQueueItem, TriageQueueFilters, TriagePriority, TriageReason, AssessmentDecision } from "../../types";
import { getTriageQueue, reviewTriageItem } from "../../api/client";
import { MetricCard, MetricCardRow } from "../shared";
import { TriageFilters } from "./TriageFilters";
import { TriageQueueRow } from "./TriageQueueRow";

// =====================
// MOCK DATA - Triage Queue
// =====================
const MOCK_TRIAGE_ITEMS: TriageQueueItem[] = [
  {
    claim_id: "CLM-2024-001847",
    priority: "critical",
    reasons: ["high_assumptions", "fraud_flag"],
    confidence_score: 45,
    assumption_count: 5,
    decision: "REJECT",
    fraud_indicator_count: 2,
  },
  {
    claim_id: "CLM-2024-001892",
    priority: "high",
    reasons: ["low_confidence", "missing_docs"],
    confidence_score: 52,
    assumption_count: 4,
    decision: "REFER_TO_HUMAN",
    fraud_indicator_count: 0,
  },
  {
    claim_id: "CLM-2024-001903",
    priority: "high",
    reasons: ["high_assumptions"],
    confidence_score: 58,
    assumption_count: 6,
    decision: "APPROVE",
    fraud_indicator_count: 0,
  },
  {
    claim_id: "CLM-2024-001915",
    priority: "medium",
    reasons: ["borderline_confidence"],
    confidence_score: 68,
    assumption_count: 2,
    decision: "APPROVE",
    fraud_indicator_count: 0,
  },
  {
    claim_id: "CLM-2024-001928",
    priority: "medium",
    reasons: ["cost_outlier"],
    confidence_score: 71,
    assumption_count: 1,
    decision: "REFER_TO_HUMAN",
    fraud_indicator_count: 1,
  },
  {
    claim_id: "CLM-2024-001934",
    priority: "low",
    reasons: ["manual_review_requested"],
    confidence_score: 82,
    assumption_count: 1,
    decision: "APPROVE",
    fraud_indicator_count: 0,
  },
  {
    claim_id: "CLM-2024-001941",
    priority: "medium",
    reasons: ["service_gap"],
    confidence_score: 65,
    assumption_count: 3,
    decision: "REJECT",
    fraud_indicator_count: 0,
  },
];

/**
 * Human-in-the-Loop triage queue page.
 * Displays claims requiring human review, sorted by priority.
 */
export function TriageQueuePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [items, setItems] = useState<TriageQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Parse filters from URL
  const filters: TriageQueueFilters = {
    priority: searchParams.get("priority")?.split(",").filter(Boolean) as TriagePriority[] | undefined,
    reasons: searchParams.get("reasons")?.split(",").filter(Boolean) as TriageReason[] | undefined,
    decision: searchParams.get("decision")?.split(",").filter(Boolean) as AssessmentDecision[] | undefined,
    min_confidence: searchParams.get("min_confidence") ? Number(searchParams.get("min_confidence")) : undefined,
    max_confidence: searchParams.get("max_confidence") ? Number(searchParams.get("max_confidence")) : undefined,
  };

  // Persist filters to URL
  const updateFilters = (newFilters: TriageQueueFilters) => {
    const params = new URLSearchParams();
    if (newFilters.priority?.length) params.set("priority", newFilters.priority.join(","));
    if (newFilters.reasons?.length) params.set("reasons", newFilters.reasons.join(","));
    if (newFilters.decision?.length) params.set("decision", newFilters.decision.join(","));
    if (newFilters.min_confidence !== undefined) params.set("min_confidence", String(newFilters.min_confidence));
    if (newFilters.max_confidence !== undefined) params.set("max_confidence", String(newFilters.max_confidence));
    setSearchParams(params);
  };

  useEffect(() => {
    loadQueue();
  }, [searchParams]);

  async function loadQueue(isRefresh = false) {
    if (isRefresh) {
      setIsRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const data = await getTriageQueue(filters);
      // Use mock data if API returns empty
      setItems(data.length > 0 ? data : MOCK_TRIAGE_ITEMS);
    } catch (err) {
      // On error, still show mock data for demo purposes
      console.warn("Triage queue API error, using mock data:", err);
      setItems(MOCK_TRIAGE_ITEMS);
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }

  async function handleQuickAction(claimId: string, action: "approve" | "reject" | "escalate") {
    try {
      await reviewTriageItem(claimId, action);
      // Remove from list after successful action
      setItems((prev) => prev.filter((item) => item.claim_id !== claimId));
    } catch (err) {
      console.error("Failed to process triage action:", err);
    }
  }

  function handleReview(claimId: string) {
    navigate(`/claims/explorer?claim=${claimId}`);
  }

  // Calculate stats
  const criticalCount = items.filter((i) => i.priority === "critical").length;
  const highCount = items.filter((i) => i.priority === "high").length;
  const avgConfidence = items.length > 0
    ? Math.round(items.reduce((sum, i) => sum + i.confidence_score, 0) / items.length)
    : 0;
  const fraudCount = items.filter((i) => i.fraud_indicator_count > 0).length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Users className="h-6 w-6 text-slate-500" />
            <h1 className="text-2xl font-bold text-foreground">Triage Queue</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Claims requiring human review, sorted by priority
          </p>
        </div>
        <button
          onClick={() => loadQueue(true)}
          disabled={isRefreshing}
          className={cn(
            "flex items-center gap-2 px-3 py-2 rounded-lg text-sm",
            "bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700",
            isRefreshing && "opacity-50 cursor-not-allowed"
          )}
        >
          <RefreshCw className={cn("h-4 w-4", isRefreshing && "animate-spin")} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <MetricCardRow columns={4}>
        <MetricCard
          label="Pending Review"
          value={items.length}
          subtext="claims in queue"
        />
        <MetricCard
          label="Critical + High"
          value={criticalCount + highCount}
          variant={criticalCount + highCount > 5 ? "error" : criticalCount + highCount > 0 ? "warning" : "default"}
          subtext="need attention"
        />
        <MetricCard
          label="Avg Confidence"
          value={`${avgConfidence}%`}
          variant={avgConfidence < 60 ? "warning" : "default"}
        />
        <MetricCard
          label="Fraud Flagged"
          value={fraudCount}
          variant={fraudCount > 0 ? "error" : "default"}
          subtext="potential fraud"
        />
      </MetricCardRow>

      {/* Filters */}
      <TriageFilters filters={filters} onFiltersChange={updateFilters} />

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
            <p className="text-sm text-slate-500">Loading triage queue...</p>
          </div>
        </div>
      ) : error ? (
        <div className="p-6 text-center bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800">
          <p className="text-sm text-red-600 dark:text-red-400 mb-4">{error}</p>
          <button
            onClick={() => loadQueue()}
            className="px-4 py-2 bg-slate-100 dark:bg-slate-800 rounded-lg text-sm hover:bg-slate-200 dark:hover:bg-slate-700"
          >
            Retry
          </button>
        </div>
      ) : items.length === 0 ? (
        <div className="p-8 text-center bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
          <div className="w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4">
            <Users className="h-6 w-6 text-green-600 dark:text-green-400" />
          </div>
          <h3 className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
            Queue Empty
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            No claims require human review at this time.
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
                  <th className="text-left px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Priority</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Claim</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Decision</th>
                  <th className="text-center px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Confidence</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Reasons</th>
                  <th className="text-center px-4 py-3 font-medium text-slate-600 dark:text-slate-300">Flags</th>
                  <th className="text-left px-4 py-3 font-medium text-slate-600 dark:text-slate-300 w-40">Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <TriageQueueRow
                    key={item.claim_id}
                    item={item}
                    onReview={() => handleReview(item.claim_id)}
                    onQuickApprove={() => handleQuickAction(item.claim_id, "approve")}
                    onQuickReject={() => handleQuickAction(item.claim_id, "reject")}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
