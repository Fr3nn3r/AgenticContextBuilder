import { useState, useEffect, useMemo } from "react";
import { cn } from "../lib/utils";
import { formatDocType } from "../lib/formatters";
import {
  MetricCard,
  MetricCardRow,
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
  ClassificationStats,
  DocPayload,
  DocTypeCatalogEntry,
} from "../types";
import {
  listClassificationDocs,
  getClassificationDetail,
  saveClassificationLabel,
  getClassificationStats,
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

  // Stats
  const [stats, setStats] = useState<ClassificationStats | null>(null);

  // Filter
  const [statusFilter, setStatusFilter] = useState<"all" | "pending" | "reviewed">("all");

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

  // Load docs when run changes
  useEffect(() => {
    if (selectedBatchId) {
      loadDocs(selectedBatchId);
      loadStats(selectedBatchId);
    }
  }, [selectedBatchId]);

  // Load detail when doc selected
  useEffect(() => {
    if (selectedDocId && selectedBatchId) {
      loadDetail(selectedDocId, selectedBatchId);
    } else {
      setDetail(null);
      setDocPayload(null);
    }
  }, [selectedDocId, selectedBatchId]);

  async function loadDocs(runId: string) {
    try {
      setDocsLoading(true);
      const data = await listClassificationDocs(runId);
      setDocs(data);
    } catch (err) {
      console.error("Failed to load docs:", err);
    } finally {
      setDocsLoading(false);
    }
  }

  async function loadStats(runId: string) {
    try {
      const data = await getClassificationStats(runId);
      setStats(data);
    } catch (err) {
      console.error("Failed to load stats:", err);
    }
  }

  async function loadDetail(docId: string, runId: string) {
    try {
      setDetailLoading(true);
      // Fetch classification detail first
      const classificationData = await getClassificationDetail(docId, runId);
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
  }

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

      // Refresh docs and stats
      await Promise.all([
        loadDocs(selectedBatchId),
        loadStats(selectedBatchId),
      ]);

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

  // Filter docs
  const filteredDocs = docs.filter((d) => {
    if (statusFilter === "pending") return d.review_status === "pending";
    if (statusFilter === "reviewed") return d.review_status !== "pending";
    return true;
  });

  return (
    <div className="h-full flex flex-col">
      {/* Header with filters and KPIs */}
      <div className="bg-card border-b px-6 py-4 flex-shrink-0">
        <div className="flex items-center justify-end mb-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground">Show:</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as "all" | "pending" | "reviewed")}
              className="border rounded-md px-3 py-1.5 text-sm bg-background"
            >
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="reviewed">Reviewed</option>
            </select>
          </div>
        </div>

        {/* KPI Cards */}
        {stats && (
          <MetricCardRow columns={4}>
            <MetricCard
              label="Documents"
              value={stats.docs_total}
              subtext={`${stats.docs_reviewed} reviewed`}
            />
            <MetricCard
              label="Reviewed"
              value={`${stats.docs_total > 0 ? Math.round((stats.docs_reviewed / stats.docs_total) * 100) : 0}%`}
              subtext={`${stats.docs_reviewed} of ${stats.docs_total}`}
            />
            <MetricCard
              label="Overrides"
              value={stats.overrides_count}
              subtext={stats.docs_reviewed > 0 ? `${Math.round((stats.overrides_count / stats.docs_reviewed) * 100)}% of reviewed` : ""}
              variant={stats.overrides_count > 0 ? "warning" : "default"}
            />
            <MetricCard
              label="Avg Confidence"
              value={`${Math.round(stats.avg_confidence * 100)}%`}
              subtext="classification confidence"
            />
          </MetricCardRow>
        )}
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
                  onClick={() => setSelectedDocId(doc.doc_id)}
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
