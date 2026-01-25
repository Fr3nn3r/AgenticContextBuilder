import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2,
  Play,
  ClipboardCheck,
  CheckCircle2,
  XCircle,
  ArrowRightCircle,
  Users,
  RefreshCw,
  ChevronRight,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { formatTimestamp } from "../../lib/formatters";
import type { ClaimSummary, AssessmentDecision } from "../../types";
import { listClaims } from "../../api/client";
import { MetricCard, MetricCardRow, StatusBadge, ScoreBadge } from "../shared";

interface AssessmentRunSummary {
  run_id: string;
  timestamp: string;
  claims_count: number;
  approved_count: number;
  rejected_count: number;
  referred_count: number;
  avg_confidence: number;
  status: "running" | "completed" | "failed";
}

interface ClaimAssessmentStatus extends ClaimSummary {
  hasAssessment: boolean;
  decision?: AssessmentDecision;
  confidence?: number;
  lastAssessedAt?: string;
}

// =====================
// MOCK DATA - Claims with Assessment Status
// =====================
const MOCK_CLAIMS_WITH_STATUS: ClaimAssessmentStatus[] = [
  {
    claim_id: "CLM-2024-001847",
    doc_count: 8,
    created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    hasAssessment: true,
    decision: "REFER_TO_HUMAN",
    confidence: 72,
    lastAssessedAt: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  },
  {
    claim_id: "CLM-2024-001892",
    doc_count: 5,
    created_at: new Date(Date.now() - 4 * 24 * 60 * 60 * 1000).toISOString(),
    hasAssessment: true,
    decision: "APPROVE",
    confidence: 89,
    lastAssessedAt: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
  },
  {
    claim_id: "CLM-2024-001903",
    doc_count: 6,
    created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
    hasAssessment: false,
  },
  {
    claim_id: "CLM-2024-001915",
    doc_count: 4,
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    hasAssessment: true,
    decision: "REJECT",
    confidence: 91,
    lastAssessedAt: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
  },
  {
    claim_id: "CLM-2024-001928",
    doc_count: 7,
    created_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
    hasAssessment: false,
  },
  {
    claim_id: "CLM-2024-001934",
    doc_count: 3,
    created_at: new Date(Date.now() - 18 * 60 * 60 * 1000).toISOString(),
    hasAssessment: false,
  },
];

// =====================
// MOCK DATA - Run History
// =====================
const MOCK_RUN_HISTORY: AssessmentRunSummary[] = [
  {
    run_id: "run-20240115-143022",
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    claims_count: 4,
    approved_count: 2,
    rejected_count: 1,
    referred_count: 1,
    avg_confidence: 78,
    status: "completed",
  },
  {
    run_id: "run-20240114-091545",
    timestamp: new Date(Date.now() - 26 * 60 * 60 * 1000).toISOString(),
    claims_count: 6,
    approved_count: 3,
    rejected_count: 2,
    referred_count: 1,
    avg_confidence: 71,
    status: "completed",
  },
  {
    run_id: "run-20240113-164230",
    timestamp: new Date(Date.now() - 50 * 60 * 60 * 1000).toISOString(),
    claims_count: 3,
    approved_count: 1,
    rejected_count: 1,
    referred_count: 1,
    avg_confidence: 65,
    status: "completed",
  },
];

/**
 * Assessment Console for batch assessment operations.
 * Lists claims, allows bulk selection, and displays run history.
 */
