import { useState, useMemo, useCallback } from "react";
import type { DashboardClaim } from "../../types";
import { DashboardClaimDetail } from "./DashboardClaimDetail";
import { GroundTruthDocPanel } from "./GroundTruthDocPanel";

interface DashboardTableProps {
  claims: DashboardClaim[];
}

type SortKey =
  | "claim_id"
  | "dataset"
  | "claim_date"
  | "decision"
  | "result_code"
  | "confidence"
  | "payout"
  | "gt_decision"
  | "decision_match";

type SortDir = "asc" | "desc";

function parseDate(d: string | null): number {
  if (!d) return 0;
  const parts = d.split(/[./]/);
  if (parts.length === 3) {
    const [day, month, year] = parts;
    return new Date(Number(year), Number(month) - 1, Number(day)).getTime();
  }
  return new Date(d).getTime() || 0;
}

/** Format the "Rationale" column based on decision and check results. */
function formatRationale(claim: DashboardClaim): React.ReactNode {
  const d = claim.decision?.toUpperCase();
  if (d === "APPROVE" || d === "APPROVED") {
    const total = claim.checks_passed + claim.checks_failed + claim.checks_inconclusive;
    if (total === 0) return <span className="text-slate-400">N/A</span>;
    const parts: string[] = [];
    parts.push(`${claim.checks_passed} passed`);
    if (claim.checks_inconclusive > 0) {
      parts.push(`${claim.checks_inconclusive} skipped`);
    }
    return (
      <span className="text-slate-600 dark:text-slate-400">{parts.join(", ")}</span>
    );
  }
  // For rejected/refer, show the result_code (denial reason)
  if (claim.result_code && claim.result_code !== "Rejected" && claim.result_code !== "Refer to human") {
    return <span>{claim.result_code}</span>;
  }
  return <span className="text-slate-400">N/A</span>;
}

