import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { listDecisions } from "../../api/client";
import type { DecisionRecord, DecisionType } from "../../types";

const DECISION_TYPES: { value: DecisionType | ""; label: string }[] = [
  { value: "", label: "All Types" },
  { value: "classification", label: "Classification" },
  { value: "extraction", label: "Extraction" },
  { value: "human_review", label: "Human Review" },
  { value: "override", label: "Override" },
];

export function ComplianceLedger() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [decisions, setDecisions] = useState<DecisionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters from URL
  const typeFilter = (searchParams.get("type") || "") as DecisionType | "";
  const claimFilter = searchParams.get("claim") || "";
  const docFilter = searchParams.get("doc") || "";

  useEffect(() => {
    loadDecisions();
  }, [typeFilter, claimFilter, docFilter]);

  async function loadDecisions() {
    try {
      setLoading(true);
      setError(null);
      const data = await listDecisions({
        decision_type: typeFilter || undefined,
        claim_id: claimFilter || undefined,
        doc_id: docFilter || undefined,
        limit: 100,
      });
      setDecisions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load decisions");
    } finally {
      setLoading(false);
    }
  }

  function updateFilter(key: string, value: string) {
    const params = new URLSearchParams(searchParams);
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    setSearchParams(params);
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">Decision Ledger</h1>
          <p className="text-muted-foreground mt-1">
            Browse all logged AI decisions with full audit trail
          </p>
        </div>
        <Link
          to="/compliance"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back to Overview
        </Link>
      </div>

      {/* Filters */}
      <div className="bg-card border border-border rounded-lg p-4">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-muted-foreground mb-1">
              Decision Type
            </label>
            <select
              value={typeFilter}
              onChange={(e) => updateFilter("type", e.target.value)}
              className="w-full px-3 py-2 bg-background border border-input rounded-md text-foreground"
            >
              {DECISION_TYPES.map((dt) => (
                <option key={dt.value} value={dt.value}>
                  {dt.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-muted-foreground mb-1">
              Claim ID
            </label>
            <input
              type="text"
              value={claimFilter}
              onChange={(e) => updateFilter("claim", e.target.value)}
              placeholder="Filter by claim..."
              className="w-full px-3 py-2 bg-background border border-input rounded-md text-foreground placeholder:text-muted-foreground"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-muted-foreground mb-1">
              Document ID
            </label>
            <input
              type="text"
              value={docFilter}
              onChange={(e) => updateFilter("doc", e.target.value)}
              placeholder="Filter by doc..."
              className="w-full px-3 py-2 bg-background border border-input rounded-md text-foreground placeholder:text-muted-foreground"
            />
          </div>
        </div>
      </div>

      {/* Results */}
      {error ? (
        <div className="bg-destructive/10 text-destructive p-4 rounded-lg">{error}</div>
      ) : loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-muted-foreground">Loading decisions...</div>
        </div>
      ) : decisions.length === 0 ? (
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          <p className="text-muted-foreground">No decisions found matching filters</p>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <table className="w-full">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Timestamp
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Claim
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Document
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Actor
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Confidence
                </th>
                <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                  Hash Chain
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {decisions.map((decision) => (
                <tr
                  key={decision.decision_id}
                  className="hover:bg-muted/30 cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <DecisionTypeBadge type={decision.decision_type} />
                  </td>
                  <td className="px-4 py-3 text-sm text-foreground">
                    {formatTimestamp(decision.timestamp)}
                  </td>
                  <td className="px-4 py-3 text-sm text-foreground">
                    {decision.claim_id || "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-foreground font-mono">
                    {decision.doc_id ? `${decision.doc_id.slice(0, 12)}...` : "—"}
                  </td>
                  <td className="px-4 py-3 text-sm text-foreground">
                    {decision.actor_type === "system" ? (
                      <span className="text-muted-foreground">System</span>
                    ) : (
                      decision.actor_id || "—"
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm">
                    {decision.rationale?.confidence != null ? (
                      <span
                        className={
                          decision.rationale.confidence >= 0.8
                            ? "text-green-500"
                            : decision.rationale.confidence >= 0.5
                            ? "text-yellow-500"
                            : "text-red-500"
                        }
                      >
                        {(decision.rationale.confidence * 100).toFixed(0)}%
                      </span>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-sm font-mono text-muted-foreground">
                    {decision.prev_hash || "genesis"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Stats footer */}
      {!loading && !error && (
        <div className="text-sm text-muted-foreground">
          Showing {decisions.length} decision{decisions.length !== 1 ? "s" : ""}
        </div>
      )}
    </div>
  );
}

function DecisionTypeBadge({ type }: { type: DecisionType }) {
  const colors: Record<DecisionType, string> = {
    classification: "bg-blue-500/10 text-blue-500",
    extraction: "bg-green-500/10 text-green-500",
    human_review: "bg-purple-500/10 text-purple-500",
    override: "bg-orange-500/10 text-orange-500",
  };

  return (
    <span
      className={`inline-flex px-2 py-1 rounded text-xs font-medium capitalize ${colors[type]}`}
    >
      {type.replace("_", " ")}
    </span>
  );
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleString();
}

export default ComplianceLedger;
