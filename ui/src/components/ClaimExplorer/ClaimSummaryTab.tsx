import { useState, useEffect, useCallback, useMemo } from "react";
import { ClipboardCheck, LayoutDashboard, FileText, Database, Shield } from "lucide-react";
import { cn } from "../../lib/utils";
import type { ClaimSummary, DocSummary, ClaimFacts, ClaimAssessment, CoverageAnalysisResult } from "../../types";
import { getClaimFacts, getClaimAssessment, getCoverageAnalysis } from "../../api/client";
import { ClaimContextBar } from "./ClaimContextBar";
import { ClaimOverviewTab } from "./ClaimOverviewTab";
import { ClaimFactsTab } from "./ClaimFactsTab";
import { ClaimAssessmentTab } from "./ClaimAssessmentTab";
import { ClaimCoveragesTab } from "./ClaimCoveragesTab";
import { ClaimDataTab } from "./ClaimDataTab";
import { DocumentSlidePanel, type EvidenceLocation } from "./DocumentSlidePanel";

interface ClaimWithDocs extends ClaimSummary {
  documents?: DocSummary[];
}

interface ClaimSummaryTabProps {
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

type SubTab = "assessment" | "coverages" | "overview" | "facts" | "data";

// All tabs (overview and facts kept for backwards compatibility but hidden from UI)
const ALL_SUB_TABS: { id: SubTab; label: string; icon: typeof FileText; hidden?: boolean }[] = [
  { id: "assessment", label: "Assessment", icon: ClipboardCheck },
  { id: "coverages", label: "Coverages", icon: Shield },
  { id: "overview", label: "Overview", icon: LayoutDashboard, hidden: true },
  { id: "facts", label: "Facts", icon: FileText, hidden: true },
  { id: "data", label: "Data", icon: Database },
];

const VISIBLE_TABS = ALL_SUB_TABS.filter((t) => !t.hidden);

/**
 * Main claim view with sub-tabs for Assessment, Coverages, and Data.
 * Overview and Facts are deprecated (hidden) but kept for backwards compatibility.
 * Assessment is the default landing tab.
 */
export function ClaimSummaryTab({ claim, onDocumentClick, onViewSource }: ClaimSummaryTabProps) {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>("assessment");

  // Data state
  const [claimFacts, setClaimFacts] = useState<ClaimFacts | null>(null);
  const [assessment, setAssessment] = useState<ClaimAssessment | null>(null);
  const [coverageAnalysis, setCoverageAnalysis] = useState<CoverageAnalysisResult | null>(null);

  // Document slide panel state
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceLocation | null>(null);

  // Loading state
  const [factsLoading, setFactsLoading] = useState(true);
  const [assessmentLoading, setAssessmentLoading] = useState(true);
  const [coverageLoading, setCoverageLoading] = useState(true);

  // Error state
  const [factsError, setFactsError] = useState<string | null>(null);
  const [assessmentError, setAssessmentError] = useState<string | null>(null);

  // Compute set of evidence refs that have actual document backing
  const resolvableRefs = useMemo(() => {
    const refs = new Set<string>();
    if (claimFacts?.facts) {
      for (const fact of claimFacts.facts) {
        if (fact.selected_from?.doc_id) {
          refs.add(fact.name.toLowerCase());
        }
      }
    }
    return refs;
  }, [claimFacts]);

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

  // Load coverage analysis
  useEffect(() => {
    async function loadCoverageAnalysis() {
      setCoverageLoading(true);
      try {
        const data = await getCoverageAnalysis(claim.claim_id);
        setCoverageAnalysis(data);
      } catch (err) {
        console.warn("Coverage analysis API error:", err);
        setCoverageAnalysis(null);
      } finally {
        setCoverageLoading(false);
      }
    }
    loadCoverageAnalysis();
  }, [claim.claim_id]);

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

  // Handle viewing source document with evidence highlighting
  const handleViewSource = (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null,
    highlightText?: string,
    highlightValue?: string
  ) => {
    setSelectedEvidence({ docId, page, charStart, charEnd, highlightText, highlightValue });
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
    console.log("Running assessment for claim:", claim.claim_id);
    await new Promise((resolve) => setTimeout(resolve, 2000));
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
  };

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
          {VISIBLE_TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeSubTab === tab.id;

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
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-y-auto">
        {activeSubTab === "assessment" && (
          <ClaimAssessmentTab
            claimId={claim.claim_id}
            assessment={assessment}
            coverageAnalysis={coverageAnalysis}
            coverageLoading={coverageLoading}
            loading={assessmentLoading}
            error={assessmentError}
            onRunAssessment={handleRunAssessment}
            onRefreshAssessment={handleRefreshAssessment}
            resolvableRefs={resolvableRefs}
            onEvidenceClick={(ref) => {
              if (ref.startsWith("_")) {
                return;
              }

              const fact = claimFacts?.facts.find(
                (f) => f.name.toLowerCase() === ref.toLowerCase()
              );

              if (fact?.selected_from?.doc_id) {
                handleViewSource(
                  fact.selected_from.doc_id,
                  fact.selected_from.page,
                  fact.selected_from.char_start,
                  fact.selected_from.char_end,
                  fact.selected_from.text_quote ?? undefined,
                  typeof fact.value === 'string' ? fact.value : undefined
                );
              }
              // If no document backing, do nothing (ref is not resolvable)
            }}
          />
        )}

        {activeSubTab === "coverages" && (
          <ClaimCoveragesTab
            coverageAnalysis={coverageAnalysis}
            loading={coverageLoading}
          />
        )}

        {/* Deprecated tabs (hidden from navigation but kept for backwards compatibility) */}
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