export function DashboardTable({ claims }: DashboardTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("claim_id");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [gtDocClaimId, setGtDocClaimId] = useState<string | null>(null);

  const handleSort = useCallback(
    (key: SortKey) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey]
  );

  const sorted = useMemo(() => {
    const compare = (a: DashboardClaim, b: DashboardClaim): number => {
      let va: string | number | boolean | null;
      let vb: string | number | boolean | null;

      switch (sortKey) {
        case "claim_id":
          va = Number(a.claim_id) || a.claim_id;
          vb = Number(b.claim_id) || b.claim_id;
          break;
        case "dataset":
          va = a.dataset_label || "";
          vb = b.dataset_label || "";
          break;
        case "claim_date":
          va = parseDate(a.claim_date);
          vb = parseDate(b.claim_date);
          break;
        case "decision":
          va = a.decision || "";
          vb = b.decision || "";
          break;
        case "result_code":
          va = a.result_code || "";
          vb = b.result_code || "";
          break;
        case "confidence":
          va = a.confidence ?? -1;
          vb = b.confidence ?? -1;
          break;
        case "payout":
          va = a.payout ?? -1;
          vb = b.payout ?? -1;
          break;
        case "gt_decision":
          va = a.gt_decision || "";
          vb = b.gt_decision || "";
          break;
        case "decision_match":
          va = a.decision_match === true ? 1 : a.decision_match === false ? 0 : -1;
          vb = b.decision_match === true ? 1 : b.decision_match === false ? 0 : -1;
          break;
        default:
          return 0;
      }

      if (va === vb) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (va < vb) return sortDir === "asc" ? -1 : 1;
      return sortDir === "asc" ? 1 : -1;
    };

    return [...claims].sort(compare);
  }, [claims, sortKey, sortDir]);

  const SortHeader = ({
    label,
    sortKeyName,
    className = "",
  }: {
    label: string;
    sortKeyName: SortKey;
    className?: string;
  }) => (
    <th
      onClick={() => handleSort(sortKeyName)}
      className={`py-2 px-2 font-medium text-slate-600 dark:text-slate-300 cursor-pointer hover:text-slate-900 dark:hover:text-slate-100 select-none ${className}`}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {sortKey === sortKeyName && (
          <span className="text-primary">{sortDir === "asc" ? "\u2191" : "\u2193"}</span>
        )}
      </span>
    </th>
  );

  const decisionBadge = (decision: string | null) => {
    if (!decision) return null;
    const d = decision.toUpperCase();
    const color =
      d === "APPROVE" || d === "APPROVED"
        ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
        : d === "REJECT" || d === "DENIED"
          ? "bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300"
          : "bg-amber-50 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300";
    const label =
      d === "APPROVE" || d === "APPROVED"
        ? "APPROVE"
        : d === "REJECT" || d === "DENIED"
          ? "REJECT"
          : "REFER";
    return (
      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${color}`}>
        {label}
      </span>
    );
  };

  const confidenceColor = (c: number | null) => {
    if (c == null) return "";
    if (c >= 80) return "text-slate-700 dark:text-slate-300";
    if (c >= 60) return "text-amber-600 dark:text-amber-400";
    return "text-rose-600 dark:text-rose-400";
  };

  return (
    <>
      <div className="bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 text-xs">
                <SortHeader label="Claim ID" sortKeyName="claim_id" className="text-left" />
                <SortHeader label="Dataset" sortKeyName="dataset" className="text-left" />
                <SortHeader label="Date" sortKeyName="claim_date" className="text-left" />
                <SortHeader label="Decision" sortKeyName="decision" className="text-center" />
                <SortHeader label="Rationale" sortKeyName="result_code" className="text-left" />
                <SortHeader label="Conf." sortKeyName="confidence" className="text-right" />
                <SortHeader label="Payout (CHF)" sortKeyName="payout" className="text-right" />
                <SortHeader label="GT Decision" sortKeyName="gt_decision" className="text-center" />
                <SortHeader label="Match" sortKeyName="decision_match" className="text-center" />
                <th className="py-2 px-2 font-medium text-slate-600 dark:text-slate-300 text-left text-xs">
                  Run ID
                </th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((claim) => (
                <TableRow
                  key={claim.claim_id}
                  claim={claim}
                  isExpanded={expandedId === claim.claim_id}
                  onToggle={() =>
                    setExpandedId(
                      expandedId === claim.claim_id ? null : claim.claim_id
                    )
                  }
                  onViewGtDoc={() => setGtDocClaimId(claim.claim_id)}
                  decisionBadge={decisionBadge}
                  confidenceColor={confidenceColor}
                />
              ))}
            </tbody>
          </table>
        </div>
        {sorted.length === 0 && (
          <div className="flex items-center justify-center py-12 text-sm text-slate-500 dark:text-slate-400">
            No claims match your filters.
          </div>
        )}
      </div>

      {gtDocClaimId && (
        <GroundTruthDocPanel
          claimId={gtDocClaimId}
          onClose={() => setGtDocClaimId(null)}
        />
      )}
    </>
  );
}

function TableRow({
  claim,
  isExpanded,
  onToggle,
  onViewGtDoc,
  decisionBadge,
  confidenceColor,
}: {
  claim: DashboardClaim;
  isExpanded: boolean;
  onToggle: () => void;
  onViewGtDoc: () => void;
  decisionBadge: (d: string | null) => React.ReactNode;
  confidenceColor: (c: number | null) => string;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopyRunId = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (claim.claim_run_id) {
      navigator.clipboard.writeText(claim.claim_run_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  return (
    <>
      <tr
        onClick={onToggle}
        className={`border-b border-slate-100 dark:border-slate-700/50 cursor-pointer transition-colors ${
          isExpanded
            ? "bg-primary/5 dark:bg-primary/10"
            : "hover:bg-slate-50 dark:hover:bg-slate-800/50"
        }`}
      >
        <td className="py-2 px-2">
          <span className="inline-flex items-center gap-1.5">
            <span className="text-[10px] text-slate-400">
              {isExpanded ? "\u25BC" : "\u25B6"}
            </span>
            <span className="font-semibold text-slate-900 dark:text-slate-100 text-sm tracking-tight">
              {claim.claim_id}
            </span>
          </span>
        </td>
        <td className="py-2 px-2 text-slate-500 dark:text-slate-400 text-xs">
          {claim.dataset_label || "-"}
        </td>
        <td className="py-2 px-2 text-slate-600 dark:text-slate-300 text-xs">
          {claim.claim_date || "-"}
        </td>
        <td className="py-2 px-2 text-center">{decisionBadge(claim.decision)}</td>
        <td className="py-2 px-2 text-xs max-w-[200px] truncate">
          {formatRationale(claim)}
        </td>
        <td
          className={`py-2 px-2 text-right font-mono text-xs ${confidenceColor(claim.confidence)}`}
        >
          {claim.confidence != null ? `${claim.confidence.toFixed(0)}%` : "-"}
        </td>
        <td className="py-2 px-2 text-right font-mono text-xs text-slate-700 dark:text-slate-200">
          {claim.payout != null ? claim.payout.toFixed(2) : "-"}
        </td>
        <td className="py-2 px-2 text-center">
          {claim.gt_decision ? (
            <span className="inline-flex items-center gap-1">
              {decisionBadge(claim.gt_decision)}
              {claim.has_ground_truth_doc && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onViewGtDoc();
                  }}
                  className="text-[10px] text-primary hover:underline ml-1"
                  title="View decision letter"
                >
                  PDF
                </button>
              )}
            </span>
          ) : (
            "-"
          )}
        </td>
        <td className="py-2 px-2 text-center">
          {claim.decision_match === true ? (
            <span className="text-emerald-600 dark:text-emerald-400 font-bold" title="Match">
              &#10003;
            </span>
          ) : claim.decision_match === false ? (
            <span className="text-rose-600 dark:text-rose-400 font-bold" title="Mismatch">
              &#10007;
            </span>
          ) : (
            <span className="text-slate-400">-</span>
          )}
        </td>
        <td className="py-2 px-2 text-xs font-mono max-w-[140px]">
          {claim.claim_run_id ? (
            <span className="inline-flex items-center gap-1">
              <span
                className="text-slate-500 dark:text-slate-400 truncate"
                title={claim.claim_run_id}
              >
                {claim.claim_run_id.slice(0, 16)}...
              </span>
              <button
                onClick={handleCopyRunId}
                className="p-0.5 rounded hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 flex-shrink-0"
                title={copied ? "Copied!" : "Copy run ID"}
              >
                {copied ? (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                  </svg>
                )}
              </button>
            </span>
          ) : (
            <span className="text-slate-400">-</span>
          )}
        </td>
      </tr>
      {isExpanded && (
        <tr>
          <td colSpan={10} className="p-0">
            <div className="px-4 py-3">
              <DashboardClaimDetail claimId={claim.claim_id} />
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
