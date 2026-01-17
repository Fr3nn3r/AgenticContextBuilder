import { useState, useEffect, useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {
  listClassificationDocs,
  getDoc,
  getDocSourceUrl,
  saveLabels,
  saveClassificationLabel,
  type ClaimRunInfo,
} from "../api/client";
import type {
  ClassificationDoc,
  ClassificationDetail,
  DocPayload,
  FieldLabel,
  DocLabels,
  UnverifiableReason,
} from "../types";
import { DocumentViewer } from "./DocumentViewer";
import { FieldsTable } from "./FieldsTable";
import { ClassificationPanel } from "./ClassificationPanel";
import { cn } from "../lib/utils";

interface DocumentReviewProps {
  batches: ClaimRunInfo[];
  selectedBatchId: string | null;
  onBatchChange: (batchId: string | null) => void;
}

type DocTypeFilter = "all" | string;
type ClaimFilter = "all" | string;
type StatusFilter = "all" | "pending" | "labeled";

export function DocumentReview({
  batches: _batches,
  selectedBatchId,
  onBatchChange: _onBatchChange,
}: DocumentReviewProps) {
  // Batch context now handled by BatchWorkspace
  void _batches;
  void _onBatchChange;

  // URL params for claim filter and doc selection (from claims tab navigation)
  const [searchParams, setSearchParams] = useSearchParams();
  const urlClaimParam = searchParams.get("claim");
  const urlDocParam = searchParams.get("doc");

  // Document list state
  const [docs, setDocs] = useState<ClassificationDoc[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [docTypeFilter, setDocTypeFilter] = useState<DocTypeFilter>("all");
  const [claimFilter, setClaimFilter] = useState<ClaimFilter>("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Selection and detail state
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [docPayload, setDocPayload] = useState<DocPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Label state for field extraction review
  const [fieldLabels, setFieldLabels] = useState<FieldLabel[]>([]);
  const [docLabels, setDocLabels] = useState<DocLabels>({ doc_type_correct: true });
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // Highlight state for provenance
  const [highlightQuote, setHighlightQuote] = useState<string | undefined>();
  const [highlightPage, setHighlightPage] = useState<number | undefined>();
  const [highlightCharStart, setHighlightCharStart] = useState<number | undefined>();
  const [highlightCharEnd, setHighlightCharEnd] = useState<number | undefined>();
  const [highlightValue, setHighlightValue] = useState<string | undefined>();

  // Optional fields toggle
  const [showOptionalFields, setShowOptionalFields] = useState(false);

  // Copy ID state
  const [copiedDocId, setCopiedDocId] = useState(false);
  const [copiedBatchId, setCopiedBatchId] = useState(false);

  // Classification panel state
  const [classificationDetail, setClassificationDetail] = useState<ClassificationDetail | null>(null);
  const [classificationConfirmed, setClassificationConfirmed] = useState(false);
  const [classificationOverridden, setClassificationOverridden] = useState(false);
  const [classificationOverriddenType, setClassificationOverriddenType] = useState<string | null>(null);

  // Load documents when run changes
  const loadDocs = useCallback(async () => {
    if (!selectedBatchId) {
      setDocs([]);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get classification docs
      const classificationDocs = await listClassificationDocs(selectedBatchId);

      // Get unique claim IDs for URL param validation
      const claimIds = Array.from(new Set(classificationDocs.map((d) => d.claim_id)));

      setDocs(classificationDocs);

      // Check for URL params (from claims tab navigation)
      if (urlDocParam && classificationDocs.some(d => d.doc_id === urlDocParam)) {
        // Select the doc from URL params
        setSelectedDocId(urlDocParam);
        // Set claim filter if provided
        if (urlClaimParam && claimIds.includes(urlClaimParam)) {
          setClaimFilter(urlClaimParam);
        }
        // Clear URL params after applying them (one-time use)
        setSearchParams({}, { replace: true });
      } else if (classificationDocs.length > 0) {
        // Auto-select first document when run changes (default behavior)
        setSelectedDocId(classificationDocs[0].doc_id);
        setClaimFilter("all");
      } else {
        setSelectedDocId(null);
        setClaimFilter("all");
      }
      // Note: Don't reset docPayload/fieldLabels here - loadDetail() handles this
      // Resetting here causes flicker as UI shows empty state before detail loads
      setHasUnsavedChanges(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [selectedBatchId, urlDocParam, urlClaimParam, setSearchParams]);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  // Load document detail when selection changes
  const loadDetail = useCallback(async () => {
    if (!selectedDocId || !selectedBatchId) {
      setDocPayload(null);
      setFieldLabels([]);
      return;
    }

    // Find the selected doc to get claim_id
    const selectedDoc = docs.find((d) => d.doc_id === selectedDocId);
    if (!selectedDoc) return;

    try {
      setDetailLoading(true);
      const payload = await getDoc(
        selectedDocId,
        selectedDoc.claim_id,
        selectedBatchId
      );
      setDocPayload(payload);

      // Build classification detail from available data
      // The selectedDoc already has predicted_type, confidence, signals from listClassificationDocs
      if (selectedDoc) {
        setClassificationDetail({
          doc_id: selectedDoc.doc_id,
          claim_id: selectedDoc.claim_id,
          filename: selectedDoc.filename,
          predicted_type: selectedDoc.predicted_type,
          confidence: selectedDoc.confidence,
          signals: selectedDoc.signals || [],
          summary: "",
          key_hints: null,
          language: "unknown",
          pages_preview: "",
          has_pdf: payload.has_pdf || false,
          has_image: payload.has_image || false,
          existing_label: payload.labels?.doc_labels
            ? {
                doc_type_correct: payload.labels.doc_labels.doc_type_correct ?? true,
                doc_type_truth: selectedDoc.doc_type_truth || null,
                notes: payload.labels.review?.notes || "",
              }
            : null,
        });

        // Initialize classification label state from existing labels
        const hasOverride = selectedDoc.doc_type_truth !== null && selectedDoc.doc_type_truth !== selectedDoc.predicted_type;
        const isConfirmed = payload.labels?.doc_labels?.doc_type_correct === true;
        setClassificationConfirmed(isConfirmed || hasOverride);
        setClassificationOverridden(hasOverride);
        setClassificationOverriddenType(hasOverride ? selectedDoc.doc_type_truth : null);
      }

      // Initialize labels from existing or create new from extraction
      if (payload.labels && payload.labels.field_labels.length > 0) {
        setFieldLabels(payload.labels.field_labels);
        setDocLabels(payload.labels.doc_labels);
        setNotes(payload.labels.review.notes);

        // Update doc status in list if it has labeled fields
        // This ensures the list shows "Labeled" even if backend returned "pending"
        const hasLabeledFields = payload.labels.field_labels.some(
          (l: FieldLabel) => l.state === "LABELED" || l.state === "CONFIRMED"
        );
        if (hasLabeledFields) {
          setDocs((prev) =>
            prev.map((d) =>
              d.doc_id === selectedDocId && d.review_status === "pending"
                ? { ...d, review_status: "confirmed" as const }
                : d
            )
          );
        }
      } else if (payload.extraction) {
        // Initialize field labels from extraction fields with UNLABELED state
        setFieldLabels(
          payload.extraction.fields.map((f) => ({
            field_name: f.name,
            state: "UNLABELED" as const,
            notes: "",
          }))
        );
        // Preserve doc_labels if they exist (for classification), otherwise default
        setDocLabels(payload.labels?.doc_labels || { doc_type_correct: true });
        setNotes(payload.labels?.review?.notes || "");
      } else {
        setFieldLabels([]);
        setDocLabels({ doc_type_correct: true });
        setNotes("");
      }

      setHasUnsavedChanges(false);
      // Clear highlights when switching documents
      setHighlightQuote(undefined);
      setHighlightPage(undefined);
      setHighlightCharStart(undefined);
      setHighlightCharEnd(undefined);
      setHighlightValue(undefined);
    } catch (err) {
      console.error("Failed to load document detail:", err);
      setDocPayload(null);
    } finally {
      setDetailLoading(false);
    }
  }, [selectedDocId, selectedBatchId, docs]);

  // Handle document selection with change tracking
  const handleSelectDoc = (docId: string) => {
    if (docId !== selectedDocId) {
      // Warn about unsaved changes only for manual selection
      if (hasUnsavedChanges) {
        const proceed = window.confirm("You have unsaved changes. Discard them?");
        if (!proceed) return;
      }
      setSelectedDocId(docId);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [loadDetail]); // Include loadDetail to trigger when docs are loaded

  // Field labeling handlers
  function handleConfirmField(fieldName: string, truthValue: string) {
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
  }

  function handleUnverifiableField(fieldName: string, reason: UnverifiableReason) {
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
  }

  function handleEditTruth(fieldName: string, newTruthValue: string) {
    setFieldLabels((prev) =>
      prev.map((l) =>
        l.field_name === fieldName && (l.state === "LABELED" || l.state === "CONFIRMED")
          ? { ...l, truth_value: newTruthValue, updated_at: new Date().toISOString() }
          : l
      )
    );
    setHasUnsavedChanges(true);
  }

  function handleQuoteClick(
    quote: string,
    page: number,
    charStart?: number,
    charEnd?: number,
    extractedValue?: string
  ) {
    setHighlightQuote(quote);
    setHighlightPage(page);
    setHighlightCharStart(charStart);
    setHighlightCharEnd(charEnd);
    setHighlightValue(extractedValue);
  }

  // Save labels (stays on current document)
  async function handleSave() {
    if (!docPayload || !classificationDetail) return;

    const currentDocId = docPayload.doc_id;

    try {
      setSaving(true);

      // Save field labels
      await saveLabels(docPayload.doc_id, "QA Console", notes, fieldLabels, docLabels);

      // Save classification label (to update doc_type_truth in the list)
      await saveClassificationLabel(classificationDetail.doc_id, {
        claim_id: classificationDetail.claim_id,
        doc_type_correct: !classificationOverridden,
        doc_type_truth: classificationOverriddenType || undefined,
        notes: "",
      });

      setHasUnsavedChanges(false);

      // Update the current doc's status locally to avoid full reload
      setDocs((prev) =>
        prev.map((d) =>
          d.doc_id === currentDocId
            ? {
                ...d,
                review_status: "confirmed" as const,
                doc_type_truth: classificationOverriddenType,
              }
            : d
        )
      );

      // Stay on current document - user can manually select next doc when ready
    } catch (err) {
      console.error("Failed to save labels:", err);
    } finally {
      setSaving(false);
    }
  }

  function handleCopyDocId() {
    if (docPayload?.doc_id) {
      navigator.clipboard.writeText(docPayload.doc_id);
      setCopiedDocId(true);
      setTimeout(() => setCopiedDocId(false), 2000);
    }
  }

  function handleCopyBatchId() {
    if (selectedBatchId) {
      navigator.clipboard.writeText(selectedBatchId);
      setCopiedBatchId(true);
      setTimeout(() => setCopiedBatchId(false), 2000);
    }
  }

  // Classification handlers - update local state only (saved with main Save button)
  function handleConfirmClassification() {
    setClassificationConfirmed(true);
    setClassificationOverridden(false);
    setClassificationOverriddenType(null);
    setDocLabels((prev) => ({ ...prev, doc_type_correct: true }));
    setHasUnsavedChanges(true);
  }

  function handleOverrideClassification(newType: string) {
    setClassificationConfirmed(true);
    setClassificationOverridden(true);
    setClassificationOverriddenType(newType);
    setDocLabels((prev) => ({ ...prev, doc_type_correct: false, doc_type_truth: newType }));
    setHasUnsavedChanges(true);
  }

  // Get unique doc types and claims for filters
  const docTypes = Array.from(new Set(docs.map((d) => d.predicted_type))).sort();
  const claims = Array.from(new Set(docs.map((d) => d.claim_id))).sort();

  // Filter documents - memoized to prevent unnecessary re-renders
  const filteredDocs = useMemo(() => {
    return docs.filter((doc) => {
      // Claim filter
      if (claimFilter !== "all" && doc.claim_id !== claimFilter) {
        return false;
      }

      // Doc type filter
      if (docTypeFilter !== "all" && doc.predicted_type !== docTypeFilter) {
        return false;
      }

      // Status filter
      if (statusFilter !== "all") {
        if (statusFilter === "pending" && doc.review_status !== "pending") {
          return false;
        }
        if (statusFilter === "labeled" && doc.review_status === "pending") {
          return false;
        }
      }

      // Search filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        return (
          doc.filename.toLowerCase().includes(query) ||
          doc.doc_id.toLowerCase().includes(query) ||
          doc.claim_id.toLowerCase().includes(query)
        );
      }

      return true;
    });
  }, [docs, claimFilter, docTypeFilter, statusFilter, searchQuery]);

  // Auto-select first doc when filter changes or selection is not in filtered list
  useEffect(() => {
    // Don't run while docs are still loading
    if (loading || !selectedBatchId) return;

    if (filteredDocs.length === 0) {
      // No docs match filter - clear selection if needed
      if (selectedDocId) {
        setSelectedDocId(null);
      }
      return;
    }

    // Check if current selection is in filtered list
    const selectionInList = selectedDocId && filteredDocs.some(d => d.doc_id === selectedDocId);

    if (!selectionInList && filteredDocs[0]) {
      // Select first doc in filtered list - loadDetail effect will handle loading
      setSelectedDocId(filteredDocs[0].doc_id);
    }
  }, [filteredDocs, selectedDocId, loading, selectedBatchId]);

  // Get status badge color
  const getStatusBadge = (status: ClassificationDoc["review_status"]) => {
    switch (status) {
      case "confirmed":
        return (
          <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">
            Labeled
          </span>
        );
      case "overridden":
        return (
          <span className="px-2 py-0.5 text-xs rounded-full bg-amber-100 text-amber-700">
            Overridden
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 text-xs rounded-full bg-muted text-muted-foreground">
            Pending
          </span>
        );
    }
  };

  // Get confidence badge
  const getConfidenceBadge = (confidence: number) => {
    const pct = Math.round(confidence * 100);
    const color =
      confidence >= 0.9
        ? "text-success"
        : confidence >= 0.7
        ? "text-amber-600"
        : "text-red-600";
    return <span className={cn("text-xs font-medium", color)}>{pct}%</span>;
  };

  const selectedDoc = docs.find((d) => d.doc_id === selectedDocId);

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="bg-card border-b px-4 py-3 flex items-center gap-4 flex-wrap">
        {/* Search */}
        <div className="relative w-64 flex-shrink-0">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search filename, doc ID, or claim..."
            className="w-full pl-8 pr-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <svg
            className="absolute left-2.5 top-2 w-4 h-4 text-muted-foreground/70"
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
        </div>

        {/* Claim Filter */}
        <select
          value={claimFilter}
          onChange={(e) => setClaimFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border rounded-md bg-card focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Claims</option>
          {claims.map((claim) => (
            <option key={claim} value={claim}>
              {claim}
            </option>
          ))}
        </select>

        {/* Doc Type Filter */}
        <select
          value={docTypeFilter}
          onChange={(e) => setDocTypeFilter(e.target.value)}
          className="px-3 py-1.5 text-sm border rounded-md bg-card focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Types</option>
          {docTypes.map((type) => (
            <option key={type} value={type}>
              {type.replace(/_/g, " ")}
            </option>
          ))}
        </select>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          className="px-3 py-1.5 text-sm border rounded-md bg-card focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="labeled">Labeled</option>
        </select>

        {/* Count */}
        <div className="text-sm text-muted-foreground">
          {filteredDocs.length} of {docs.length} documents
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex min-h-0">
        {/* Document List - narrow left panel */}
        <div className="w-72 border-r overflow-auto bg-card flex-shrink-0" data-testid="document-list">
          {loading ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Loading documents...
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full p-4">
              <p className="text-red-600 mb-2 text-sm">{error}</p>
              <button
                onClick={loadDocs}
                className="px-3 py-1.5 text-sm bg-primary text-white rounded-md hover:bg-primary/90"
              >
                Retry
              </button>
            </div>
          ) : !selectedBatchId ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Select a run to view documents
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              No documents match filters
            </div>
          ) : (
            <div className="divide-y">
              {filteredDocs.map((doc) => (
                <div
                  key={doc.doc_id}
                  onClick={() => handleSelectDoc(doc.doc_id)}
                  data-testid="doc-list-item"
                  className={cn(
                    "p-3 cursor-pointer hover:bg-muted/50 transition-colors",
                    selectedDocId === doc.doc_id && "bg-accent/10 border-l-2 border-accent"
                  )}
                >
                  <div className="font-medium text-sm text-foreground truncate">
                    {doc.filename}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground">
                      {doc.predicted_type.replace(/_/g, " ")}
                    </span>
                    {getConfidenceBadge(doc.confidence)}
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-xs text-muted-foreground/70 truncate">
                      {doc.claim_id}
                    </span>
                    {getStatusBadge(doc.review_status)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Document Viewer + Fields Panel */}
        {selectedDoc && docPayload ? (
          <div className="flex-1 flex min-h-0">
            {/* Center: Document Viewer */}
            <div className="flex-1 border-r bg-card">
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

            {/* Right: Fields Panel */}
            <div className="w-[420px] flex-shrink-0 flex flex-col bg-muted/50">
              {/* Header */}
              <div className="px-4 py-2.5 border-b bg-card">
                <div className="flex items-center justify-between">
                  <h3 className="font-medium text-foreground">Field Extraction</h3>
                  <div className="flex items-center gap-2">
                    {hasUnsavedChanges && (
                      <span className="text-xs text-amber-600">Unsaved</span>
                    )}
                    <button
                      onClick={handleSave}
                      disabled={saving || !hasUnsavedChanges}
                      className={cn(
                        "px-3 py-1.5 text-sm rounded-md font-medium transition-colors",
                        saving || !hasUnsavedChanges
                          ? "bg-muted text-muted-foreground cursor-not-allowed"
                          : "bg-primary text-white hover:bg-primary/90"
                      )}
                    >
                      {saving ? "Saving..." : "Save"}
                    </button>
                  </div>
                </div>
              </div>

              {/* Classification Panel */}
              {docPayload.extraction && classificationDetail && (
                <ClassificationPanel
                  predictedType={classificationDetail.predicted_type}
                  confidence={classificationDetail.confidence}
                  signals={classificationDetail.signals}
                  isConfirmed={classificationConfirmed}
                  isOverridden={classificationOverridden}
                  overriddenType={classificationOverriddenType}
                  onConfirm={handleConfirmClassification}
                  onOverride={handleOverrideClassification}
                />
              )}

              {/* Fields Table */}
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
                  <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                    No extraction data available
                  </div>
                )}
              </div>

              {/* Notes */}
              <div className="px-4 py-3 border-t bg-card">
                <label className="block text-xs font-medium text-foreground mb-1">
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
                  className="w-full px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                />
              </div>

              {/* Copy IDs Section */}
              <div className="px-4 py-2 border-t bg-muted/50 flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1">
                  <span className="text-muted-foreground">Doc ID:</span>
                  <code className="text-foreground font-mono">{docPayload.doc_id.slice(0, 12)}...</code>
                  <button
                    onClick={handleCopyDocId}
                    className="p-1 text-muted-foreground/70 hover:text-muted-foreground"
                    title="Copy full Doc ID"
                  >
                    {copiedDocId ? (
                      <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    )}
                  </button>
                </div>
                <div className="flex items-center gap-1">
                  <span className="text-muted-foreground">Batch:</span>
                  <code className="text-foreground font-mono">{selectedBatchId?.slice(0, 12)}...</code>
                  <button
                    onClick={handleCopyBatchId}
                    className="p-1 text-muted-foreground/70 hover:text-muted-foreground"
                    title="Copy full Batch ID"
                  >
                    {copiedBatchId ? (
                      <svg className="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        ) : detailLoading ? (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            Loading document...
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground">
            Select a document to review
          </div>
        )}
      </div>
    </div>
  );
}
