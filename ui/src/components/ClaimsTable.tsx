import { useState } from "react";
import type { ClaimSummary, DocSummary } from "../types";
import { cn } from "../lib/utils";

interface ClaimsTableProps {
  claims: ClaimSummary[];
  totalCount: number;
  selectedClaim: ClaimSummary | null;
  docs: DocSummary[];
  searchQuery: string;
  lobFilter: string;
  statusFilter: string;
  riskFilter: string;
  onSearchChange: (query: string) => void;
  onLobFilterChange: (lob: string) => void;
  onStatusFilterChange: (status: string) => void;
  onRiskFilterChange: (risk: string) => void;
  onSelectClaim: (claim: ClaimSummary) => void;
  onSelectDoc: (docId: string) => void;
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
  onSearchChange,
  onLobFilterChange,
  onStatusFilterChange,
  onRiskFilterChange,
  onSelectClaim,
  onSelectDoc,
}: ClaimsTableProps) {
  void _selectedClaim; // Used for future features
  const [expandedClaim, setExpandedClaim] = useState<string | null>(null);

  function handleClaimClick(claim: ClaimSummary) {
    if (expandedClaim === claim.claim_id) {
      setExpandedClaim(null);
    } else {
      setExpandedClaim(claim.claim_id);
      onSelectClaim(claim);
    }
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-semibold text-gray-900">Claims Review</h2>
        <p className="text-gray-500">{totalCount} claims</p>
      </div>

      {/* Filters and Search */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          {/* LOB Filter */}
          <select
            value={lobFilter}
            onChange={(e) => onLobFilterChange(e.target.value)}
            className="px-3 py-2 bg-white border rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-200"
          >
            <option value="all">All LOB</option>
            <option value="MOTOR">MOTOR</option>
            <option value="HOME">HOME</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value)}
            className="px-3 py-2 bg-white border rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-200"
          >
            <option value="all">All Status</option>
            <option value="Not Reviewed">Not Reviewed</option>
            <option value="Reviewed">Reviewed</option>
          </select>

          {/* Risk Filter */}
          <select
            value={riskFilter}
            onChange={(e) => onRiskFilterChange(e.target.value)}
            className="px-3 py-2 bg-white border rounded-lg text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-200"
          >
            <option value="all">All Risk</option>
            <option value="high">High Risk (50+)</option>
            <option value="medium">Medium Risk (25-49)</option>
            <option value="low">Low Risk (&lt;25)</option>
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
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                <div className="flex items-center gap-1">
                  Claim ID
                  <SortIcon />
                </div>
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">LOB</th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">
                <div className="flex items-center gap-1">
                  Risk Score
                  <SortIcon />
                </div>
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Loss Type</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">Amount</th>
              <th className="px-4 py-3 text-center text-sm font-medium text-gray-700">Flags</th>
              <th className="px-4 py-3 text-center text-sm font-medium text-gray-700">Status</th>
              <th className="px-4 py-3 text-right text-sm font-medium text-gray-700">
                <div className="flex items-center justify-end gap-1">
                  Closed
                  <SortIcon />
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <>
                <tr
                  key={claim.claim_id}
                  onClick={() => handleClaimClick(claim)}
                  className={cn(
                    "border-b cursor-pointer hover:bg-gray-50 transition-colors",
                    expandedClaim === claim.claim_id && "bg-gray-50"
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
                    <span className="font-medium text-gray-900">{claim.claim_id}</span>
                  </td>
                  <td className="px-4 py-3">
                    <LobBadge lob={claim.lob} />
                  </td>
                  <td className="px-4 py-3">
                    <RiskScore score={claim.risk_score} />
                  </td>
                  <td className="px-4 py-3 text-gray-700">{claim.loss_type}</td>
                  <td className="px-4 py-3 text-right text-gray-900">
                    {claim.amount ? formatCurrency(claim.amount, claim.currency) : "-"}
                  </td>
                  <td className="px-4 py-3 text-center">
                    {claim.flags_count > 0 && (
                      <span className="inline-flex items-center gap-1 text-amber-600">
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path
                            fillRule="evenodd"
                            d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                            clipRule="evenodd"
                          />
                        </svg>
                        {claim.flags_count}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge status={claim.status} />
                  </td>
                  <td className="px-4 py-3 text-right text-gray-500 text-sm">
                    {claim.closed_date || "-"}
                  </td>
                </tr>

                {/* Expanded docs row */}
                {expandedClaim === claim.claim_id && (
                  <tr>
                    <td colSpan={9} className="bg-gray-50 border-b">
                      <div className="px-6 py-4">
                        <h4 className="text-sm font-medium text-gray-700 mb-3">
                          Documents ({claim.doc_count})
                        </h4>
                        {docs.length === 0 ? (
                          <p className="text-sm text-gray-500">Loading documents...</p>
                        ) : (
                          <div className="space-y-2">
                            {docs.map((doc) => (
                              <button
                                key={doc.doc_id}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onSelectDoc(doc.doc_id);
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
                                      {doc.doc_type} &middot; {doc.language.toUpperCase()}
                                      {doc.confidence > 0 && ` &middot; ${Math.round(doc.confidence * 100)}% confidence`}
                                    </div>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  {doc.has_extraction && (
                                    <span className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded">
                                      Extracted
                                    </span>
                                  )}
                                  {doc.has_labels && (
                                    <span className="text-xs px-2 py-1 bg-green-50 text-green-700 rounded">
                                      Labeled
                                    </span>
                                  )}
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
              </>
            ))}
          </tbody>
        </table>

        {claims.length === 0 && (
          <div className="py-12 text-center text-gray-500">
            No claims found matching your filters.
          </div>
        )}
      </div>
    </div>
  );
}

function SortIcon() {
  return (
    <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
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

function RiskScore({ score }: { score: number }) {
  // Color based on score
  let barColor = "bg-green-500";
  if (score >= 50) {
    barColor = "bg-orange-500";
  } else if (score >= 25) {
    barColor = "bg-yellow-500";
  }

  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={cn("h-full rounded-full", barColor)}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
      <span className="text-sm font-medium text-gray-900 w-8">{score}</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const isReviewed = status === "Reviewed";
  return (
    <span
      className={cn(
        "inline-flex px-2 py-1 text-xs font-medium rounded",
        isReviewed
          ? "bg-green-100 text-green-800"
          : "text-gray-600"
      )}
    >
      {status}
    </span>
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

function formatCurrency(amount: number, currency: string): string {
  const symbol = currency === "USD" ? "$" : currency === "EUR" ? "€" : "£";
  return `${symbol}${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
