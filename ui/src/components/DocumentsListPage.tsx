import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import {
  listAllDocuments,
  getDocTypeCatalog,
  listClaims,
  getDoc,
  getDocSourceUrl,
  getDocRuns,
  saveLabels,
} from "../api/client";
import type { DocumentListItem, DocRunInfo } from "../api/client";
import type { DocPayload, FieldLabel, DocLabels } from "../types";
import { DocumentViewer } from "./DocumentViewer";
import { FieldsTable } from "./FieldsTable";
import { cn } from "../lib/utils";

type TruthFilter = "" | "yes" | "no";

export function DocumentsListPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Data
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter options
  const [docTypeOptions, setDocTypeOptions] = useState<string[]>([]);
  const [claimOptions, setClaimOptions] = useState<string[]>([]);

  // Filters from URL params
  const search = searchParams.get("search") || "";
  const docType = searchParams.get("doc_type") || "";
  const claimId = searchParams.get("claim") || "";
  const hasTruth = (searchParams.get("has_truth") || "") as TruthFilter;

  // Selection state
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);

  // Document detail state
  const [docPayload, setDocPayload] = useState<DocPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Run selection state
  const [availableRuns, setAvailableRuns] = useState<DocRunInfo[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Label editing state
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

  // Update URL params
  const updateParam = (key: string, value: string) => {
    const newParams = new URLSearchParams(searchParams);
    if (value) {
      newParams.set(key, value);
    } else {
      newParams.delete(key);
    }
    setSearchParams(newParams);
  };

  // Load filter options
  useEffect(() => {
    getDocTypeCatalog()
      .then((catalog) => setDocTypeOptions(catalog.map((c) => c.doc_type).sort()))
      .catch(() => setDocTypeOptions([]));

    listClaims()
      .then((claims) => setClaimOptions(claims.map((c) => c.claim_id).sort()))
      .catch(() => setClaimOptions([]));
  }, []);

  // Load documents
  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await listAllDocuments({
        search: search || undefined,
        doc_type: docType || undefined,
        claim_id: claimId || undefined,
        has_truth: hasTruth === "yes" ? true : hasTruth === "no" ? false : undefined,
        limit: 500, // Load more for browsing
      });

      setDocuments(response.documents);
      setTotal(response.total);

      // Auto-select first document if none selected
      if (response.documents.length > 0 && !selectedDocId) {
        setSelectedDocId(response.documents[0].doc_id);
        setSelectedClaimId(response.documents[0].claim_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, [search, docType, claimId, hasTruth]);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Load available runs when document selection changes
  useEffect(() => {
    async function loadRuns() {
      if (!selectedDocId || !selectedClaimId) {
        setAvailableRuns([]);
        setSelectedRunId(null);
        return;
      }

      try {
        const runs = await getDocRuns(selectedDocId, selectedClaimId);
        setAvailableRuns(runs);
        // Default to first (latest) run if no run selected
        if (runs.length > 0 && !selectedRunId) {
          setSelectedRunId(runs[0].run_id);
        }
      } catch (err) {
        console.error("Failed to load runs:", err);
        setAvailableRuns([]);
      }
    }

    loadRuns();
  }, [selectedDocId, selectedClaimId]);

  // Load document detail when selection or run changes
  const loadDetail = useCallback(async () => {
    if (!selectedDocId || !selectedClaimId) {
      setDocPayload(null);
      setFieldLabels([]);
      return;
    }

    try {
      setDetailLoading(true);
      const payload = await getDoc(selectedDocId, selectedClaimId, selectedRunId || undefined);
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
  }, [selectedDocId, selectedClaimId, selectedRunId]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  // Handle document selection
  const handleSelectDoc = (docId: string, docClaimId: string) => {
    if (docId !== selectedDocId) {
      if (hasUnsavedChanges) {
        const proceed = window.confirm("You have unsaved changes. Discard them?");
        if (!proceed) return;
      }
      setSelectedDocId(docId);
      setSelectedClaimId(docClaimId);
      setSelectedRunId(null); // Reset run selection for new document
    }
  };

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

  function handleUnverifiableField(
    fieldName: string,
    reason: "not_present_in_doc" | "unreadable_text" | "wrong_doc_type" | "cannot_verify" | "other"
  ) {
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

  // Save labels and update list
  async function handleSave() {
    if (!docPayload) return;

    try {
      setSaving(true);
      await saveLabels(docPayload.doc_id, "QA Console", notes, fieldLabels, docLabels);
      setHasUnsavedChanges(false);

      // Update the document in the list to show it has labels now
      setDocuments((prev) =>
        prev.map((d) =>
          d.doc_id === docPayload.doc_id ? { ...d, has_truth: true } : d
        )
      );

      // Find and select next unlabeled document
      const currentIndex = documents.findIndex((d) => d.doc_id === docPayload.doc_id);
      const nextUnlabeled = documents.slice(currentIndex + 1).find((d) => !d.has_truth);
      if (nextUnlabeled) {
        setSelectedDocId(nextUnlabeled.doc_id);
        setSelectedClaimId(nextUnlabeled.claim_id);
      }
    } catch (err) {
      console.error("Failed to save labels:", err);
      alert(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  // Quality status badge
  const QualityBadge = ({ status }: { status: string | null }) => {
    if (!status) return null;
    const styles: Record<string, string> = {
      pass: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
      warn: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
      fail: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    };
    return (
      <span className={`px-1.5 py-0.5 rounded text-xs ${styles[status] || ""}`}>
        {status}
      </span>
    );
  };

  const selectedDoc = documents.find((d) => d.doc_id === selectedDocId);

  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="bg-card border-b px-4 py-3 flex items-center gap-4 flex-wrap">
        <h2 className="font-semibold text-foreground">All Documents</h2>

        {/* Search */}
        <div className="relative w-48">
          <input
            type="text"
            value={search}
            onChange={(e) => updateParam("search", e.target.value)}
            placeholder="Search..."
            className="w-full pl-8 pr-3 py-1.5 text-sm border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <svg
            className="absolute left-2.5 top-2 w-4 h-4 text-muted-foreground/70"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>

        {/* Claim Filter */}
        <select
          value={claimId}
          onChange={(e) => updateParam("claim", e.target.value)}
          className="px-3 py-1.5 text-sm border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All Claims</option>
          {claimOptions.map((claim) => (
            <option key={claim} value={claim}>{claim}</option>
          ))}
        </select>

        {/* Doc Type Filter */}
        <select
          value={docType}
          onChange={(e) => updateParam("doc_type", e.target.value)}
          className="px-3 py-1.5 text-sm border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All Types</option>
          {docTypeOptions.map((type) => (
            <option key={type} value={type}>{type.replace(/_/g, " ")}</option>
          ))}
        </select>

        {/* Truth Filter */}
        <select
          value={hasTruth}
          onChange={(e) => updateParam("has_truth", e.target.value)}
          className="px-3 py-1.5 text-sm border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
        >
          <option value="">All</option>
          <option value="yes">Has truth</option>
          <option value="no">No truth</option>
        </select>

        {/* Count */}
        <div className="text-sm text-muted-foreground ml-auto">
          {documents.length} of {total} documents
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Main 3-panel layout */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Document list */}
        <div className="w-72 border-r overflow-auto bg-card flex-shrink-0">
          {loading ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Loading...
            </div>
          ) : documents.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              No documents found
            </div>
          ) : (
            <div className="divide-y divide-border">
              {documents.map((doc) => (
                <div
                  key={`${doc.claim_id}-${doc.doc_id}`}
                  onClick={() => handleSelectDoc(doc.doc_id, doc.claim_id)}
                  className={cn(
                    "p-3 cursor-pointer hover:bg-muted/50 transition-colors",
                    selectedDocId === doc.doc_id && "bg-accent/10 border-l-2 border-accent"
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-foreground truncate flex-1">
                      {doc.filename}
                    </span>
                    {doc.has_truth && (
                      <svg className="w-3.5 h-3.5 text-success flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground truncate">
                      {doc.claim_id}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {doc.doc_type.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <QualityBadge status={doc.quality_status} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Center: Document viewer */}
        {selectedDoc && docPayload ? (
          <>
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
                <div className="flex items-center justify-between gap-2">
                  <h3 className="font-medium text-foreground flex-shrink-0">Ground Truth</h3>
                  {/* Run Selector */}
                  {availableRuns.length > 0 && (
                    <select
                      value={selectedRunId || ""}
                      onChange={(e) => setSelectedRunId(e.target.value || null)}
                      className="flex-1 min-w-0 px-2 py-1 text-xs border rounded bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary truncate"
                      title="Select extraction run"
                    >
                      {availableRuns.map((run) => (
                        <option key={run.run_id} value={run.run_id}>
                          {run.run_id.slice(0, 8)}... ({run.model})
                          {run.extraction ? ` - ${run.extraction.gate_status || "no gate"}` : " - no extraction"}
                        </option>
                      ))}
                    </select>
                  )}
                  <div className="flex items-center gap-2 flex-shrink-0">
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
                          : "bg-primary text-primary-foreground hover:bg-primary/90"
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
                  placeholder="Optional notes..."
                  rows={2}
                  className="w-full px-3 py-2 text-sm border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                />
              </div>
            </div>
          </>
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
