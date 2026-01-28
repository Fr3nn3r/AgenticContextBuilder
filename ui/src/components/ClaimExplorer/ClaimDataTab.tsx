import { useState, useEffect, useCallback } from "react";
import {
  Loader2,
  Database,
  FileText,
  ExternalLink,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import type {
  ClaimSummary,
  DocSummary,
  ClaimFacts,
  ClaimRunManifest,
  ReconciliationReport,
  AggregatedFact,
} from "../../types";
import { cn, formatFieldName } from "../../lib/utils";
import {
  getClaimRunsForClaim,
  getClaimFactsByRun,
  getReconciliationReport,
} from "../../api/client";
import { ClaimRunSelector } from "./ClaimRunSelector";
import { ReconciliationStatusCard } from "./ReconciliationStatusCard";
import { ConflictsList } from "./ConflictsList";

interface ClaimWithDocs extends ClaimSummary {
  documents?: DocSummary[];
}

interface ClaimDataTabProps {
  claim: ClaimWithDocs;
  onDocumentClick?: (docId: string) => void;
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null,
    highlightText?: string,
    highlightValue?: string
  ) => void;
}

/**
 * Data tab showing reconciliation results including gate status,
 * conflicts, and all aggregated facts with provenance.
 */
export function ClaimDataTab({
  claim,
  onDocumentClick,
  onViewSource,
}: ClaimDataTabProps) {
  // Claim runs state
  const [claimRuns, setClaimRuns] = useState<ClaimRunManifest[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runsLoading, setRunsLoading] = useState(true);

  // Data for selected run
  const [report, setReport] = useState<ReconciliationReport | null>(null);
  const [facts, setFacts] = useState<ClaimFacts | null>(null);
  const [dataLoading, setDataLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load claim runs on mount
  useEffect(() => {
    async function loadRuns() {
      setRunsLoading(true);
      setError(null);
      try {
        const runs = await getClaimRunsForClaim(claim.claim_id);
        setClaimRuns(runs);
        // Auto-select the latest run
        if (runs.length > 0) {
          setSelectedRunId(runs[0].claim_run_id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load claim runs");
      } finally {
        setRunsLoading(false);
      }
    }
    loadRuns();
  }, [claim.claim_id]);

  // Load data for selected run
  useEffect(() => {
    async function loadRunData() {
      if (!selectedRunId) return;

      setDataLoading(true);
      setError(null);
      try {
        const [reportData, factsData] = await Promise.all([
          getReconciliationReport(claim.claim_id, selectedRunId),
          getClaimFactsByRun(claim.claim_id, selectedRunId),
        ]);
        setReport(reportData);
        setFacts(factsData);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load run data");
      } finally {
        setDataLoading(false);
      }
    }
    loadRunData();
  }, [claim.claim_id, selectedRunId]);

  // Handle run selection
  const handleRunSelect = useCallback((runId: string) => {
    setSelectedRunId(runId);
  }, []);

  // Handle view source (simplify for doc click)
  const handleViewDoc = useCallback(
    (docId: string) => {
      if (onDocumentClick) {
        onDocumentClick(docId);
      } else if (onViewSource) {
        onViewSource(docId, null, null, null);
      }
    },
    [onDocumentClick, onViewSource]
  );

  // Loading state
  if (runsLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading claim runs...</p>
        </div>
      </div>
    );
  }

  // No runs available
  if (claimRuns.length === 0) {
    return (
      <div className="p-4">
        <div className="bg-card rounded-lg border border-border p-8 text-center">
          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
            <Database className="h-6 w-6 text-muted-foreground" />
          </div>
          <h3 className="text-sm font-medium text-foreground mb-1">
            No Claim Runs
          </h3>
          <p className="text-xs text-muted-foreground">
            Run the reconciliation pipeline to generate claim data.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {/* Claim Run Selector */}
      <ClaimRunSelector
        runs={claimRuns}
        selectedRunId={selectedRunId}
        onSelect={handleRunSelect}
        loading={dataLoading}
      />

      {/* Error state */}
      {error && (
        <div className="bg-destructive/10 border border-destructive/30 rounded-lg p-4">
          <p className="text-sm text-destructive">{error}</p>
        </div>
      )}

      {/* Loading state for data */}
      {dataLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Content */}
      {!dataLoading && selectedRunId && (
        <div className="space-y-4">
          {/* Reconciliation Status Card */}
          {report?.gate && (
            <ReconciliationStatusCard
              gate={report.gate}
              factCount={report.fact_count}
            />
          )}

          {/* No report fallback */}
          {!report && (
            <div className="bg-muted/50 rounded-lg border border-border p-4">
              <p className="text-sm text-muted-foreground text-center">
                No reconciliation report available for this run.
              </p>
            </div>
          )}

          {/* Conflicts List */}
          {report?.conflicts && report.conflicts.length > 0 && (
            <ConflictsList
              conflicts={report.conflicts}
              onViewSource={handleViewDoc}
            />
          )}

          {/* All Facts */}
          {facts && facts.facts.length > 0 && (
            <FactsPanel
              facts={facts.facts}
              sources={facts.sources}
              onViewSource={onViewSource}
            />
          )}

          {/* No facts fallback */}
          {(!facts || facts.facts.length === 0) && !report && (
            <div className="bg-card rounded-lg border border-border p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
                <FileText className="h-6 w-6 text-muted-foreground" />
              </div>
              <h3 className="text-sm font-medium text-foreground mb-1">
                No Data Available
              </h3>
              <p className="text-xs text-muted-foreground">
                This claim run has no reconciliation data.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Facts Panel - Groups facts by doc_type
// =============================================================================

interface FactsPanelProps {
  facts: AggregatedFact[];
  sources: Array<{ doc_id: string; doc_type: string; filename: string }>;
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null,
    highlightText?: string,
    highlightValue?: string
  ) => void;
}

function FactsPanel({ facts, sources, onViewSource }: FactsPanelProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set(["all"]));

  // Group facts by doc_type from their selected_from provenance
  const factsByDocType = new Map<string, AggregatedFact[]>();

  facts.forEach((fact) => {
    const docType = fact.selected_from?.doc_type || "unknown";
    if (!factsByDocType.has(docType)) {
      factsByDocType.set(docType, []);
    }
    factsByDocType.get(docType)!.push(fact);
  });

  // Convert to array and sort by doc_type
  const groups = Array.from(factsByDocType.entries()).sort(([a], [b]) =>
    a.localeCompare(b)
  );

  const toggleGroup = (docType: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(docType)) {
        next.delete(docType);
      } else {
        next.add(docType);
      }
      return next;
    });
  };

  return (
    <div className="bg-card rounded-lg border border-border overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-muted/50">
        <div className="flex items-center gap-2">
          <Database className="h-4 w-4 text-muted-foreground" />
          <h3 className="font-semibold text-foreground">
            All Facts
          </h3>
          <span className="text-xs text-muted-foreground">
            ({facts.length} facts from {groups.length} document types)
          </span>
        </div>
      </div>

      {/* Groups */}
      <div className="divide-y divide-border">
        {groups.map(([docType, groupFacts]) => {
          const isExpanded = expandedGroups.has(docType) || expandedGroups.has("all");
          const source = sources.find((s) => s.doc_type === docType);

          return (
            <div key={docType}>
              {/* Group Header */}
              <button
                onClick={() => toggleGroup(docType)}
                className="w-full px-4 py-2 flex items-center gap-2 hover:bg-muted transition-colors"
              >
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                )}
                <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <span className="font-medium text-sm text-foreground">
                  {docType.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-muted-foreground">
                  ({groupFacts.length} facts)
                </span>
                {source && (
                  <span className="text-xs text-muted-foreground/70 ml-auto truncate max-w-[200px]">
                    {source.filename}
                  </span>
                )}
              </button>

              {/* Facts */}
              {isExpanded && (
                <div className="px-4 pb-3 pl-10">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1">
                    {groupFacts.map((fact) => (
                      <FactRow
                        key={fact.name}
                        fact={fact}
                        onViewSource={onViewSource}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// =============================================================================
// Fact Row - Single fact display
// =============================================================================

interface FactRowProps {
  fact: AggregatedFact;
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null,
    highlightText?: string,
    highlightValue?: string
  ) => void;
}

function FactRow({ fact, onViewSource }: FactRowProps) {
  const hasSource = fact.selected_from?.doc_id;

  // Format value for display
  const displayValue = Array.isArray(fact.value)
    ? fact.value.join(", ")
    : fact.value !== null && fact.value !== undefined
      ? String(fact.value)
      : "—";

  const handleClick = () => {
    if (onViewSource && fact.selected_from) {
      onViewSource(
        fact.selected_from.doc_id,
        fact.selected_from.page,
        fact.selected_from.char_start,
        fact.selected_from.char_end,
        fact.selected_from.text_quote ?? undefined,
        displayValue !== "—" ? displayValue : undefined
      );
    }
  };

  // Truncate long values
  const truncatedValue =
    displayValue.length > 50 ? displayValue.slice(0, 47) + "..." : displayValue;

  return (
    <div
      className={cn(
        "flex items-center gap-2 py-1 px-2 rounded transition-colors",
        hasSource && onViewSource
          ? "hover:bg-muted cursor-pointer"
          : ""
      )}
      onClick={hasSource ? handleClick : undefined}
      title={displayValue}
    >
      <span className="text-xs text-muted-foreground min-w-[120px] flex-shrink-0">
        {formatFieldName(fact.name)}
      </span>
      <span className="text-sm text-foreground truncate flex-1">
        {truncatedValue}
      </span>
      {hasSource && onViewSource && (
        <ExternalLink className="h-3 w-3 text-muted-foreground/50 flex-shrink-0" />
      )}
    </div>
  );
}
