import { useState, Fragment } from "react";
import type { ClaimSummary, DocSummary } from "../types";
import type { ClaimRunInfo } from "../api/client";
import { cn } from "../lib/utils";
import { formatDocType } from "../lib/formatters";
import {
  MetricCard,
  MetricCardRow,
  LabeledBadge,
  UnlabeledBadge,
  GateStatusBadge,
  NotInRunBadge,
  NoSearchResultsEmptyState,
} from "./shared";

interface ClaimsTableProps {
  claims: ClaimSummary[];
  totalCount: number;
  selectedClaim: ClaimSummary | null;
  docs: DocSummary[];
  searchQuery: string;
  lobFilter: string;
  statusFilter: string;
  riskFilter: string;
  // Run props
  runs: ClaimRunInfo[];
  selectedRunId: string | null;
  onRunChange: (runId: string | null) => void;
  // Callbacks
  onSearchChange: (query: string) => void;
  onLobFilterChange: (lob: string) => void;
  onStatusFilterChange: (status: string) => void;
  onRiskFilterChange: (risk: string) => void;
  onSelectClaim: (claim: ClaimSummary) => void;
  onSelectDoc: (docId: string, claimId: string) => void;
  onNavigateToReview: (claimId: string) => void;
}

export function ClaimsTable({
  claims,
  totalCount,
  selectedClaim: _selectedClaim,
  docs,
  searchQuery,
  lobFilter,
  statusFilter,
  riskFilter,
  runs: _runs,
  selectedRunId: _selectedRunId,
  onRunChange: _onRunChange,
  onSearchChange,
  onLobFilterChange,
  onStatusFilterChange,
  onRiskFilterChange,
  onSelectClaim,
  onSelectDoc,
  onNavigateToReview,
}: ClaimsTableProps) {
  // Batch context now handled by BatchWorkspace
  void _selectedClaim;
  void _runs;
  void _selectedRunId;
  void _onRunChange;
  const [expandedClaim, setExpandedClaim] = useState<string | null>(null);

  // Sorting state
  type SortColumn = "claim_id" | "doc_count" | "labeled" | "gate" | "last_processed";
  const [sortColumn, setSortColumn] = useState<SortColumn>("claim_id");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  function handleSort(column: SortColumn) {
    if (sortColumn === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortColumn(column);
      setSortDirection("asc");
    }
  }

  // Sort claims
  const sortedClaims = [...claims].sort((a, b) => {
    let comparison = 0;
    switch (sortColumn) {
      case "claim_id":
        comparison = a.claim_id.localeCompare(b.claim_id);
        break;
      case "doc_count":
        comparison = a.doc_count - b.doc_count;
        break;
      case "labeled":
        comparison = a.labeled_count - b.labeled_count;
        break;
      case "gate":
        // Sort by fail count (higher = worse = later in asc)
        comparison = a.gate_fail_count - b.gate_fail_count;
        break;
      case "last_processed":
        comparison = (a.last_processed || "").localeCompare(b.last_processed || "");
        break;
    }
    return sortDirection === "asc" ? comparison : -comparison;
  });

  // Count claims in run vs not in run
  const claimsInRun = claims.filter((c) => c.in_run).length;
  const claimsNotInRun = claims.filter((c) => !c.in_run).length;

  function handleClaimClick(claim: ClaimSummary) {
    if (expandedClaim === claim.claim_id) {
      setExpandedClaim(null);
    } else {
      setExpandedClaim(claim.claim_id);
      onSelectClaim(claim);
    }
  }

  // Calculate KPIs only from claims in this run
  const claimsInRunData = claims.filter((c) => c.in_run);
  const totalDocsLabeled = claims.reduce((sum, c) => sum + c.labeled_count, 0);  // Labels are run-independent
  const totalDocs = claims.reduce((sum, c) => sum + c.doc_count, 0);
  const totalGateFail = claimsInRunData.reduce((sum, c) => sum + c.gate_fail_count, 0);  // Run-dependent

  return (
    <div className="p-6">
      {/* KPI Stats */}
      <MetricCardRow columns={4} className="mb-6">
        <MetricCard
          label="Claims"
          value={totalCount}
          subtext={claimsNotInRun > 0 ? `${claimsNotInRun} not in run` : undefined}
          variant={claimsNotInRun > 0 ? "warning" : "default"}
        />
        <MetricCard
          label="Docs labeled"
          value={`${totalDocsLabeled} / ${totalDocs}`}
          subtext="Run-independent"
        />
        <MetricCard
          label="Docs failing gate"
          value={totalGateFail}
          subtext="In selected run"
          variant={totalGateFail > 0 ? "error" : "default"}
        />
        <MetricCard
          label="Claims in run"
          value={claimsInRun}
        />
      </MetricCardRow>

      {/* Filters and Search */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          {/* Gate Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value)}
            className="px-3 py-2 bg-white border rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-200"
          >
            <option value="all">All Gate Status</option>
            <option value="has_fail">Has FAIL docs</option>
            <option value="has_warn">Has WARN docs</option>
            <option value="all_pass">All PASS</option>
          </select>

          {/* Unlabeled Filter */}
          <select
            value={lobFilter}
            onChange={(e) => onLobFilterChange(e.target.value)}
            className="px-3 py-2 bg-white border rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-200"
          >
            <option value="all">All Claims</option>
            <option value="has_unlabeled">Has unlabeled docs</option>
          </select>

          {/* Risk Filter (kept for backwards compatibility) */}
          <select
            value={riskFilter}
            onChange={(e) => onRiskFilterChange(e.target.value)}
            className="px-3 py-2 bg-white border rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-200"
          >
            <option value="all">All Priority</option>
            <option value="high">High Priority</option>
            <option value="medium">Medium Priority</option>
            <option value="low">Low Priority</option>
          </select>
        </div>

        {/* Search */}
        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <input
            type="text"
            placeholder="Search by Claim ID..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10 pr-4 py-2 w-64 bg-white border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-gray-200"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="w-10 px-4 py-3"></th>
              <th
                className="px-4 py-3 text-left text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort("claim_id")}
              >
                <div className="flex items-center gap-1">
                  Claim ID
                  <SortIcon active={sortColumn === "claim_id"} direction={sortDirection} />
                </div>
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">LOB</th>
              <th
                className="px-4 py-3 text-center text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort("doc_count")}
              >
                <div className="flex items-center justify-center gap-1">
                  Docs
                  <SortIcon active={sortColumn === "doc_count"} direction={sortDirection} />
                </div>
              </th>
              <th
                className="px-4 py-3 text-center text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort("labeled")}
              >
                <div className="flex items-center justify-center gap-1">
                  Labeled
                  <SortIcon active={sortColumn === "labeled"} direction={sortDirection} />
                </div>
              </th>
              <th
                className="px-4 py-3 text-center text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort("gate")}
                title="Extraction Gate (Run): PASS/WARN/FAIL based on required fields presence, evidence quality, and extraction errors for the selected run"
              >
                <div className="flex items-center justify-center gap-1">
                  Extraction Gate
                  <SortIcon active={sortColumn === "gate"} direction={sortDirection} />
                </div>
              </th>
              <th
                className="px-4 py-3 text-right text-sm font-medium text-gray-700 cursor-pointer hover:bg-gray-100"
                onClick={() => handleSort("last_processed")}
              >
                <div className="flex items-center justify-end gap-1">
                  Last processed
                  <SortIcon active={sortColumn === "last_processed"} direction={sortDirection} />
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedClaims.map((claim) => (
              <Fragment key={claim.claim_id}>
                <tr
                  onClick={() => handleClaimClick(claim)}
                  className={cn(
                    "border-b cursor-pointer hover:bg-gray-50 transition-colors",
                    expandedClaim === claim.claim_id && "bg-gray-50",
                    !claim.in_run && "opacity-60"
                  )}
                >
                  <td className="px-4 py-3">
                    <button className="text-gray-400 hover:text-gray-600">
                      <svg
                        className={cn(
                          "w-4 h-4 transition-transform",
                          expandedClaim === claim.claim_id && "rotate-90"
                        )}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                    </button>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">{claim.claim_id}</span>
                      {!claim.in_run && <NotInRunBadge />}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <LobBadge lob={claim.lob} />
                  </td>
                  <td className="px-4 py-3 text-center text-gray-900">
                    {claim.doc_count}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={cn(
                      "text-sm",
                      claim.labeled_count === claim.doc_count ? "text-green-600" : "text-gray-600"
                    )}>
                      {claim.labeled_count}/{claim.doc_count}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    {claim.in_run ? (
                      <GateSummary
                        pass={claim.gate_pass_count}
                        warn={claim.gate_warn_count}
                        fail={claim.gate_fail_count}
                      />
                    ) : (
                      <span className="text-gray-400">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-gray-500 text-sm">
                    {claim.in_run ? (claim.last_processed || "-") : "-"}
                  </td>
                </tr>

                {/* Expanded docs row - Document Pack Queue */}
                {expandedClaim === claim.claim_id && (
                  <tr>
                    <td colSpan={7} className="bg-gray-50 border-b">
                      <div className="px-6 py-4">
                        {/* Document Pack Header */}
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <h4 className="text-sm font-semibold text-gray-900">Document Pack</h4>
                            <p className="text-xs text-gray-500">
                              {claim.doc_count} documents &middot; {claim.labeled_count} labeled &middot; {claim.gate_fail_count} fail
                            </p>
                          </div>
                          {docs.length > 0 && docs.some(d => !d.has_labels) && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onNavigateToReview(claim.claim_id);
                              }}
                              className="px-3 py-1.5 bg-gray-900 text-white text-xs font-medium rounded hover:bg-gray-800 transition-colors"
                            >
                              Review next unlabeled
                            </button>
                          )}
                        </div>
                        {docs.length === 0 ? (
                          <p className="text-sm text-gray-500">Loading documents...</p>
                        ) : (
                          <div className="space-y-2">
                            {/* Sort docs: Unlabeled first, then FAIL > WARN > PASS */}
                            {[...docs].sort((a, b) => {
                              // Unlabeled first
                              if (!a.has_labels && b.has_labels) return -1;
                              if (a.has_labels && !b.has_labels) return 1;
                              // Then by gate status: FAIL > WARN > PASS
                              const statusOrder = { fail: 0, warn: 1, pass: 2 };
                              const aStatus = a.quality_status || "pass";
                              const bStatus = b.quality_status || "pass";
                              const aOrder = statusOrder[aStatus as keyof typeof statusOrder] ?? 2;
                              const bOrder = statusOrder[bStatus as keyof typeof statusOrder] ?? 2;
                              return aOrder - bOrder;
                            }).map((doc) => (
                              <button
                                key={doc.doc_id}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onSelectDoc(doc.doc_id, claim.claim_id);
                                }}
                                className="w-full flex items-center justify-between p-3 bg-white rounded-lg border hover:border-gray-300 transition-colors text-left"
                              >
                                <div className="flex items-center gap-3">
                                  <QualityDot status={doc.quality_status} />
                                  <div>
                                    <div className="text-sm font-medium text-gray-900">
                                      {doc.filename}
                                    </div>
                                    <div className="text-xs text-gray-500">
                                      {formatDocType(doc.doc_type)} &middot; {Math.round(doc.confidence * 100)}%
                                    </div>
                                    {doc.missing_required_fields && doc.missing_required_fields.length > 0 && (
                                      <div className="text-xs text-red-600 mt-0.5">
                                        Missing: {doc.missing_required_fields.join(", ")}
                                      </div>
                                    )}
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  {/* Gate Badge */}
                                  {doc.quality_status && <GateStatusBadge status={doc.quality_status as "pass" | "warn" | "fail"} />}
                                  {/* Labeled/Unlabeled Badge */}
                                  {doc.has_labels ? <LabeledBadge /> : <UnlabeledBadge />}
                                  <svg
                                    className="w-4 h-4 text-gray-400"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                  >
                                    <path
                                      strokeLinecap="round"
                                      strokeLinejoin="round"
                                      strokeWidth={2}
                                      d="M9 5l7 7-7 7"
                                    />
                                  </svg>
                                </div>
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>

        {claims.length === 0 && <NoSearchResultsEmptyState />}
      </div>
    </div>
  );
}

function SortIcon({ active, direction }: { active: boolean; direction: "asc" | "desc" }) {
  if (!active) {
    return (
      <svg className="w-4 h-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
      </svg>
    );
  }
  // Show single arrow for active sort
  return (
    <svg className="w-4 h-4 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      {direction === "asc" ? (
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      )}
    </svg>
  );
}

function LobBadge({ lob }: { lob: string }) {
  const isMotor = lob === "MOTOR";
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-gray-700">
      {isMotor ? (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h8m-8 5h8m-4 8c-4.418 0-8-1.79-8-4v-1a4 4 0 014-4h8a4 4 0 014 4v1c0 2.21-3.582 4-8 4z" />
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
        </svg>
      )}
      {lob}
    </span>
  );
}

function GateSummary({ pass, warn, fail }: { pass: number; warn: number; fail: number }) {
  return (
    <div className="flex items-center gap-1 text-xs">
      {pass > 0 && (
        <span className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded">
          {pass} PASS
        </span>
      )}
      {warn > 0 && (
        <span className="px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded">
          {warn} WARN
        </span>
      )}
      {fail > 0 && (
        <span className="px-1.5 py-0.5 bg-red-100 text-red-700 rounded">
          {fail} FAIL
        </span>
      )}
      {pass === 0 && warn === 0 && fail === 0 && (
        <span className="text-gray-400">-</span>
      )}
    </div>
  );
}

function QualityDot({ status }: { status: string | null }) {
  const colors: Record<string, string> = {
    pass: "bg-green-500",
    warn: "bg-yellow-500",
    fail: "bg-red-500",
  };

  return (
    <span
      className={cn(
        "w-2 h-2 rounded-full",
        status ? colors[status] || "bg-gray-300" : "bg-gray-300"
      )}
    />
  );
}

