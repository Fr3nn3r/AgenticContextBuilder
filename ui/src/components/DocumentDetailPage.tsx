import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import {
  getDoc,
  getDocSourceUrl,
  getDocRuns,
  saveLabels,
  saveClassificationLabel,
  type DocRunInfo,
} from "../api/client";
import type {
  DocPayload,
  FieldLabel,
  DocLabels,
  UnverifiableReason,
  ClassificationDetail,
} from "../types";
import { DocumentViewer } from "./DocumentViewer";
import { FieldsTable } from "./FieldsTable";
import { ClassificationPanel } from "./ClassificationPanel";
import { cn } from "../lib/utils";
import { formatDocType } from "../lib/formatters";

export function DocumentDetailPage() {
  const { claimId, docId } = useParams<{ claimId: string; docId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Run from URL
  const urlRunId = searchParams.get("run");

  // Document data
  const [docPayload, setDocPayload] = useState<DocPayload | null>(null);
  const [docRuns, setDocRuns] = useState<DocRunInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected run
  const [selectedRunId, setSelectedRunId] = useState<string | null>(urlRunId);
  const [showRunDropdown, setShowRunDropdown] = useState(false);

  // Label state
  const [fieldLabels, setFieldLabels] = useState<FieldLabel[]>([]);
  const [docLabels, setDocLabels] = useState<DocLabels>({ doc_type_correct: true });
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Highlight state for DocumentViewer
  const [highlightQuote, setHighlightQuote] = useState<string | undefined>();
  const [highlightPage, setHighlightPage] = useState<number | undefined>();
  const [highlightCharStart, setHighlightCharStart] = useState<number | undefined>();
  const [highlightCharEnd, setHighlightCharEnd] = useState<number | undefined>();
  const [highlightValue, setHighlightValue] = useState<string | undefined>();

  // Classification state
  const [classificationConfirmed, setClassificationConfirmed] = useState(false);
  const [classificationOverridden, setClassificationOverridden] = useState(false);
  const [classificationOverriddenType, setClassificationOverriddenType] = useState<string | null>(null);

  // Optional fields toggle
  const [showOptionalFields, setShowOptionalFields] = useState(false);

  // Load document data
  const loadDocument = useCallback(async () => {
    if (!claimId || !docId) return;

    try {
      setLoading(true);
      setError(null);

      const payload = await getDoc(docId, claimId, selectedRunId || undefined);
      setDocPayload(payload);

      // Initialize labels from existing or create new from extraction
      if (payload.labels && payload.labels.field_labels.length > 0) {
        setFieldLabels(payload.labels.field_labels);
        setDocLabels(payload.labels.doc_labels);
        setNotes(payload.labels.review.notes);
      } else if (payload.extraction) {
        setFieldLabels(
          payload.extraction.fields.map((f) => ({
            field_name: f.name,
            state: "UNLABELED" as const,
            notes: "",
          }))
        );
        setDocLabels(payload.labels?.doc_labels || { doc_type_correct: true });
        setNotes(payload.labels?.review?.notes || "");
      } else {
        setFieldLabels([]);
        setDocLabels({ doc_type_correct: true });
        setNotes("");
      }

      // Initialize classification state
      const hasOverride =
        payload.labels?.doc_labels?.doc_type_truth !== null &&
        payload.labels?.doc_labels?.doc_type_truth !== undefined &&
        payload.labels?.doc_labels?.doc_type_truth !== payload.doc_type;
      const isConfirmed = payload.labels?.doc_labels?.doc_type_correct === true;
      setClassificationConfirmed(isConfirmed || hasOverride);
      setClassificationOverridden(hasOverride);
      setClassificationOverriddenType(hasOverride ? payload.labels?.doc_labels?.doc_type_truth || null : null);

      setHasUnsavedChanges(false);

      // Clear highlights
      setHighlightQuote(undefined);
      setHighlightPage(undefined);
      setHighlightCharStart(undefined);
      setHighlightCharEnd(undefined);
      setHighlightValue(undefined);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  }, [claimId, docId, selectedRunId]);

  // Load runs for this document
  const loadDocRuns = useCallback(async () => {
    if (!claimId || !docId) return;

    try {
      const runs = await getDocRuns(docId, claimId);
      setDocRuns(runs);
      // Default to latest run if none selected
      if (runs.length > 0 && !selectedRunId) {
        setSelectedRunId(runs[0].run_id);
      }
    } catch (err) {
      console.error("Failed to load document runs:", err);
      // Fallback: if we have extraction data, create a single run entry
      if (docPayload?.extraction?.run) {
        setDocRuns([
          {
            run_id: docPayload.extraction.run.run_id,
            timestamp: null,
            model: docPayload.extraction.run.model,
            status: "complete",
            extraction: {
              field_count: docPayload.extraction.fields.length,
              gate_status: docPayload.extraction.quality_gate?.status || null,
            },
          },
        ]);
        if (!selectedRunId) {
          setSelectedRunId(docPayload.extraction.run.run_id);
        }
      }
    }
  }, [claimId, docId, docPayload, selectedRunId]);

  useEffect(() => {
    loadDocument();
  }, [loadDocument]);

  useEffect(() => {
    loadDocRuns();
  }, [loadDocRuns]);

  // Run selection handler
  const handleRunChange = async (runId: string) => {
    if (hasUnsavedChanges) {
      const proceed = window.confirm("You have unsaved changes. Discard them?");
      if (!proceed) return;
    }
    setSelectedRunId(runId);
    setSearchParams({ run: runId });
    setShowRunDropdown(false);
  };

  // Field labeling handlers
  const handleConfirmField = (fieldName: string, truthValue: string) => {
    setFieldLabels((prev) =>
      prev.map((l) =>
        l.field_name === fieldName
          ? {
              ...l,
              state: "LABELED" as const,
              truth_value: truthValue,
              unverifiable_reason: undefined,
              updated_at: new Date().toISOString(),
            }
          : l
      )
    );
    setHasUnsavedChanges(true);
  };

  const handleUnverifiableField = (fieldName: string, reason: UnverifiableReason) => {
    setFieldLabels((prev) =>
      prev.map((l) =>
        l.field_name === fieldName
          ? {
              ...l,
              state: "UNVERIFIABLE" as const,
              truth_value: undefined,
              unverifiable_reason: reason,
              updated_at: new Date().toISOString(),
            }
          : l
      )
    );
    setHasUnsavedChanges(true);
  };

  const handleEditTruth = (fieldName: string, newTruthValue: string) => {
    setFieldLabels((prev) =>
      prev.map((l) =>
        l.field_name === fieldName && (l.state === "LABELED" || l.state === "CONFIRMED")
          ? { ...l, truth_value: newTruthValue, updated_at: new Date().toISOString() }
          : l
      )
    );
    setHasUnsavedChanges(true);
  };

  const handleQuoteClick = (
    quote: string,
    page: number,
    charStart?: number,
    charEnd?: number,
    extractedValue?: string
  ) => {
    setHighlightQuote(quote);
    setHighlightPage(page);
    setHighlightCharStart(charStart);
    setHighlightCharEnd(charEnd);
    setHighlightValue(extractedValue);
  };

  // Classification handlers
  const handleConfirmClassification = () => {
    setClassificationConfirmed(true);
    setClassificationOverridden(false);
    setClassificationOverriddenType(null);
    setDocLabels((prev) => ({ ...prev, doc_type_correct: true }));
    setHasUnsavedChanges(true);
  };

  const handleOverrideClassification = (newType: string) => {
    setClassificationConfirmed(true);
    setClassificationOverridden(true);
    setClassificationOverriddenType(newType);
    setDocLabels((prev) => ({ ...prev, doc_type_correct: false, doc_type_truth: newType }));
    setHasUnsavedChanges(true);
  };

  // Save handler
  const handleSave = async () => {
    if (!docPayload) return;

    try {
      setSaving(true);

      // Save field labels
      await saveLabels(docPayload.doc_id, "QA Console", notes, fieldLabels, docLabels);

      // Save classification label
      await saveClassificationLabel(docPayload.doc_id, {
        claim_id: docPayload.claim_id,
        doc_type_correct: !classificationOverridden,
        doc_type_truth: classificationOverriddenType || undefined,
        notes: "",
      });

      setHasUnsavedChanges(false);
    } catch (err) {
      console.error("Failed to save labels:", err);
    } finally {
      setSaving(false);
    }
  };

  // Build classification detail for ClassificationPanel
  const classificationDetail = useMemo<ClassificationDetail | null>(() => {
    if (!docPayload) return null;
    return {
      doc_id: docPayload.doc_id,
      claim_id: docPayload.claim_id,
      filename: docPayload.filename,
      predicted_type: docPayload.doc_type,
      confidence: docPayload.extraction?.doc?.doc_type_confidence || 0,
      signals: [],
      summary: "",
      key_hints: null,
      language: docPayload.language,
      pages_preview: "",
      has_pdf: docPayload.has_pdf,
      has_image: docPayload.has_image,
      existing_label: null,
    };
  }, [docPayload]);

  // Labeling progress stats
  const labelStats = useMemo(() => {
    const total = fieldLabels.length;
    const labeled = fieldLabels.filter((l) => l.state === "LABELED" || l.state === "CONFIRMED").length;
    const unverifiable = fieldLabels.filter((l) => l.state === "UNVERIFIABLE").length;
    const pending = total - labeled - unverifiable;
    return { total, labeled, unverifiable, pending };
  }, [fieldLabels]);

  // Loading state
  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-muted-foreground text-sm">Loading document...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="bg-destructive/10 text-destructive p-6 rounded-lg max-w-md text-center">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="font-medium mb-2">Failed to load document</p>
          <p className="text-sm opacity-80 mb-4">{error}</p>
          <button
            onClick={() => loadDocument()}
            className="px-4 py-2 bg-destructive text-destructive-foreground rounded-md text-sm font-medium hover:bg-destructive/90 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  // No document
  if (!docPayload) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground">
        Document not found
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col bg-background">
      {/* Compact Header */}
      <header className="bg-card border-b border-border px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center gap-4 min-w-0">
          {/* Breadcrumb */}
          <nav className="flex items-center gap-1.5 text-sm text-muted-foreground flex-shrink-0">
            <button
              onClick={() => navigate("/documents")}
              className="hover:text-foreground transition-colors"
            >
              Documents
            </button>
            <ChevronIcon className="w-3.5 h-3.5" />
            <button
              onClick={() => navigate(`/claims/${claimId}/review`)}
              className="hover:text-foreground transition-colors"
            >
              {claimId}
            </button>
            <ChevronIcon className="w-3.5 h-3.5" />
          </nav>

          {/* Doc title */}
          <h1 className="font-medium text-foreground truncate">
            {docPayload.filename}
          </h1>

          {/* Doc type badge */}
          <span className="px-2 py-0.5 bg-muted rounded text-xs font-medium text-muted-foreground flex-shrink-0">
            {formatDocType(docPayload.doc_type)}
          </span>

          {/* Run selector dropdown */}
          {docRuns.length > 0 && (
            <div className="relative flex-shrink-0">
              <button
                onClick={() => setShowRunDropdown(!showRunDropdown)}
                className="flex items-center gap-1.5 px-2 py-1 text-xs font-mono text-muted-foreground hover:text-foreground bg-muted/50 rounded border border-transparent hover:border-border transition-colors"
              >
                <HistoryIcon className="w-3 h-3" />
                <span className="max-w-[120px] truncate">
                  {selectedRunId ? selectedRunId.slice(0, 20) : "Select run"}
                </span>
                <svg className={cn("w-3 h-3 transition-transform", showRunDropdown && "rotate-180")} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>

              {showRunDropdown && (
                <>
                  <div className="fixed inset-0 z-10" onClick={() => setShowRunDropdown(false)} />
                  <div className="absolute top-full left-0 mt-1 z-20 bg-card border border-border rounded-md shadow-lg py-1 min-w-[280px] max-h-[300px] overflow-auto">
                    {docRuns.map((run) => (
                      <button
                        key={run.run_id}
                        onClick={() => handleRunChange(run.run_id)}
                        className={cn(
                          "w-full text-left px-3 py-2 text-sm hover:bg-muted/50 transition-colors",
                          selectedRunId === run.run_id && "bg-accent/10"
                        )}
                      >
                        <div className="font-mono text-xs text-foreground">{run.run_id}</div>
                        <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
                          <span>{run.model}</span>
                          {run.extraction && (
                            <>
                              <span className="text-muted-foreground/50">|</span>
                              <span>{run.extraction.field_count} fields</span>
                              {run.extraction.gate_status && (
                                <span className={cn(
                                  "px-1 py-0.5 rounded text-[10px] font-medium uppercase",
                                  run.extraction.gate_status === "pass" && "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
                                  run.extraction.gate_status === "warn" && "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
                                  run.extraction.gate_status === "fail" && "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                                )}>
                                  {run.extraction.gate_status}
                                </span>
                              )}
                            </>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Right side: status + save */}
        <div className="flex items-center gap-3 flex-shrink-0">
          {/* Progress indicator */}
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="text-green-600 dark:text-green-400">{labelStats.labeled}</span>
            <span>/</span>
            <span>{labelStats.total}</span>
            <span>labeled</span>
          </div>

          {hasUnsavedChanges && (
            <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
              Unsaved
            </span>
          )}
          <button
            onClick={handleSave}
            disabled={saving || !hasUnsavedChanges}
            className={cn(
              "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
              saving || !hasUnsavedChanges
                ? "bg-muted text-muted-foreground cursor-not-allowed"
                : "bg-primary text-primary-foreground hover:bg-primary/90"
            )}
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </header>

      {/* Main 2-panel layout */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Document Viewer (takes most space) */}
        <div className="flex-1 border-r border-border">
          <DocumentViewer
            pages={docPayload.pages}
            sourceUrl={getDocSourceUrl(docPayload.doc_id, docPayload.claim_id)}
            hasPdf={docPayload.has_pdf}
            hasImage={docPayload.has_image}
            claimId={docPayload.claim_id}
            docId={docPayload.doc_id}
            highlightQuote={highlightQuote}
            highlightPage={highlightPage}
            highlightCharStart={highlightCharStart}
            highlightCharEnd={highlightCharEnd}
            highlightValue={highlightValue}
          />
        </div>

        {/* Right: Labeling Panel */}
        <div className="w-[420px] flex-shrink-0 flex flex-col bg-muted/30">
          {/* Classification panel (collapsed header style) */}
          {classificationDetail && docPayload.extraction && (
            <ClassificationPanel
              predictedType={classificationDetail.predicted_type}
              confidence={classificationDetail.confidence}
              isConfirmed={classificationConfirmed}
              isOverridden={classificationOverridden}
              overriddenType={classificationOverriddenType}
              onConfirm={handleConfirmClassification}
              onOverride={handleOverrideClassification}
            />
          )}

          {/* Fields table */}
          <div className="flex-1 overflow-auto">
            {docPayload.extraction ? (
              <FieldsTable
                fields={docPayload.extraction.fields}
                labels={fieldLabels}
                onConfirm={handleConfirmField}
                onUnverifiable={handleUnverifiableField}
                onEditTruth={handleEditTruth}
                onQuoteClick={handleQuoteClick}
                docType={docPayload.doc_type}
                showOptionalFields={showOptionalFields}
                onToggleOptionalFields={() => setShowOptionalFields(!showOptionalFields)}
                readOnly={classificationOverridden}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-muted-foreground text-sm p-4">
                <div className="text-center">
                  <svg className="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p>No extraction data available</p>
                  <p className="text-xs mt-1">Run the extraction pipeline first</p>
                </div>
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="px-4 py-3 border-t border-border bg-card">
            <label className="block text-xs font-medium text-muted-foreground mb-1.5">
              Review Notes
            </label>
            <textarea
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
                setHasUnsavedChanges(true);
              }}
              placeholder="Optional notes about this document..."
              rows={2}
              className="w-full px-3 py-2 text-sm border border-input rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// Icons
function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  );
}

function HistoryIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
