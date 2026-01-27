import { useState, useEffect, useCallback } from "react";
import { LayoutDashboard, FileText, ClipboardCheck, History, AlertTriangle, Database } from "lucide-react";
import { cn } from "../../lib/utils";
import type { ClaimSummary, DocSummary, ClaimFacts, ClaimAssessment } from "../../types";
import { getClaimFacts, getClaimAssessment, getAssessmentHistory } from "../../api/client";
import { ClaimContextBar } from "./ClaimContextBar";
import { ClaimOverviewTab } from "./ClaimOverviewTab";
import { ClaimFactsTab } from "./ClaimFactsTab";
import { ClaimAssessmentTab } from "./ClaimAssessmentTab";
import { ClaimAssumptionsTab } from "./ClaimAssumptionsTab";
import { ClaimHistoryTab, type AssessmentHistoryEntry } from "./ClaimHistoryTab";
import { ClaimDataTab } from "./ClaimDataTab";
import { DocumentSlidePanel, type EvidenceLocation } from "./DocumentSlidePanel";

interface ClaimWithDocs extends ClaimSummary {
  documents?: DocSummary[];
}

interface ClaimSummaryTabProps {
  claim: ClaimWithDocs;
  onDocumentClick?: (docId: string) => void;
  onViewSource?: (docId: string, page: number | null, charStart: number | null, charEnd: number | null) => void;
}

type SubTab = "overview" | "facts" | "assessment" | "assumptions" | "history" | "data";

const SUB_TABS: { id: SubTab; label: string; icon: typeof FileText }[] = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "facts", label: "Facts", icon: FileText },
  { id: "assessment", label: "Assessment", icon: ClipboardCheck },
  { id: "assumptions", label: "Assumptions", icon: AlertTriangle },
  { id: "history", label: "History", icon: History },
  { id: "data", label: "Data", icon: Database },
];

/**
 * Main claim view with sub-tabs for Overview, Facts, Assessment, and History.
 * Overview is the default landing tab showing decision readiness and attention items.
 */
