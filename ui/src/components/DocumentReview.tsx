import { useState, useEffect, useCallback } from "react";
import {
  listClassificationDocs,
  listDocs,
  getDoc,
  getDocSourceUrl,
  saveLabels,
  type ClaimRunInfo,
} from "../api/client";
import type {
  ClassificationDoc,
  DocPayload,
  FieldLabel,
  DocLabels,
  UnverifiableReason,
} from "../types";
import { RunSelector } from "./shared/RunSelector";
import { DocumentViewer } from "./DocumentViewer";
import { FieldsTable } from "./FieldsTable";
import { cn } from "../lib/utils";

interface DocumentReviewProps {
  runs: ClaimRunInfo[];
  selectedRunId: string | null;
  onRunChange: (runId: string | null) => void;
}

type DocTypeFilter = "all" | string;
type ClaimFilter = "all" | string;
type StatusFilter = "all" | "pending" | "labeled";

export function DocumentReview({
  runs,
  selectedRunId,
  onRunChange,
}: DocumentReviewProps) {
  // Document list state
  const [docs, setDocs] = useState<ClassificationDoc[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track docs that have extraction (for filtering)
  const [docsWithExtraction, setDocsWithExtraction] = useState<Set<string>>(new Set());

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

  // Load documents when run changes
  const loadDocs = useCallback(async () => {
    if (!selectedRunId) {
      setDocs([]);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Get classification docs
      const classificationDocs = await listClassificationDocs(selectedRunId);

      // Get unique claim IDs to fetch extraction status
      const claimIds = Array.from(new Set(classificationDocs.map((d) => d.claim_id)));

      // Fetch doc summaries for all claims to get has_extraction status
      const docSummariesByClaimPromises = claimIds.map((claimId) =>
        listDocs(claimId, selectedRunId).catch(() => [])
      );
      const docSummariesByClaim = await Promise.all(docSummariesByClaimPromises);

      // Build set of doc IDs that have extraction
      const extractedDocIds = new Set<string>();
      docSummariesByClaim.flat().forEach((doc) => {
        if (doc.has_extraction) {
          extractedDocIds.add(doc.doc_id);
        }
      });

      setDocs(classificationDocs);
      setDocsWithExtraction(extractedDocIds);

      // Clear selection when run changes
      setSelectedDocId(null);
      setDocPayload(null);
      setFieldLabels([]);
      setHasUnsavedChanges(false);
      setClaimFilter("all");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [selectedRunId]);

  useEffect(() => {
    loadDocs();
  }, [loadDocs]);

  // Load document detail when selection changes
  const loadDetail = useCallback(async () => {
    if (!selectedDocId || !selectedRunId) {
      setDocPayload(null);
      setFieldLabels([]);
      return;
    }

    // Warn about unsaved changes
    if (hasUnsavedChanges) {
      const proceed = window.confirm("You have unsaved changes. Discard them?");
      if (!proceed) return;
    }

    // Find the selected doc to get claim_id
    const selectedDoc = docs.find((d) => d.doc_id === selectedDocId);
    if (!selectedDoc) return;

    try {
      setDetailLoading(true);
      const payload = await getDoc(
        selectedDocId,
        selectedDoc.claim_id,
        selectedRunId
      );
      setDocPayload(payload);

      
      // Initialize labels from existing or create new from extraction
      if (payload.labels) {
        setFieldLabels(payload.labels.field_labels);
        setDocLabels(payload.labels.doc_labels);
        setNotes(payload.labels.review.notes);
      } else if (payload.extraction) {
        // Initialize field labels from extraction fields with UNLABELED state
        setFieldLabels(
          payload.extraction.fields.map((f) => ({
            field_name: f.name,
            state: "UNLABELED" as const,
            notes: "",
          }))
        );
        setDocLabels({ doc_type_correct: true });
        setNotes("");
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
  }, [selectedDocId, selectedRunId, docs, hasUnsavedChanges]);

  // Handle document selection with change tracking
  const handleSelectDoc = (docId: string) => {
    if (docId !== selectedDocId) {
      setSelectedDocId(docId);
    }
  };

  useEffect(() => {
    loadDetail();
  }, [selectedDocId]); // Note: not including loadDetail to avoid loops with hasUnsavedChanges

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

  // Save labels and auto-advance to next unlabeled doc
  async function handleSave() {
    if (!docPayload) return;

    const currentDocId = docPayload.doc_id;

    // Find next pending doc BEFORE saving (current doc will become labeled)
    const currentIndex = filteredDocs.findIndex((d) => d.doc_id === currentDocId);

    // Look for next pending doc after current position (exclude current)
    let nextDoc = filteredDocs.slice(currentIndex + 1).find((d) => d.review_status === "pending");

    // If none found after, look from beginning (exclude current)
    if (!nextDoc) {
      nextDoc = filteredDocs.find((d) => d.doc_id !== currentDocId && d.review_status === "pending");
    }

    try {
      setSaving(true);
      await saveLabels(docPayload.doc_id, "QA Console", notes, fieldLabels, docLabels);
      setHasUnsavedChanges(false);

      // Update the current doc's status locally to avoid full reload
      setDocs((prev) =>
        prev.map((d) =>
          d.doc_id === currentDocId ? { ...d, review_status: "confirmed" as const } : d
        )
      );

      // Auto-advance to next unlabeled doc
      if (nextDoc) {
        setSelectedDocId(nextDoc.doc_id);
      }
    } catch (err) {
      console.error("Failed to save labels:", err);
    } finally {
      setSaving(false);
    }
  }

  // Get unique doc types and claims for filters
  const docTypes = Array.from(new Set(docs.map((d) => d.predicted_type))).sort();
  const claims = Array.from(new Set(docs.map((d) => d.claim_id))).sort();

  // Filter documents - only include docs with extraction
  const filteredDocs = docs.filter((doc) => {
    // Only include docs that have extraction
    if (!docsWithExtraction.has(doc.doc_id)) {
      return false;
    }

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
          <span className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600">
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
        ? "text-green-600"
        : confidence >= 0.7
        ? "text-amber-600"
        : "text-red-600";
    return <span className={cn("text-xs font-medium", color)}>{pct}%</span>;
  };

  // Count labeled fields
  const labeledCount = fieldLabels.filter(
    (l) => l.state === "LABELED" || l.state === "CONFIRMED"
  ).length;
  const unverifiableCount = fieldLabels.filter((l) => l.state === "UNVERIFIABLE").length;
  const totalFields = fieldLabels.length;

  const selectedDoc = docs.find((d) => d.doc_id === selectedDocId);

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="bg-white border-b px-4 py-3 flex items-center gap-4">
        {/* Run Selector */}
        <RunSelector
          runs={runs}
          selectedRunId={selectedRunId}
          onRunChange={onRunChange}
          showMetadata={false}
          className="w-56"
          testId="document-review"
        />

        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search filename, doc ID, or claim..."
            className="w-full pl-8 pr-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <svg
            className="absolute left-2.5 top-2 w-4 h-4 text-gray-400"
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
          className="px-3 py-1.5 text-sm border rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
          className="px-3 py-1.5 text-sm border rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
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
          className="px-3 py-1.5 text-sm border rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="labeled">Labeled</option>
        </select>

        {/* Count */}
        <div className="text-sm text-gray-500">
          {filteredDocs.length} of {docs.length} documents
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex min-h-0">
        {/* Document List - narrow left panel */}
        <div className="w-72 border-r overflow-auto bg-white flex-shrink-0">
          {loading ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              Loading documents...
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center h-full p-4">
              <p className="text-red-600 mb-2 text-sm">{error}</p>
              <button
                onClick={loadDocs}
                className="px-3 py-1.5 text-sm bg-gray-900 text-white rounded-md hover:bg-gray-800"
              >
                Retry
              </button>
            </div>
          ) : !selectedRunId ? (
            <div className="flex items-center justify-center h-full text-gray-500 text-sm">
              Select a run to view documents
            </div>
          ) : filteredDocs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-gray-500 text-sm">
              No documents match filters
            </div>
          ) : (
            <div className="divide-y">
              {filteredDocs.map((doc) => (
                <div
                  key={doc.doc_id}
                  onClick={() => handleSelectDoc(doc.doc_id)}
                  className={cn(
                    "p-3 cursor-pointer hover:bg-gray-50 transition-colors",
                    selectedDocId === doc.doc_id && "bg-blue-50 border-l-2 border-blue-500"
                  )}
                >
                  <div className="font-medium text-sm text-gray-900 truncate">
                    {doc.filename}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-500">
                      {doc.predicted_type.replace(/_/g, " ")}
                    </span>
                    {getConfidenceBadge(doc.confidence)}
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-xs text-gray-400 truncate">
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
            <div className="flex-1 border-r bg-white">
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
            <div className="w-[420px] flex-shrink-0 flex flex-col bg-gray-50">
              {/* Header */}
              <div className="px-4 py-3 border-b bg-white">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-gray-900">Field Extraction</h3>
                    <div className="text-xs text-gray-500 mt-0.5">
                      {labeledCount} labeled, {unverifiableCount} unverifiable of {totalFields} fields
                    </div>
                  </div>
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
                          ? "bg-gray-200 text-gray-500 cursor-not-allowed"
                          : "bg-gray-900 text-white hover:bg-gray-800"
                      )}
                    >
                      {saving ? "Saving..." : "Save"}
                    </button>
                  </div>
                </div>
              </div>

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
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                    No extraction data available
                  </div>
                )}
              </div>

              {/* Notes */}
              <div className="px-4 py-3 border-t bg-white">
                <label className="block text-xs font-medium text-gray-700 mb-1">
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
            </div>
          </div>
        ) : detailLoading ? (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Loading document...
          </div>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            Select a document to review
          </div>
        )}
      </div>
    </div>
  );
}
