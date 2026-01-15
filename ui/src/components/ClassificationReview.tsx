import { useState, useEffect, useMemo, useCallback } from "react";
import { cn } from "../lib/utils";
import { formatDocType } from "../lib/formatters";
import {
  ScoreBadge,
  StatusBadge,
  PendingBadge,
  ConfirmedBadge,
  SelectToViewEmptyState,
  Spinner,
  NoDocumentsEmptyState,
} from "./shared";
import { DocumentViewer } from "./DocumentViewer";
import { ClassificationInfoPanel } from "./ClassificationInfoPanel";
import type {
  ClassificationDoc,
  ClassificationDetail,
  DocPayload,
  DocTypeCatalogEntry,
} from "../types";
import {
  listClassificationDocs,
  getClassificationDetail,
  saveClassificationLabel,
  getDocTypeCatalog,
  getDoc,
  getDocSourceUrl,
  type ClaimRunInfo,
} from "../api/client";

interface ClassificationReviewProps {
  batches: ClaimRunInfo[];
  selectedBatchId: string | null;
  onBatchChange: (batchId: string | null) => void;
}

export function ClassificationReview({
  batches: _batches,
  selectedBatchId,
  onBatchChange: _onBatchChange,
}: ClassificationReviewProps) {
  // Batch context now handled by BatchWorkspace
  void _batches;
  void _onBatchChange;

  // Doc list state
  const [docs, setDocs] = useState<ClassificationDoc[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);

  // Selected doc detail
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClassificationDetail | null>(null);
  const [docPayload, setDocPayload] = useState<DocPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Review state
  const [reviewAction, setReviewAction] = useState<"confirm" | "change">("confirm");
  const [newDocType, setNewDocType] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "reviewed">("all");
  const [claimFilter, setClaimFilter] = useState<"all" | string>("all");
  const [docTypeFilter, setDocTypeFilter] = useState<"all" | string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Doc type catalog
  const [docTypeCatalog, setDocTypeCatalog] = useState<DocTypeCatalogEntry[]>([]);

  // Load doc type catalog on mount
  useEffect(() => {
    getDocTypeCatalog()
      .then(setDocTypeCatalog)
      .catch((err) => console.error("Failed to load doc type catalog:", err));
  }, []);

  // Get catalog entry for current predicted type
  const currentDocTypeInfo = useMemo(() => {
    if (!detail) return null;
    return docTypeCatalog.find((d) => d.doc_type === detail.predicted_type) || null;
  }, [detail, docTypeCatalog]);

  // Load detail - takes explicit params to avoid closure issues
  const loadDetail = useCallback(async (docId: string, runId: string, claimId: string) => {
    try {
      setDetailLoading(true);
      // Fetch classification detail first
      const classificationData = await getClassificationDetail(docId, runId, claimId);
      setDetail(classificationData);

      // Then fetch full doc payload for PDF viewer
      const docData = await getDoc(docId, classificationData.claim_id, runId);
      setDocPayload(docData);

      // Pre-populate form from existing label
      if (classificationData.existing_label) {
        setReviewAction(classificationData.existing_label.doc_type_correct ? "confirm" : "change");
        setNewDocType(classificationData.existing_label.doc_type_truth || "");
        setNotes(classificationData.existing_label.notes || "");
      } else {
        setReviewAction("confirm");
        setNewDocType("");
        setNotes("");
      }
    } catch (err) {
      console.error("Failed to load detail:", err);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  // Load docs and auto-select first document
  const loadDocs = useCallback(async (runId: string) => {
    try {
      setDocsLoading(true);
      const data = await listClassificationDocs(runId);
      setDocs(data);
      // Auto-select first document and load its detail immediately
      if (data.length > 0) {
        setSelectedDocId(data[0].doc_id);
        loadDetail(data[0].doc_id, runId, data[0].claim_id);
      }
    } catch (err) {
      console.error("Failed to load docs:", err);
    } finally {
      setDocsLoading(false);
    }
  }, [loadDetail]);

  // Load docs when run changes
  useEffect(() => {
    if (selectedBatchId) {
      // Reset selection when batch changes
      setSelectedDocId(null);
      setDetail(null);
      setDocPayload(null);
      loadDocs(selectedBatchId);
    }
  }, [selectedBatchId, loadDocs]);

  // Load detail when doc selected manually (not auto-selected from loadDocs)
  const handleSelectDoc = useCallback((docId: string) => {
    if (docId !== selectedDocId && selectedBatchId) {
      const doc = docs.find(d => d.doc_id === docId);
      if (doc) {
        setSelectedDocId(docId);
        loadDetail(docId, selectedBatchId, doc.claim_id);
      }
    }
  }, [selectedDocId, selectedBatchId, loadDetail, docs]);

  async function handleSave() {
    if (!detail || !selectedBatchId) return;

    try {
      setSaving(true);
      await saveClassificationLabel(detail.doc_id, {
        claim_id: detail.claim_id,
        doc_type_correct: reviewAction === "confirm",
        doc_type_truth: reviewAction === "change" ? newDocType : undefined,
        notes: notes || undefined,
      });

      // Refresh docs
      await loadDocs(selectedBatchId);

      // Move to next pending doc
      const nextPending = docs.find(
        (d) => d.review_status === "pending" && d.doc_id !== detail.doc_id
      );
      if (nextPending) {
        setSelectedDocId(nextPending.doc_id);
      }
    } catch (err) {
      console.error("Failed to save:", err);
    } finally {
      setSaving(false);
    }
  }

  // Get unique claims and doc types for filters
  const claims = useMemo(() => Array.from(new Set(docs.map((d) => d.claim_id))).sort(), [docs]);
  const docTypes = useMemo(() => Array.from(new Set(docs.map((d) => d.predicted_type))).sort(), [docs]);

  // Filter docs - memoized to prevent unnecessary re-renders
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
      if (statusFilter === "pending" && doc.review_status !== "pending") {
        return false;
      }
      if (statusFilter === "reviewed" && doc.review_status === "pending") {
        return false;
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
    if (docsLoading || !selectedBatchId) return;

    if (filteredDocs.length === 0) {
      // No docs match filter - clear selection
      if (selectedDocId) {
        setSelectedDocId(null);
        setDetail(null);
        setDocPayload(null);
      }
      return;
    }

    // Check if current selection is in filtered list
    const selectionInList = selectedDocId && filteredDocs.some(d => d.doc_id === selectedDocId);

    if (!selectionInList && filteredDocs[0]) {
      // Select first doc in filtered list
      const firstDoc = filteredDocs[0];
      setSelectedDocId(firstDoc.doc_id);
      loadDetail(firstDoc.doc_id, selectedBatchId, firstDoc.claim_id);
    }
  }, [filteredDocs, selectedDocId, selectedBatchId, loadDetail, docsLoading]);

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
              {formatDocType(type)}
            </option>
          ))}
        </select>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as "all" | "pending" | "reviewed")}
          className="px-3 py-1.5 text-sm border rounded-md bg-card focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="reviewed">Reviewed</option>
        </select>

        {/* Count */}
        <div className="text-sm text-muted-foreground">
          {filteredDocs.length} of {docs.length} documents
        </div>
      </div>

      {/* Main content: 3-column layout */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Doc List (narrow) */}
        <div className="w-72 border-r overflow-auto bg-card flex-shrink-0">
          {docsLoading ? (
            <div className="p-8 flex justify-center"><Spinner /></div>
          ) : filteredDocs.length === 0 ? (
            <NoDocumentsEmptyState />
          ) : (
            <div className="divide-y">
              {filteredDocs.map((doc) => (
                <div
                  key={doc.doc_id}
                  onClick={() => handleSelectDoc(doc.doc_id)}
                  className={cn(
                    "p-3 cursor-pointer hover:bg-muted/50 transition-colors",
                    selectedDocId === doc.doc_id && "bg-accent/10 border-l-2 border-accent"
                  )}
                >
                  <div className="font-medium text-sm text-foreground truncate" title={doc.filename}>
                    {doc.filename}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground truncate">
                      {formatDocType(doc.predicted_type)}
                    </span>
                    <ScoreBadge value={Math.round(doc.confidence * 100)} />
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-xs text-muted-foreground/70 truncate">
                      {doc.claim_id}
                    </span>
                    <ReviewStatusBadge status={doc.review_status} />
                  </div>
                  {doc.doc_type_truth && (
                    <div className="text-xs text-warning mt-1">
                      Changed to: {formatDocType(doc.doc_type_truth)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Center: Document Viewer (flexible) */}
        <div className="flex-1 border-r bg-card min-w-0">
          {detailLoading ? (
            <div className="flex items-center justify-center h-full">
              <Spinner />
            </div>
          ) : !detail || !docPayload ? (
            <div className="flex items-center justify-center h-full bg-muted/50">
              <SelectToViewEmptyState itemType="document" />
            </div>
          ) : (
            <DocumentViewer
              pages={docPayload.pages}
              sourceUrl={getDocSourceUrl(detail.doc_id, detail.claim_id)}
              hasPdf={docPayload.has_pdf}
              hasImage={docPayload.has_image}
              claimId={detail.claim_id}
              docId={detail.doc_id}
            />
          )}
        </div>

        {/* Right: Classification Info Panel (fixed width) */}
        <div className="w-[400px] flex-shrink-0 bg-muted/50">
          {detailLoading ? (
            <div className="flex items-center justify-center h-full">
              <Spinner />
            </div>
          ) : !detail ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Select a document to review
            </div>
          ) : (
            <ClassificationInfoPanel
              detail={detail}
              docTypeInfo={currentDocTypeInfo}
              reviewAction={reviewAction}
              newDocType={newDocType}
              notes={notes}
              saving={saving}
              onReviewActionChange={setReviewAction}
              onNewDocTypeChange={setNewDocType}
              onNotesChange={setNotes}
              onSave={handleSave}
            />
          )}
        </div>
      </div>
    </div>
  );
}

// Helper components

function ReviewStatusBadge({ status }: { status: "pending" | "confirmed" | "overridden" }) {
  if (status === "pending") return <PendingBadge />;
  if (status === "confirmed") return <ConfirmedBadge />;
  // Overridden
  return <StatusBadge variant="warning">Overridden</StatusBadge>;
}