export function AssessmentConsolePage() {
  const navigate = useNavigate();

  // Claims state
  const [claims, setClaims] = useState<ClaimAssessmentStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selection state
  const [selectedClaimIds, setSelectedClaimIds] = useState<Set<string>>(new Set());

  // Run state
  const [isRunning, setIsRunning] = useState(false);
  const [runHistory, setRunHistory] = useState<AssessmentRunSummary[]>(MOCK_RUN_HISTORY);

  // Load claims on mount
  useEffect(() => {
    loadClaims();
  }, []);

  async function loadClaims() {
    setLoading(true);
    setError(null);
    try {
      const data = await listClaims();
      if (data.length > 0) {
        // Enrich with assessment status from API
        const enriched: ClaimAssessmentStatus[] = data.map((c) => ({
          ...c,
          hasAssessment: false, // Will be populated from API
        }));
        setClaims(enriched);
      } else {
        // Use mock data if API returns empty
        setClaims(MOCK_CLAIMS_WITH_STATUS);
      }
    } catch (err) {
      // On error, still show mock data for demo purposes
      console.warn("Claims API error, using mock data:", err);
      setClaims(MOCK_CLAIMS_WITH_STATUS);
    } finally {
      setLoading(false);
    }
  }

  // Selection handlers
  const toggleClaim = (claimId: string) => {
    setSelectedClaimIds((prev) => {
      const next = new Set(prev);
      if (next.has(claimId)) {
        next.delete(claimId);
      } else {
        next.add(claimId);
      }
      return next;
    });
  };

  const selectAll = () => {
    setSelectedClaimIds(new Set(claims.map((c) => c.claim_id)));
  };

  const selectNone = () => {
    setSelectedClaimIds(new Set());
  };

  const selectWithoutAssessment = () => {
    setSelectedClaimIds(new Set(claims.filter((c) => !c.hasAssessment).map((c) => c.claim_id)));
  };

  // Run assessment
  const handleRunAssessment = async () => {
    if (selectedClaimIds.size === 0) return;

    setIsRunning(true);
    try {
      // TODO: Call API to run batch assessment
      // await runBatchAssessment(Array.from(selectedClaimIds));
      console.log("Running assessment for claims:", Array.from(selectedClaimIds));
      await new Promise((resolve) => setTimeout(resolve, 3000)); // Simulate

      // Add to history (mock)
      const newRun: AssessmentRunSummary = {
        run_id: `run-${Date.now()}`,
        timestamp: new Date().toISOString(),
        claims_count: selectedClaimIds.size,
        approved_count: Math.floor(selectedClaimIds.size * 0.6),
        rejected_count: Math.floor(selectedClaimIds.size * 0.2),
        referred_count: Math.floor(selectedClaimIds.size * 0.2),
        avg_confidence: 75,
        status: "completed",
      };
      setRunHistory((prev) => [newRun, ...prev]);

      // Clear selection
      setSelectedClaimIds(new Set());

      // Reload claims
      await loadClaims();
    } finally {
      setIsRunning(false);
    }
  };

  // Stats
  const totalClaims = claims.length;
  const assessedClaims = claims.filter((c) => c.hasAssessment).length;
  const pendingClaims = totalClaims - assessedClaims;

  if (loading && claims.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
          <p className="text-sm text-slate-500">Loading claims...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <ClipboardCheck className="h-6 w-6 text-slate-500" />
            <h1 className="text-2xl font-bold text-foreground">Assessment Console</h1>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Run automated assessments on claims and review results
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/triage")}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/30"
          >
            <Users className="h-4 w-4" />
            Triage Queue
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            onClick={loadClaims}
            disabled={loading}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm",
              "bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700",
              loading && "opacity-50 cursor-not-allowed"
            )}
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            Refresh
          </button>
        </div>
      </div>

      {/* Stats */}
      <MetricCardRow columns={4}>
        <MetricCard
          label="Total Claims"
          value={totalClaims}
          subtext="in workspace"
        />
        <MetricCard
          label="Assessed"
          value={assessedClaims}
          subtext="have assessment"
          variant={assessedClaims === totalClaims ? "success" : "default"}
        />
        <MetricCard
          label="Pending"
          value={pendingClaims}
          subtext="need assessment"
          variant={pendingClaims > 0 ? "warning" : "success"}
        />
        <MetricCard
          label="Selected"
          value={selectedClaimIds.size}
          subtext="for this run"
          variant={selectedClaimIds.size > 0 ? "info" : "default"}
        />
      </MetricCardRow>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Claims Selection */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Select Claims
            </h3>
            <div className="flex items-center gap-2">
              <button
                onClick={selectAll}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                All
              </button>
              <span className="text-slate-300 dark:text-slate-600">|</span>
              <button
                onClick={selectNone}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                None
              </button>
              <span className="text-slate-300 dark:text-slate-600">|</span>
              <button
                onClick={selectWithoutAssessment}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                Pending Only
              </button>
            </div>
          </div>

          <div className="max-h-[400px] overflow-y-auto">
            {error ? (
              <div className="p-4 text-center text-red-600 dark:text-red-400">{error}</div>
            ) : claims.length === 0 ? (
              <div className="p-8 text-center text-slate-500">No claims found</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-50 dark:bg-slate-800/50">
                  <tr className="border-b border-slate-200 dark:border-slate-700">
                    <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300 w-10">
                      <input
                        type="checkbox"
                        checked={selectedClaimIds.size === claims.length && claims.length > 0}
                        onChange={(e) => e.target.checked ? selectAll() : selectNone()}
                        className="rounded"
                      />
                    </th>
                    <th className="text-left px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Claim ID</th>
                    <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Docs</th>
                    <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Status</th>
                    <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Decision</th>
                    <th className="text-center px-4 py-2 font-medium text-slate-600 dark:text-slate-300">Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {claims.map((claim) => (
                    <tr
                      key={claim.claim_id}
                      onClick={() => toggleClaim(claim.claim_id)}
                      className={cn(
                        "border-b border-slate-100 dark:border-slate-800 cursor-pointer transition-colors",
                        selectedClaimIds.has(claim.claim_id)
                          ? "bg-blue-50 dark:bg-blue-900/20"
                          : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
                      )}
                    >
                      <td className="px-4 py-2">
                        <input
                          type="checkbox"
                          checked={selectedClaimIds.has(claim.claim_id)}
                          onChange={() => toggleClaim(claim.claim_id)}
                          onClick={(e) => e.stopPropagation()}
                          className="rounded"
                        />
                      </td>
                      <td className="px-4 py-2 font-mono text-xs">{claim.claim_id}</td>
                      <td className="px-4 py-2 text-center text-slate-500">{claim.doc_count}</td>
                      <td className="px-4 py-2 text-center">
                        {claim.hasAssessment ? (
                          <StatusBadge variant="success" size="sm">Assessed</StatusBadge>
                        ) : (
                          <StatusBadge variant="neutral" size="sm">Pending</StatusBadge>
                        )}
                      </td>
                      <td className="px-4 py-2 text-center">
                        {claim.decision ? (
                          <DecisionBadge decision={claim.decision} />
                        ) : (
                          <span className="text-slate-400">-</span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-center">
                        {claim.confidence !== undefined ? (
                          <ScoreBadge value={claim.confidence} />
                        ) : (
                          <span className="text-slate-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Run Button */}
          <div className="px-4 py-3 border-t border-slate-200 dark:border-slate-700 flex items-center justify-between">
            <span className="text-sm text-slate-500">
              {selectedClaimIds.size} claim{selectedClaimIds.size !== 1 ? "s" : ""} selected
            </span>
            <button
              onClick={handleRunAssessment}
              disabled={isRunning || selectedClaimIds.size === 0}
              className={cn(
                "flex items-center gap-2 px-4 py-2 rounded-lg font-medium",
                "bg-blue-600 text-white hover:bg-blue-700",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "transition-colors"
              )}
            >
              {isRunning ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Run Assessment
                </>
              )}
            </button>
          </div>
        </div>

        {/* Run History */}
        <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-700">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-200">
              Recent Runs
            </h3>
          </div>

          <div className="max-h-[400px] overflow-y-auto">
            {runHistory.length === 0 ? (
              <div className="p-8 text-center text-slate-500 text-sm">
                No assessment runs yet
              </div>
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {runHistory.map((run) => (
                  <div key={run.run_id} className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-xs text-slate-600 dark:text-slate-300">
                        {run.run_id}
                      </span>
                      <StatusBadge
                        variant={run.status === "completed" ? "success" : run.status === "failed" ? "error" : "info"}
                        size="sm"
                      >
                        {run.status}
                      </StatusBadge>
                    </div>
                    <p className="text-xs text-slate-500 mb-2">
                      {formatTimestamp(run.timestamp)}
                    </p>
                    <div className="flex items-center gap-3 text-xs">
                      <span className="text-slate-500">{run.claims_count} claims</span>
                      <span className="text-green-600">{run.approved_count} approved</span>
                      <span className="text-red-600">{run.rejected_count} rejected</span>
                      <span className="text-amber-600">{run.referred_count} referred</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DecisionBadge({ decision }: { decision: AssessmentDecision }) {
  switch (decision) {
    case "APPROVE":
      return (
        <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400">
          <CheckCircle2 className="h-3.5 w-3.5" />
          <span className="text-xs">Approve</span>
        </span>
      );
    case "REJECT":
      return (
        <span className="inline-flex items-center gap-1 text-red-600 dark:text-red-400">
          <XCircle className="h-3.5 w-3.5" />
          <span className="text-xs">Reject</span>
        </span>
      );
    case "REFER_TO_HUMAN":
      return (
        <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400">
          <ArrowRightCircle className="h-3.5 w-3.5" />
          <span className="text-xs">Refer</span>
        </span>
      );
  }
}
