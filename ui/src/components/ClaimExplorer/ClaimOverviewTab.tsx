import { Loader2 } from "lucide-react";
import type {
  ClaimSummary,
  DocSummary,
  ClaimFacts,
  ClaimAssessment,
} from "../../types";
import { type DecisionReadiness, type BlockingIssue } from "./DecisionReadinessCard";
import { WorkflowActionsPanel } from "./WorkflowActionsPanel";
import { DocumentsPanel } from "./DocumentsPanel";
import { QuickFactsSummary } from "./QuickFactsSummary";
import { ChecksSummaryPanel } from "./ChecksSummaryPanel";

/** Format field name from snake_case to Title Case */
function formatFieldName(name: string): string {
  return name
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

interface ClaimWithDocs extends ClaimSummary {
  documents?: DocSummary[];
}

interface ClaimOverviewTabProps {
  claim: ClaimWithDocs;
  facts: ClaimFacts | null;
  assessment: ClaimAssessment | null;
  factsLoading: boolean;
  assessmentLoading: boolean;
  factsError: string | null;
  assessmentError: string | null;
  onDocumentClick?: (docId: string) => void;
  onViewSource?: (
    docId: string,
    page: number | null,
    charStart: number | null,
    charEnd: number | null,
    highlightText?: string,
    highlightValue?: string
  ) => void;
  onAction?: (action: "approve" | "reject" | "refer", reason: string) => void;
}

/**
 * Compute decision readiness from real facts and assessment data.
 * This determines what percentage of prerequisites are met for a decision.
 */
function computeDecisionReadiness(
  facts: ClaimFacts | null,
  assessment: ClaimAssessment | null,
  documents: DocSummary[]
): DecisionReadiness {
  const blockingIssues: BlockingIssue[] = [];
  let totalChecks = 0;
  let passedChecks = 0;

  // Check for critical missing facts
  const criticalFields = [
    "incident_date",
    "loss_date",
    "policy_number",
    "vin",
    "vehicle_make",
    "mileage",
  ];

  const extractedFactNames = new Set(
    facts?.facts.map((f) => f.name.toLowerCase()) || []
  );

  for (const field of criticalFields) {
    totalChecks++;
    const fact = facts?.facts.find(
      (f) => f.name.toLowerCase() === field || f.name.toLowerCase().includes(field)
    );
    if (fact && fact.value !== null && fact.value !== "") {
      passedChecks++;
    } else {
      // Check if it's truly missing or just named differently
      const hasRelated = facts?.facts.some(
        (f) =>
          f.name.toLowerCase().includes(field.replace("_", "")) &&
          f.value !== null
      );
      if (!hasRelated) {
        blockingIssues.push({
          type: "missing_evidence",
          description: `${formatFieldName(field)} not found in documents`,
          field: field,
        });
      } else {
        passedChecks++;
      }
    }
  }

  // Check assessment checks
  if (assessment) {
    for (const check of assessment.checks) {
      totalChecks++;
      if (check.result === "PASS") {
        passedChecks++;
      } else if (check.result === "FAIL") {
        blockingIssues.push({
          type: "failed_check",
          description: check.check_name,
          field: check.check_name,
          checkNumber: check.check_number,
        });
      } else if (check.result === "INCONCLUSIVE") {
        blockingIssues.push({
          type: "inconclusive_check",
          description: `${check.check_name}: ${check.details.slice(0, 60)}...`,
          field: check.check_name,
          checkNumber: check.check_number,
        });
      }
    }
  }

  // Check for quality gate failures
  const gateFailDocs = documents.filter((d) => d.quality_status === "fail");
  for (const doc of gateFailDocs) {
    blockingIssues.push({
      type: "quality_gate",
      description: `Quality gate failed for ${doc.filename}`,
      docId: doc.doc_id,
    });
  }

  // Count critical assumptions
  const criticalAssumptions =
    assessment?.assumptions.filter((a) => a.impact === "high").length || 0;

  // Compute readiness percentage
  const readinessPct =
    totalChecks > 0 ? Math.round((passedChecks / totalChecks) * 100) : 0;

  // Determine if auto-actions are possible
  const hasFailedChecks =
    assessment?.checks.some((c) => c.result === "FAIL") || false;
  const hasInconclusiveChecks =
    assessment?.checks.some((c) => c.result === "INCONCLUSIVE") || false;
  const hasMissingCritical = blockingIssues.some(
    (i) => i.type === "missing_evidence"
  );

  return {
    readinessPct,
    blockingIssues,
    criticalAssumptions,
    canAutoApprove:
      !hasFailedChecks &&
      !hasInconclusiveChecks &&
      !hasMissingCritical &&
      criticalAssumptions === 0,
    canAutoReject: hasFailedChecks && !hasInconclusiveChecks,
  };
}


/**
 * Overview tab showing decision readiness, attention items, and workflow actions.
 * All data comes from real backend sources - no mock data.
 */
export function ClaimOverviewTab({
  claim,
  facts,
  assessment,
  factsLoading,
  assessmentLoading,
  factsError,
  assessmentError,
  onDocumentClick,
  onViewSource,
  onAction,
}: ClaimOverviewTabProps) {
  const documents = claim.documents || [];
  const isLoading = factsLoading || assessmentLoading;

  // Compute derived data from real backend data
  const decisionReadiness = computeDecisionReadiness(facts, assessment, documents);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Loading claim overview...</p>
        </div>
      </div>
    );
  }

  if (factsError && assessmentError) {
    return (
      <div className="p-4">
        <div className="bg-card rounded-lg border border-destructive/30 p-6 text-center">
          <p className="text-sm text-destructive">
            Failed to load claim data: {factsError || assessmentError}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-4">
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* LEFT COLUMN (60% - 3 cols) */}
        <div className="lg:col-span-3 space-y-4">
          {/* Quick Facts Summary */}
          <QuickFactsSummary
            facts={facts?.facts || []}
            onViewSource={onViewSource}
          />

          {/* Assessment Checks */}
          <ChecksSummaryPanel
            checks={assessment?.checks || []}
          />
        </div>

        {/* RIGHT COLUMN (40% - 2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          {/* Documents Quick View */}
          <DocumentsPanel
            documents={documents}
            onDocumentClick={onDocumentClick}
          />

          {/* Workflow Actions */}
          <WorkflowActionsPanel
            readiness={decisionReadiness}
            currentDecision={assessment?.decision || null}
            onAction={onAction}
          />
        </div>
      </div>
    </div>
  );
}
