import { useState, useEffect } from "react";
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
  RunSelector,
} from "./shared";
import { DocumentViewer } from "./DocumentViewer";
import type {
  ClassificationDoc,
  ClassificationDetail,
  ClassificationStats,
  DocPayload,
} from "../types";
import {
  listClassificationDocs,
  getClassificationDetail,
  saveClassificationLabel,
  getClassificationStats,
  getDoc,
  getDocSourceUrl,
  type ClaimRunInfo,
} from "../api/client";

// Document type options from the catalog
const DOC_TYPES = [
  "fnol_form",
  "insurance_policy",
  "police_report",
  "invoice",
  "id_document",
  "vehicle_registration",
  "certificate",
  "medical_report",
  "travel_itinerary",
  "customer_comm",
  "supporting_document",
];

interface ClassificationReviewProps {
  runs: ClaimRunInfo[];
  selectedRunId: string | null;
  onRunChange: (runId: string | null) => void;
}

export function ClassificationReview({
  runs,
  selectedRunId,
  onRunChange,
}: ClassificationReviewProps) {

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

  // Sorting state
  type SortColumn = "filename" | "predicted_type" | "confidence" | "review_status";
  const [sortColumn, setSortColumn] = useState<SortColumn>("filename");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  function handleSort(column: SortColumn) {
    if (sortColumn === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortColumn(column);
      setSortDirection("asc");
    }
  }

  // Load docs when run changes
  useEffect(() => {
    if (selectedRunId) {
      loadDocs(selectedRunId);
      loadStats(selectedRunId);
    }
  }, [selectedRunId]);

  // Load detail when doc selected
  useEffect(() => {
    if (selectedDocId && selectedRunId) {
      loadDetail(selectedDocId, selectedRunId);
    } else {
      setDetail(null);
      setDocPayload(null);
    }
  }, [selectedDocId, selectedRunId]);

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
    if (!detail || !selectedRunId) return;

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
        loadDocs(selectedRunId),
        loadStats(selectedRunId),
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

  // Filter and sort docs
  const filteredDocs = docs
    .filter((d) => {
      if (statusFilter === "pending") return d.review_status === "pending";
      if (statusFilter === "reviewed") return d.review_status !== "pending";
      return true;
    })
    .sort((a, b) => {
      let comparison = 0;
      switch (sortColumn) {
        case "filename":
          comparison = a.filename.localeCompare(b.filename);
          break;
        case "predicted_type":
          comparison = a.predicted_type.localeCompare(b.predicted_type);
          break;
        case "confidence":
          comparison = a.confidence - b.confidence;
          break;
        case "review_status":
          comparison = a.review_status.localeCompare(b.review_status);
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });

  return (
    <div className="h-full flex flex-col">
      {/* Header with run selector and KPIs */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <RunSelector
            runs={runs}
            selectedRunId={selectedRunId}
            onRunChange={(id) => onRunChange(id || null)}
            showMetadata
          />

          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">Show:</label>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as "all" | "pending" | "reviewed")}
              className="border rounded-md px-3 py-1.5 text-sm"
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

      {/* Main content: doc list + detail panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Doc List */}
        <div className="w-1/2 border-r overflow-auto bg-white">
          {docsLoading ? (
            <div className="p-8 flex justify-center"><Spinner /></div>
          ) : filteredDocs.length === 0 ? (
            <NoDocumentsEmptyState />
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort("filename")}
                  >
                    <div className="flex items-center gap-1">
                      Doc
                      <SortIcon active={sortColumn === "filename"} direction={sortDirection} />
                    </div>
                  </th>
                  <th
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort("predicted_type")}
                  >
                    <div className="flex items-center gap-1">
                      Type
                      <SortIcon active={sortColumn === "predicted_type"} direction={sortDirection} />
                    </div>
                  </th>
                  <th
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort("confidence")}
                  >
                    <div className="flex items-center gap-1">
                      Conf.
                      <SortIcon active={sortColumn === "confidence"} direction={sortDirection} />
                    </div>
                  </th>
                  <th
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer hover:bg-gray-100"
                    onClick={() => handleSort("review_status")}
                  >
                    <div className="flex items-center gap-1">
                      Status
                      <SortIcon active={sortColumn === "review_status"} direction={sortDirection} />
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {filteredDocs.map((doc) => (
                  <tr
                    key={doc.doc_id}
                    onClick={() => setSelectedDocId(doc.doc_id)}
                    className={cn(
                      "cursor-pointer hover:bg-gray-50",
                      selectedDocId === doc.doc_id && "bg-blue-50"
                    )}
                  >
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-gray-900 truncate max-w-[200px]">
                        {doc.filename}
                      </div>
                      <div className="text-xs text-gray-500">{doc.claim_id}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-gray-700">{formatDocType(doc.predicted_type)}</span>
                      {doc.doc_type_truth && (
                        <div className="text-xs text-amber-600">
                          Changed to: {formatDocType(doc.doc_type_truth)}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge value={Math.round(doc.confidence * 100)} />
                    </td>
                    <td className="px-4 py-3">
                      <ReviewStatusBadge status={doc.review_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail Panel - Split View */}
        <div className="w-1/2 flex flex-col overflow-hidden">
          {detailLoading ? (
            <div className="flex items-center justify-center h-full bg-gray-50">
              <Spinner />
            </div>
          ) : !detail ? (
            <div className="flex items-center justify-center h-full bg-gray-50">
              <SelectToViewEmptyState itemType="document" />
            </div>
          ) : (
            <>
              {/* Top: Document Viewer */}
              <div className="h-1/2 border-b bg-white">
                {docPayload ? (
                  <DocumentViewer
                    pages={docPayload.pages}
                    sourceUrl={getDocSourceUrl(detail.doc_id, detail.claim_id)}
                    hasPdf={docPayload.has_pdf}
                    hasImage={docPayload.has_image}
                    claimId={detail.claim_id}
                    docId={detail.doc_id}
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-400">
                    <Spinner />
                  </div>
                )}
              </div>

              {/* Bottom: Classification Review Panel */}
              <div className="h-1/2 overflow-auto bg-gray-50 p-4">
                <div className="space-y-4">
                  {/* Doc Info Header */}
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-gray-900">{detail.filename}</h3>
                      <div className="text-xs text-gray-500">
                        {detail.claim_id} &bull; {Math.round(detail.confidence * 100)}% confidence
                      </div>
                    </div>
                    <ScoreBadge value={Math.round(detail.confidence * 100)} />
                  </div>

                  {/* Classification Info */}
                  <div className="bg-white rounded-lg p-3 shadow-sm">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-gray-500">Predicted Type</span>
                      <span className="text-sm font-semibold text-gray-900">
                        {formatDocType(detail.predicted_type)}
                      </span>
                    </div>

                    {detail.summary && (
                      <p className="text-xs text-gray-600 mb-2">{detail.summary}</p>
                    )}

                    {detail.signals && detail.signals.length > 0 && (
                      <div className="text-xs text-gray-500">
                        Signals: {detail.signals.slice(0, 3).join(", ")}
                        {detail.signals.length > 3 && ` +${detail.signals.length - 3} more`}
                      </div>
                    )}
                  </div>

                  {/* Review Actions */}
                  <div className="bg-white rounded-lg p-3 shadow-sm">
                    <div className="flex gap-2 mb-3">
                      <button
                        onClick={() => setReviewAction("confirm")}
                        className={cn(
                          "flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                          reviewAction === "confirm"
                            ? "bg-green-600 text-white"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        )}
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setReviewAction("change")}
                        className={cn(
                          "flex-1 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                          reviewAction === "change"
                            ? "bg-amber-600 text-white"
                            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                        )}
                      >
                        Change Type
                      </button>
                    </div>

                    {reviewAction === "change" && (
                      <select
                        value={newDocType}
                        onChange={(e) => setNewDocType(e.target.value)}
                        className="w-full border rounded-md px-2 py-1.5 text-sm mb-3"
                      >
                        <option value="">Select correct type...</option>
                        {DOC_TYPES.filter((t) => t !== detail.predicted_type).map((type) => (
                          <option key={type} value={type}>
                            {formatDocType(type)}
                          </option>
                        ))}
                      </select>
                    )}

                    <textarea
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      className="w-full border rounded-md px-2 py-1.5 text-sm mb-3"
                      rows={2}
                      placeholder="Notes (optional)..."
                    />

                    <button
                      onClick={handleSave}
                      disabled={saving || (reviewAction === "change" && !newDocType)}
                      className={cn(
                        "w-full px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                        saving || (reviewAction === "change" && !newDocType)
                          ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                          : "bg-gray-900 text-white hover:bg-gray-800"
                      )}
                    >
                      {saving ? "Saving..." : "Save Review"}
                    </button>
                  </div>
                </div>
              </div>
            </>
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

function SortIcon({ active, direction }: { active: boolean; direction: "asc" | "desc" }) {
  if (!active) {
    return (
      <svg className="w-3 h-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
      </svg>
    );
  }
  return (
    <svg className="w-3 h-3 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      {direction === "asc" ? (
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
      )}
    </svg>
  );
}