export function ClaimSummaryTab({ claim, onDocumentClick, onViewSource }: ClaimSummaryTabProps) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("overview");

  // Data state
  const [claimFacts, setClaimFacts] = useState<ClaimFacts | null>(null);
  const [assessment, setAssessment] = useState<ClaimAssessment | null>(null);
  const [history, setHistory] = useState<AssessmentHistoryEntry[]>([]);

  // Document slide panel state
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceLocation | null>(null);

  // Loading state
  const [factsLoading, setFactsLoading] = useState(true);
  const [assessmentLoading, setAssessmentLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(true);

  // Error state
  const [factsError, setFactsError] = useState<string | null>(null);
  const [assessmentError, setAssessmentError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // Load facts
  useEffect(() => {
    async function loadFacts() {
      setFactsLoading(true);
      setFactsError(null);
      try {
        const facts = await getClaimFacts(claim.claim_id);
        setClaimFacts(facts);
      } catch (err) {
        setFactsError(err instanceof Error ? err.message : "Failed to load facts");
      } finally {
        setFactsLoading(false);
      }
    }
    loadFacts();
  }, [claim.claim_id]);

  // Load assessment from real backend API
  useEffect(() => {
    async function loadAssessment() {
      setAssessmentLoading(true);
      setAssessmentError(null);
      try {
        const data = await getClaimAssessment(claim.claim_id);
        setAssessment(data); // Will be null if no assessment exists
      } catch (err) {
        console.warn("Assessment API error:", err);
        setAssessmentError(err instanceof Error ? err.message : "Failed to load assessment");
        setAssessment(null);
      } finally {
        setAssessmentLoading(false);
      }
    }
    loadAssessment();
  }, [claim.claim_id]);

  // Load history from real backend API
  useEffect(() => {
    async function loadHistory() {
      setHistoryLoading(true);
      setHistoryError(null);
      try {
        const data = await getAssessmentHistory(claim.claim_id);
        setHistory(data);
      } catch (err) {
        console.warn("History API error:", err);
        setHistoryError(err instanceof Error ? err.message : "Failed to load history");
        setHistory([]);
      } finally {
        setHistoryLoading(false);
      }
    }
    // Wait for assessment to load first
    if (!assessmentLoading) {
      loadHistory();
    }
  }, [claim.claim_id, assessmentLoading]);

  // Refresh assessment data (for re-run callback)
  const handleRefreshAssessment = useCallback(async () => {
    setAssessmentLoading(true);
    setAssessmentError(null);
    try {
      const data = await getClaimAssessment(claim.claim_id);
      setAssessment(data);
    } catch (err) {
      console.warn("Assessment refresh error:", err);
      setAssessmentError(err instanceof Error ? err.message : "Failed to load assessment");
      setAssessment(null);
    } finally {
      setAssessmentLoading(false);
    }
  }, [claim.claim_id]);

  // Refresh history data (for re-run callback)
  const handleRefreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError(null);
    try {
      const data = await getAssessmentHistory(claim.claim_id);
      setHistory(data);
    } catch (err) {
      console.warn("History refresh error:", err);
      setHistoryError(err instanceof Error ? err.message : "Failed to load history");
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [claim.claim_id]);

  // Handle viewing source document with evidence highlighting
  const handleViewSource = (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null
  ) => {
    setSelectedEvidence({ docId, page, charStart, charEnd });
  };

  // Handle clicking a document (without specific evidence location)
  const handleDocumentClick = (docId: string) => {
    setSelectedEvidence({ docId, page: 1, charStart: null, charEnd: null });
  };

  // Handle closing the document panel
  const handleClosePanel = () => {
    setSelectedEvidence(null);
  };

  // Handle running assessment
  const handleRunAssessment = async () => {
    // TODO: Implement API call to run assessment
    // await runAssessment(claim.claim_id);
    // Then reload assessment
    console.log("Running assessment for claim:", claim.claim_id);
    // For now, just simulate
    await new Promise((resolve) => setTimeout(resolve, 2000));
    // Reload assessment after running
    setAssessmentLoading(true);
    try {
      const data = await getClaimAssessment(claim.claim_id);
      setAssessment(data);
    } catch (err) {
      setAssessmentError(err instanceof Error ? err.message : "Failed to load assessment");
    } finally {
      setAssessmentLoading(false);
    }
  };

  const handleExport = () => {
    console.log("Export claim:", claim.claim_id);
    // TODO: Implement export action
  };

  // Badge counts for tabs
  const assumptionCount = assessment?.assumptions.length || 0;
  const criticalAssumptions = assessment?.assumptions.filter((a) => a.impact === "high").length || 0;
  const failedChecks = assessment?.checks.filter((c) => c.result === "FAIL").length || 0;

  return (
    <div className="h-full overflow-hidden bg-muted/50 flex flex-col">
      {/* Sticky Context Bar */}
      <ClaimContextBar
        claim={claim}
        facts={claimFacts}
        assessment={assessment}
        onExport={handleExport}
      />

      {/* Sub-Tab Navigation */}
      <div className="bg-card border-b border-border px-4">
        <div className="flex gap-1">
          {SUB_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeSubTab === tab.id;

            // Badge logic
            let badge: React.ReactNode = null;
            if (tab.id === "assessment" && failedChecks > 0) {
              badge = (
                <span className="ml-1.5 px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-destructive/10 text-destructive">
                  {failedChecks}
                </span>
              );
            } else if (tab.id === "assumptions" && criticalAssumptions > 0) {
              badge = (
                <span className="ml-1.5 px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-destructive/10 text-destructive">
                  {criticalAssumptions}
                </span>
              );
            } else if (tab.id === "assumptions" && assumptionCount > 0) {
              badge = (
                <span className="ml-1.5 px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-warning/10 text-warning">
                  {assumptionCount}
                </span>
              );
            }

            return (
              <button
                key={tab.id}
                onClick={() => setActiveSubTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {tab.label}
                {badge}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto">
        {activeSubTab === "overview" && (
          <ClaimOverviewTab
            claim={claim}
            facts={claimFacts}
            assessment={assessment}
            factsLoading={factsLoading}
            assessmentLoading={assessmentLoading}
            factsError={factsError}
            assessmentError={assessmentError}
            onDocumentClick={handleDocumentClick}
            onViewSource={handleViewSource}
            onAction={(action, reason) => {
              console.log(`Claim action: ${action}`, { claimId: claim.claim_id, reason });
              // TODO: Implement actual action API call
            }}
          />
        )}

        {activeSubTab === "facts" && (
          <ClaimFactsTab
            claim={claim}
            facts={claimFacts}
            loading={factsLoading}
            error={factsError}
            onDocumentClick={handleDocumentClick}
            onViewSource={handleViewSource}
          />
        )}

        {activeSubTab === "assessment" && (
          <ClaimAssessmentTab
            claimId={claim.claim_id}
            assessment={assessment}
            loading={assessmentLoading}
            error={assessmentError}
            onRunAssessment={handleRunAssessment}
            onRefreshAssessment={handleRefreshAssessment}
            onRefreshHistory={handleRefreshHistory}
            onViewHistory={() => setActiveSubTab("history")}
            onEvidenceClick={(ref) => {
              // Synthetic refs (computed lookups) - no navigation
              if (ref.startsWith("_")) {
                console.log("Computed lookup result:", ref);
                return;
              }

              // Try to find matching fact by name to get full provenance
              const fact = claimFacts?.facts.find(
                (f) => f.name.toLowerCase() === ref.toLowerCase()
              );

              if (fact?.selected_from?.doc_id) {
                handleViewSource(
                  fact.selected_from.doc_id,
                  fact.selected_from.page,
                  fact.selected_from.char_start,
                  fact.selected_from.char_end
                );
                return;
              }

              // Fallback: parse as "doc_id:page" format
              const parts = ref.split(":");
              const docId = parts[0];
              const page = parts.length > 1 ? parseInt(parts[1], 10) : null;
              handleViewSource(docId, page, null, null);
            }}
          />
        )}

        {activeSubTab === "assumptions" && (
          <ClaimAssumptionsTab
            assumptions={assessment?.assumptions || []}
            checks={assessment?.checks}
            loading={assessmentLoading}
            error={assessmentError}
          />
        )}

        {activeSubTab === "history" && (
          <ClaimHistoryTab
            claimId={claim.claim_id}
            history={history}
            loading={historyLoading}
            error={historyError}
            onViewRun={(runId) => {
              console.log("View run:", runId);
              // TODO: Load and display historical assessment
            }}
          />
        )}

        {activeSubTab === "data" && (
          <ClaimDataTab
            claim={claim}
            onDocumentClick={handleDocumentClick}
            onViewSource={handleViewSource}
          />
        )}
      </div>

      {/* Document Slide Panel */}
      <DocumentSlidePanel
        claimId={claim.claim_id}
        evidence={selectedEvidence}
        documents={claim.documents || []}
        onClose={handleClosePanel}
      />
    </div>
  );
}
