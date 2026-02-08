import { useState, useEffect, useCallback } from "react";
import { cn } from "../lib/utils";
import {
  listClaims,
  getDecisionDossier,
  listDossierVersions,
  getDossierVersion,
  evaluateDecision,
  getDenialClauses,
} from "../api/client";
import {
  PageLoadingSkeleton,
  NoDataEmptyState,
  ErrorEmptyState,
} from "../components/shared";
import {
  DossierHeader,
  AssumptionsPanel,
  ClauseEvaluationTable,
  LineItemDecisionsTable,
  FinancialSummaryCard,
} from "../components/decision";
import type {
  ClaimSummary,
  DecisionDossier,
  DossierVersionMeta,
  DenialClauseDefinition,
} from "../types";

type TabId = "clauses" | "items" | "financial";

export function DecisionDossierPage() {
  const [claims, setClaims] = useState<ClaimSummary[]>([]);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [dossier, setDossier] = useState<DecisionDossier | null>(null);
  const [versions, setVersions] = useState<DossierVersionMeta[]>([]);
  const [clauses, setClauses] = useState<DenialClauseDefinition[]>([]);
  const [assumptions, setAssumptions] = useState<Record<string, boolean>>({});
  const [activeTab, setActiveTab] = useState<TabId>("clauses");
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load claims on mount
  const loadClaims = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [claimsList, clausesList] = await Promise.all([
        listClaims(),
        getDenialClauses().catch(() => [] as DenialClauseDefinition[]),
      ]);
      setClaims(claimsList);
      setClauses(clausesList);

      // Auto-select first claim if available
      if (claimsList.length > 0 && !selectedClaimId) {
        setSelectedClaimId(claimsList[0].claim_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load claims");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadClaims();
  }, [loadClaims]);

  // Load dossier when claim changes
  const loadDossier = useCallback(
    async (claimId: string) => {
      try {
        setLoading(true);
        setError(null);

        const [dossierData, versionsData] = await Promise.all([
          getDecisionDossier(claimId),
          listDossierVersions(claimId).catch(
            () => [] as DossierVersionMeta[]
          ),
        ]);

        setDossier(dossierData);
        setVersions(versionsData);

        // Initialize assumptions from dossier
        const newAssumptions: Record<string, boolean> = {};
        for (const a of dossierData.assumptions_used) {
          newAssumptions[a.clause_reference] = a.assumed_value;
        }
        setAssumptions(newAssumptions);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load decision dossier"
        );
        setDossier(null);
        setVersions([]);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (selectedClaimId) {
      loadDossier(selectedClaimId);
    }
  }, [selectedClaimId, loadDossier]);

  // Handle version change
  const handleVersionChange = useCallback(
    async (version: number) => {
      if (!selectedClaimId) return;
      try {
        setLoading(true);
        setError(null);
        const dossierData = await getDossierVersion(
          selectedClaimId,
          version
        );
        setDossier(dossierData);

        // Update assumptions from the loaded version
        const newAssumptions: Record<string, boolean> = {};
        for (const a of dossierData.assumptions_used) {
          newAssumptions[a.clause_reference] = a.assumed_value;
        }
        setAssumptions(newAssumptions);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load dossier version"
        );
      } finally {
        setLoading(false);
      }
    },
    [selectedClaimId]
  );

  // Handle assumption toggle
  const handleAssumptionChange = useCallback(
    (clauseRef: string, value: boolean) => {
      setAssumptions((prev) => ({
        ...prev,
        [clauseRef]: value,
      }));
    },
    []
  );

  // Handle re-run with current assumptions
  const handleRerun = useCallback(async () => {
    if (!selectedClaimId) return;
    try {
      setEvaluating(true);
      setError(null);
      const result = await evaluateDecision(selectedClaimId, assumptions);
      setDossier(result);

      // Refresh versions list
      const versionsData = await listDossierVersions(selectedClaimId).catch(
        () => [] as DossierVersionMeta[]
      );
      setVersions(versionsData);

      // Update assumptions from result
      const newAssumptions: Record<string, boolean> = {};
      for (const a of result.assumptions_used) {
        newAssumptions[a.clause_reference] = a.assumed_value;
      }
      setAssumptions(newAssumptions);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to evaluate decision"
      );
    } finally {
      setEvaluating(false);
    }
  }, [selectedClaimId, assumptions]);

  // Tabs configuration
  const tabs: { id: TabId; label: string }[] = [
    { id: "clauses", label: "Clause Audit" },
    { id: "items", label: "Line Items" },
    { id: "financial", label: "Financial Summary" },
  ];

  // Show loading state on initial load (before claims are loaded)
  if (loading && claims.length === 0 && !error) {
    return <PageLoadingSkeleton message="Loading Decision Dossier..." />;
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header bar */}
      <div className="bg-card border-b border-border px-4 py-3 flex items-center gap-4 flex-shrink-0">
        <h2 className="font-semibold text-foreground">Decision Dossier</h2>

        {/* Claim selector */}
        <div className="flex items-center gap-2">
          <label className="text-sm text-muted-foreground">Claim:</label>
          <select
            value={selectedClaimId || ""}
            onChange={(e) => setSelectedClaimId(e.target.value || null)}
            className="text-sm border border-border rounded-md px-2 py-1.5 bg-background text-foreground min-w-[180px]"
          >
            <option value="">Select a claim...</option>
            {claims.map((c) => (
              <option key={c.claim_id} value={c.claim_id}>
                {c.claim_id} ({c.doc_count} docs)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-4 mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-destructive hover:text-destructive/80 ml-2"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {!selectedClaimId ? (
          <NoDataEmptyState />
        ) : loading ? (
          <PageLoadingSkeleton message="Loading dossier..." />
        ) : !dossier ? (
          <ErrorEmptyState
            message="No decision dossier found for this claim. Run the decision engine first."
            onRetry={() => selectedClaimId && loadDossier(selectedClaimId)}
          />
        ) : (
          <>
            {/* Dossier Header */}
            <DossierHeader
              dossier={dossier}
              versions={versions}
              onVersionChange={handleVersionChange}
              onRerun={handleRerun}
              loading={evaluating}
            />

            {/* Assumptions Panel (collapsible) */}
            <AssumptionsPanel
              assumptions={dossier.assumptions_used}
              clauses={clauses}
              onAssumptionChange={handleAssumptionChange}
            />

            {/* Tabs */}
            <div className="border-b border-border">
              <nav className="flex gap-0">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                      activeTab === tab.id
                        ? "border-primary text-primary"
                        : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
                    )}
                  >
                    {tab.label}
                    {tab.id === "clauses" && (
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        ({dossier.clause_evaluations.length})
                      </span>
                    )}
                    {tab.id === "items" && (
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        ({dossier.line_item_decisions.length})
                      </span>
                    )}
                  </button>
                ))}
              </nav>
            </div>

            {/* Tab content */}
            <div>
              {activeTab === "clauses" && (
                <ClauseEvaluationTable
                  evaluations={dossier.clause_evaluations}
                />
              )}
              {activeTab === "items" && (
                <LineItemDecisionsTable
                  items={dossier.line_item_decisions}
                />
              )}
              {activeTab === "financial" && (
                <FinancialSummaryCard summary={dossier.financial_summary} />
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
