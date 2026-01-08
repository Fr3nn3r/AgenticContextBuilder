import { useState, useEffect } from "react";
import { cn } from "../lib/utils";
import type {
  ClassificationDoc,
  ClassificationDetail,
  ClassificationStats,
} from "../types";
import {
  listClaimRuns,
  listClassificationDocs,
  getClassificationDetail,
  saveClassificationLabel,
  getClassificationStats,
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

export function ClassificationReview() {
  // Run selection
  const [runs, setRuns] = useState<ClaimRunInfo[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Doc list state
  const [docs, setDocs] = useState<ClassificationDoc[]>([]);
  const [docsLoading, setDocsLoading] = useState(false);

  // Selected doc detail
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ClassificationDetail | null>(null);
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

  // Load runs on mount
  useEffect(() => {
    loadRuns();
  }, []);

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
    }
  }, [selectedDocId, selectedRunId]);

  async function loadRuns() {
    try {
      const data = await listClaimRuns();
      setRuns(data);
      if (data.length > 0) {
        setSelectedRunId(data[0].run_id);
      }
    } catch (err) {
      console.error("Failed to load runs:", err);
    }
  }

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
      const data = await getClassificationDetail(docId, runId);
      setDetail(data);
      // Pre-populate form from existing label
      if (data.existing_label) {
        setReviewAction(data.existing_label.doc_type_correct ? "confirm" : "change");
        setNewDocType(data.existing_label.doc_type_truth || "");
        setNotes(data.existing_label.notes || "");
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

  // Filter docs
  const filteredDocs = docs.filter((d) => {
    if (statusFilter === "pending") return d.review_status === "pending";
    if (statusFilter === "reviewed") return d.review_status !== "pending";
    return true;
  });

  return (
    <div className="h-full flex flex-col">
      {/* Header with run selector and KPIs */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4">
            <label className="text-sm text-gray-600">Run:</label>
            <select
              value={selectedRunId || ""}
              onChange={(e) => setSelectedRunId(e.target.value || null)}
              className="border rounded-md px-3 py-1.5 text-sm"
            >
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id} {run.timestamp ? `(${new Date(run.timestamp).toLocaleDateString()})` : ""}
                </option>
              ))}
            </select>
          </div>

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
          <div className="grid grid-cols-4 gap-4">
            <KPICard
              label="Documents"
              value={stats.docs_total}
              subtext={`${stats.docs_reviewed} reviewed`}
            />
            <KPICard
              label="Reviewed"
              value={`${stats.docs_total > 0 ? Math.round((stats.docs_reviewed / stats.docs_total) * 100) : 0}%`}
              subtext={`${stats.docs_reviewed} of ${stats.docs_total}`}
            />
            <KPICard
              label="Overrides"
              value={stats.overrides_count}
              subtext={stats.docs_reviewed > 0 ? `${Math.round((stats.overrides_count / stats.docs_reviewed) * 100)}% of reviewed` : ""}
            />
            <KPICard
              label="Avg Confidence"
              value={`${Math.round(stats.avg_confidence * 100)}%`}
              subtext="classification confidence"
            />
          </div>
        )}
      </div>

      {/* Main content: doc list + detail panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Doc List */}
        <div className="w-1/2 border-r overflow-auto bg-white">
          {docsLoading ? (
            <div className="p-8 text-center text-gray-500">Loading...</div>
          ) : filteredDocs.length === 0 ? (
            <div className="p-8 text-center text-gray-500">No documents found</div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Doc</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Conf.</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
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
                      <ConfidenceBadge confidence={doc.confidence} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={doc.review_status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail Panel */}
        <div className="w-1/2 overflow-auto bg-gray-50 p-6">
          {detailLoading ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              Loading...
            </div>
          ) : !detail ? (
            <div className="flex items-center justify-center h-full text-gray-500">
              Select a document to review
            </div>
          ) : (
            <div className="space-y-6">
              {/* Doc Info */}
              <div className="bg-white rounded-lg p-4 shadow-sm">
                <h3 className="font-medium text-gray-900 mb-2">{detail.filename}</h3>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-gray-500">Claim:</span>{" "}
                    <span className="text-gray-900">{detail.claim_id}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">Confidence:</span>{" "}
                    <span className="text-gray-900">{Math.round(detail.confidence * 100)}%</span>
                  </div>
                </div>
              </div>

              {/* Classification Info */}
              <div className="bg-white rounded-lg p-4 shadow-sm">
                <h4 className="text-sm font-medium text-gray-700 mb-2">Predicted Type</h4>
                <div className="text-lg font-semibold text-gray-900 mb-3">
                  {formatDocType(detail.predicted_type)}
                </div>

                {detail.summary && (
                  <div className="mb-3">
                    <h4 className="text-sm font-medium text-gray-700 mb-1">Summary</h4>
                    <p className="text-sm text-gray-600">{detail.summary}</p>
                  </div>
                )}

                {detail.signals && detail.signals.length > 0 && (
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-1">Signals</h4>
                    <ul className="space-y-1">
                      {detail.signals.map((signal, i) => (
                        <li key={i} className="text-sm text-gray-600 flex items-start gap-2">
                          <span className="text-green-500 mt-0.5">*</span>
                          {signal}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {detail.key_hints && Object.keys(detail.key_hints).length > 0 && (
                  <div className="mt-3">
                    <h4 className="text-sm font-medium text-gray-700 mb-1">Key Hints</h4>
                    <div className="text-sm text-gray-600">
                      {Object.entries(detail.key_hints).map(([key, value]) => (
                        <div key={key}>
                          <span className="text-gray-500">{key}:</span> {value}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Text Preview */}
              {detail.pages_preview && (
                <div className="bg-white rounded-lg p-4 shadow-sm">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Text Preview</h4>
                  <pre className="text-xs text-gray-600 whitespace-pre-wrap font-mono bg-gray-50 p-3 rounded max-h-40 overflow-auto">
                    {detail.pages_preview}
                  </pre>
                </div>
              )}

              {/* Review Actions */}
              <div className="bg-white rounded-lg p-4 shadow-sm">
                <h4 className="text-sm font-medium text-gray-700 mb-3">Review</h4>

                <div className="flex gap-2 mb-4">
                  <button
                    onClick={() => setReviewAction("confirm")}
                    className={cn(
                      "px-4 py-2 rounded-md text-sm font-medium transition-colors",
                      reviewAction === "confirm"
                        ? "bg-green-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    Confirm Type
                  </button>
                  <button
                    onClick={() => setReviewAction("change")}
                    className={cn(
                      "px-4 py-2 rounded-md text-sm font-medium transition-colors",
                      reviewAction === "change"
                        ? "bg-amber-600 text-white"
                        : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                    )}
                  >
                    Change Type
                  </button>
                </div>

                {reviewAction === "change" && (
                  <div className="mb-4">
                    <label className="block text-sm text-gray-600 mb-1">Correct Type:</label>
                    <select
                      value={newDocType}
                      onChange={(e) => setNewDocType(e.target.value)}
                      className="w-full border rounded-md px-3 py-2 text-sm"
                    >
                      <option value="">Select type...</option>
                      {DOC_TYPES.filter((t) => t !== detail.predicted_type).map((type) => (
                        <option key={type} value={type}>
                          {formatDocType(type)}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="mb-4">
                  <label className="block text-sm text-gray-600 mb-1">Notes (optional):</label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="w-full border rounded-md px-3 py-2 text-sm"
                    rows={2}
                    placeholder="Add notes..."
                  />
                </div>

                <button
                  onClick={handleSave}
                  disabled={saving || (reviewAction === "change" && !newDocType)}
                  className={cn(
                    "w-full px-4 py-2 rounded-md text-sm font-medium transition-colors",
                    saving || (reviewAction === "change" && !newDocType)
                      ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                      : "bg-gray-900 text-white hover:bg-gray-800"
                  )}
                >
                  {saving ? "Saving..." : "Save Review"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Helper components

function KPICard({ label, value, subtext }: { label: string; value: string | number; subtext?: string }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <div className="text-sm text-gray-600 mb-1">{label}</div>
      <div className="text-2xl font-semibold text-gray-900">{value}</div>
      {subtext && <div className="text-xs text-gray-500 mt-1">{subtext}</div>}
    </div>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const color = pct >= 90 ? "text-green-600" : pct >= 70 ? "text-amber-600" : "text-red-600";
  return <span className={cn("text-sm font-medium", color)}>{pct}%</span>;
}

function StatusBadge({ status }: { status: "pending" | "confirmed" | "overridden" }) {
  const styles = {
    pending: "bg-gray-100 text-gray-700",
    confirmed: "bg-green-100 text-green-700",
    overridden: "bg-amber-100 text-amber-700",
  };
  const labels = {
    pending: "Pending",
    confirmed: "Confirmed",
    overridden: "Overridden",
  };
  return (
    <span className={cn("px-2 py-1 rounded-full text-xs font-medium", styles[status])}>
      {labels[status]}
    </span>
  );
}

function formatDocType(type: string): string {
  return type
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
