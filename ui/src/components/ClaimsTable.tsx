import { useState, Fragment } from "react";
import { useNavigate } from "react-router-dom";
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
import { useClaims } from "../context/ClaimsContext";
import { useFilters } from "../context/FilterContext";
import { useBatch } from "../context/BatchContext";

interface ClaimsTableProps {
  /** If true, shows all claims instead of filtered claims */
  showAllClaims?: boolean;
}

export function ClaimsTable({ showAllClaims = false }: ClaimsTableProps) {
  const navigate = useNavigate();

  // Get data from contexts
  const { claims, filteredClaims, docs, selectClaim, loading, error, refreshClaims } = useClaims();
  const { selectedRunId: _selectedRunId } = useBatch();
  void _selectedRunId; // No longer used - documents now link directly to Document Detail
  const {
    searchQuery,
    lobFilter,
    statusFilter,
    riskFilter,
    setSearchQuery,
    setLobFilter,
    setStatusFilter,
    setRiskFilter,
  } = useFilters();

  // Use filtered or all claims based on prop
  const displayClaims = showAllClaims ? claims : filteredClaims;
  const totalCount = claims.length;

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
  const sortedClaims = [...displayClaims].sort((a, b) => {
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
        comparison = a.gate_fail_count - b.gate_fail_count;
        break;
      case "last_processed":
        comparison = (a.last_processed || "").localeCompare(b.last_processed || "");
        break;
    }
    return sortDirection === "asc" ? comparison : -comparison;
  });

  // Count claims in run vs not in run
  const claimsInRun = displayClaims.filter((c) => c.in_run).length;
  const claimsNotInRun = displayClaims.filter((c) => !c.in_run).length;

  function handleClaimClick(claim: typeof claims[0]) {
    if (expandedClaim === claim.claim_id) {
      setExpandedClaim(null);
    } else {
      setExpandedClaim(claim.claim_id);
      selectClaim(claim);
    }
  }

  function handleSelectDoc(docId: string, claimId: string) {
    // Navigate directly to Document Detail page
    navigate(`/documents/${claimId}/${docId}`);
  }

  function handleNavigateToReview(claimId: string) {
    navigate(`/claims/${claimId}/review`);
  }

  // Calculate KPIs
  const claimsInRunData = displayClaims.filter((c) => c.in_run);
  const totalDocsLabeled = displayClaims.reduce((sum, c) => sum + c.labeled_count, 0);
  const totalDocs = displayClaims.reduce((sum, c) => sum + c.doc_count, 0);
  const totalGateFail = claimsInRunData.reduce((sum, c) => sum + c.gate_fail_count, 0);

  // Handle loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-full p-6">
        <div className="text-muted-foreground">Loading claims...</div>
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6">
        <p className="text-destructive mb-4">{error}</p>
        <button
          onClick={refreshClaims}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          Retry
        </button>
      </div>
    );
  }

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
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 bg-card border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-muted"
          >
            <option value="all">All Gate Status</option>
            <option value="has_fail">Has FAIL docs</option>
            <option value="has_warn">Has WARN docs</option>
            <option value="all_pass">All PASS</option>
          </select>

          <select
            value={lobFilter}
            onChange={(e) => setLobFilter(e.target.value)}
            className="px-3 py-2 bg-card border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-muted"
          >
            <option value="all">All Claims</option>
            <option value="has_unlabeled">Has unlabeled docs</option>
          </select>

          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="px-3 py-2 bg-card border rounded-lg text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-muted"
          >
            <option value="all">All Priority</option>
            <option value="high">High Priority</option>
            <option value="medium">Medium Priority</option>
            <option value="low">Low Priority</option>
          </select>
        </div>

        <div className="relative">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground/70"
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
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 pr-4 py-2 w-64 bg-card border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-muted"
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-card rounded-lg border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/50">
              <th className="w-10 px-4 py-3"></th>
              <th
                className="px-4 py-3 text-left text-sm font-medium text-foreground cursor-pointer hover:bg-muted"
                onClick={() => handleSort("claim_id")}
              >
                <div className="flex items-center gap-1">
                  Claim ID
                  <SortIcon active={sortColumn === "claim_id"} direction={sortDirection} />
                </div>
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-foreground">LOB</th>
              <th
                className="px-4 py-3 text-center text-sm font-medium text-foreground cursor-pointer hover:bg-muted"
                onClick={() => handleSort("doc_count")}
              >
                <div className="flex items-center justify-center gap-1">
                  Docs
                  <SortIcon active={sortColumn === "doc_count"} direction={sortDirection} />
                </div>
              </th>
              <th
                className="px-4 py-3 text-center text-sm font-medium text-foreground cursor-pointer hover:bg-muted"
                onClick={() => handleSort("labeled")}
              >
                <div className="flex items-center justify-center gap-1">
                  Labeled
                  <SortIcon active={sortColumn === "labeled"} direction={sortDirection} />
                </div>
              </th>
              <th
                className="px-4 py-3 text-center text-sm font-medium text-foreground cursor-pointer hover:bg-muted"
                onClick={() => handleSort("gate")}
                title="Extraction Gate (Run): PASS/WARN/FAIL based on required fields presence, evidence quality, and extraction errors for the selected run"
              >
                <div className="flex items-center justify-center gap-1">
                  Extraction Gate
                  <SortIcon active={sortColumn === "gate"} direction={sortDirection} />
                </div>
              </th>
              <th
                className="px-4 py-3 text-right text-sm font-medium text-foreground cursor-pointer hover:bg-muted"
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
                  data-testid={`claim-row-${claim.claim_id}`}
                  onClick={() => handleClaimClick(claim)}
                  className={cn(
                    "border-b cursor-pointer hover:bg-muted/50 transition-colors",
                    expandedClaim === claim.claim_id && "bg-muted/50",
                    !claim.in_run && "opacity-60"
                  )}
                >
                  <td className="px-4 py-3">
                    <button className="text-muted-foreground/70 hover:text-muted-foreground">
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
                      <span className="font-medium text-foreground">{claim.claim_id}</span>
                      {!claim.in_run && <NotInRunBadge />}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <LobBadge lob={claim.lob} />
                  </td>
                  <td className="px-4 py-3 text-center text-foreground">
                    {claim.doc_count}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span className={cn(
                      "text-sm",
                      claim.labeled_count === claim.doc_count ? "text-success" : "text-muted-foreground"
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
                      <span className="text-muted-foreground/70">-</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-muted-foreground text-sm">
                    {claim.in_run ? (claim.last_processed || "-") : "-"}
                  </td>
                </tr>

                {/* Expanded docs row */}
                {expandedClaim === claim.claim_id && (
                  <tr>
                    <td colSpan={7} className="bg-muted/50 border-b">
                      <div className="px-6 py-4">
                        <div className="flex items-center justify-between mb-3">
                          <div>
                            <h4 className="text-sm font-semibold text-foreground">Document Pack</h4>
                            <p className="text-xs text-muted-foreground">
                              {claim.doc_count} documents &middot; {claim.labeled_count} labeled &middot; {claim.gate_fail_count} fail
                            </p>
                          </div>
                          {docs.length > 0 && docs.some(d => !d.has_labels) && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleNavigateToReview(claim.claim_id);
                              }}
                              className="px-3 py-1.5 bg-primary text-white text-xs font-medium rounded hover:bg-primary/90 transition-colors"
                            >
                              Review next unlabeled
                            </button>
                          )}
                        </div>
                        {docs.length === 0 ? (
                          <p className="text-sm text-muted-foreground">Loading documents...</p>
                        ) : (
                          <div className="space-y-2">
                            {[...docs].sort((a, b) => {
                              if (!a.has_labels && b.has_labels) return -1;
                              if (a.has_labels && !b.has_labels) return 1;
                              const statusOrder = { fail: 0, warn: 1, pass: 2 };
                              const aOrder = statusOrder[(a.quality_status || "pass") as keyof typeof statusOrder] ?? 2;
                              const bOrder = statusOrder[(b.quality_status || "pass") as keyof typeof statusOrder] ?? 2;
                              return aOrder - bOrder;
                            }).map((doc) => (
                              <button
                                key={doc.doc_id}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSelectDoc(doc.doc_id, claim.claim_id);
                                }}
                                className="w-full flex items-center justify-between p-3 bg-card rounded-lg border hover:border-border transition-colors text-left"
                              >
                                <div className="flex items-center gap-3">
                                  <QualityDot status={doc.quality_status} />
                                  <div>
                                    <div className="text-sm font-medium text-foreground">
                                      {doc.filename}
                                    </div>
                                    <div className="text-xs text-muted-foreground">
                                      {formatDocType(doc.doc_type)} &middot; {Math.round(doc.confidence * 100)}%
                                    </div>
                                    {doc.missing_required_fields && doc.missing_required_fields.length > 0 && (
                                      <div className="text-xs text-destructive mt-0.5">
                                        Missing: {doc.missing_required_fields.join(", ")}
                                      </div>
                                    )}
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  {doc.quality_status && <GateStatusBadge status={doc.quality_status as "pass" | "warn" | "fail"} />}
                                  {doc.has_labels ? <LabeledBadge /> : <UnlabeledBadge />}
                                  <svg className="w-4 h-4 text-muted-foreground/70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
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

        {displayClaims.length === 0 && <NoSearchResultsEmptyState />}
      </div>
    </div>
  );
}

function SortIcon({ active, direction }: { active: boolean; direction: "asc" | "desc" }) {
  if (!active) {
    return (
      <svg className="w-4 h-4 text-muted-foreground/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
      </svg>
    );
  }
  return (
    <svg className="w-4 h-4 text-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
    <span className="inline-flex items-center gap-1.5 text-sm text-foreground">
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
      {pass > 0 && <span className="px-1.5 py-0.5 bg-success/10 text-success rounded">{pass} PASS</span>}
      {warn > 0 && <span className="px-1.5 py-0.5 bg-warning/10 text-warning-foreground rounded">{warn} WARN</span>}
      {fail > 0 && <span className="px-1.5 py-0.5 bg-destructive/10 text-destructive rounded">{fail} FAIL</span>}
      {pass === 0 && warn === 0 && fail === 0 && <span className="text-muted-foreground/70">-</span>}
    </div>
  );
}

function QualityDot({ status }: { status: string | null }) {
  const colors: Record<string, string> = { pass: "bg-success", warn: "bg-warning", fail: "bg-destructive" };
  return <span className={cn("w-2 h-2 rounded-full", status ? colors[status] || "bg-gray-300" : "bg-gray-300")} />;
}
