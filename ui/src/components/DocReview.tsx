import { useState, useEffect } from "react";
import { getDoc, saveLabels } from "../api/client";
import type { DocPayload, FieldLabel, DocLabels } from "../types";
import { PageViewer } from "./PageViewer";
import { FieldsTable } from "./FieldsTable";
import { cn } from "../lib/utils";

interface DocReviewProps {
  docId: string;
  onBack: () => void;
  onSaved: () => void;
}

export function DocReview({ docId, onBack, onSaved }: DocReviewProps) {
  const [doc, setDoc] = useState<DocPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Local label state
  const [fieldLabels, setFieldLabels] = useState<FieldLabel[]>([]);
  const [docLabels, setDocLabels] = useState<DocLabels>({
    doc_type_correct: true,
  });
  const [reviewer, setReviewer] = useState("");
  const [notes, setNotes] = useState("");

  // Highlight state with provenance info
  const [highlightQuote, setHighlightQuote] = useState<string | undefined>();
  const [highlightPage, setHighlightPage] = useState<number | undefined>();
  const [highlightCharStart, setHighlightCharStart] = useState<number | undefined>();
  const [highlightCharEnd, setHighlightCharEnd] = useState<number | undefined>();

  useEffect(() => {
    loadDoc();
  }, [docId]);

  async function loadDoc() {
    try {
      setLoading(true);
      setError(null);
      const data = await getDoc(docId);
      setDoc(data);

      // Initialize labels from existing or create new
      if (data.labels) {
        setFieldLabels(data.labels.field_labels);
        setDocLabels(data.labels.doc_labels);
        setReviewer(data.labels.review.reviewer);
        setNotes(data.labels.review.notes);
      } else if (data.extraction) {
        // Initialize field labels from extraction fields with UNLABELED state
        setFieldLabels(
          data.extraction.fields.map((f) => ({
            field_name: f.name,
            state: "UNLABELED" as const,
            notes: "",
          }))
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  }

  function handleConfirmField(fieldName: string, truthValue: string) {
    setFieldLabels((prev) =>
      prev.map((l) =>
        l.field_name === fieldName
          ? {
              ...l,
              state: "CONFIRMED" as const,
              truth_value: truthValue,
              unverifiable_reason: undefined,
              updated_at: new Date().toISOString(),
            }
          : l
      )
    );
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
  }

  function handleEditTruth(fieldName: string, newTruthValue: string) {
    setFieldLabels((prev) =>
      prev.map((l) =>
        l.field_name === fieldName && l.state === "CONFIRMED"
          ? { ...l, truth_value: newTruthValue, updated_at: new Date().toISOString() }
          : l
      )
    );
  }

  function handleQuoteClick(quote: string, page: number, charStart?: number, charEnd?: number) {
    setHighlightQuote(quote);
    setHighlightPage(page);
    setHighlightCharStart(charStart);
    setHighlightCharEnd(charEnd);
  }

  async function handleSave() {
    if (!reviewer.trim()) {
      alert("Please enter your name as reviewer");
      return;
    }

    try {
      setSaving(true);
      await saveLabels(docId, reviewer, notes, fieldLabels, docLabels);
      onSaved();
      alert("Labels saved successfully!");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save labels");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">Loading document...</div>
      </div>
    );
  }

  if (error || !doc) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <p className="text-destructive mb-4">{error || "Document not found"}</p>
          <button
            onClick={onBack}
            className="px-4 py-2 bg-secondary rounded-md"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const extraction = doc.extraction;
  const qualityStatus = extraction?.quality_gate.status;

  return (
    <div className="p-6 space-y-4">
      {/* Back button */}
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
        Back to Claim Workspace
      </button>

      {/* Document header - Extraction Review */}
      <div className="bg-white rounded-lg border p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Extraction Review</h2>
            <p className="text-xs text-gray-400 mb-1">Validate fields against source text</p>
            <div className="text-sm text-gray-700 font-medium">{doc.filename}</div>
            <div className="text-sm text-gray-500">
              {doc.claim_id} &middot; {doc.doc_type}
              {extraction && ` (${Math.round(extraction.doc.doc_type_confidence * 100)}%)`}
              {" "}&middot; {doc.language.toUpperCase()} &middot; {doc.pages.length} pages
            </div>
            {extraction && (
              <div className="text-xs text-gray-400 mt-1">
                Run: {extraction.run.run_id} &middot; Extractor v{extraction.run.extractor_version}
              </div>
            )}
          </div>
          <div className="flex items-center gap-3">
            {qualityStatus && (
              <QualityBadge status={qualityStatus} />
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className={cn(
                "px-4 py-2 rounded-md font-medium transition-colors",
                saving
                  ? "bg-gray-200 text-gray-500 cursor-not-allowed"
                  : "bg-gray-900 text-white hover:bg-gray-800"
              )}
            >
              {saving ? "Saving..." : "Save review"}
            </button>
          </div>
        </div>
      </div>

      {/* Main content: split view */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ height: "calc(100vh - 320px)" }}>
        {/* Left: Page viewer */}
        <div className="bg-white rounded-lg border overflow-hidden">
          <div className="p-3 border-b bg-gray-50">
            <h3 className="font-medium text-gray-900">Document Text</h3>
          </div>
          <div className="h-full overflow-hidden" style={{ height: "calc(100% - 48px)" }}>
            <PageViewer
              pages={doc.pages}
              highlightQuote={highlightQuote}
              highlightPage={highlightPage}
              highlightCharStart={highlightCharStart}
              highlightCharEnd={highlightCharEnd}
            />
          </div>
        </div>

        {/* Right: Fields + Labels */}
        <div className="bg-white rounded-lg border overflow-hidden flex flex-col">
          <div className="p-3 border-b bg-gray-50">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-gray-900">Extracted Fields</h3>
              {/* Label Status Summary */}
              <div className="flex items-center gap-3 text-xs">
                <span className={cn(
                  "px-2 py-1 rounded",
                  doc.labels ? "bg-green-100 text-green-700" : "bg-amber-100 text-amber-700"
                )}>
                  {doc.labels ? "Labels: Saved" : "Labels: Not saved"}
                </span>
                {extraction && (
                  <span className="text-gray-500">
                    Fields labeled: {fieldLabels.filter(l => l.state !== "UNLABELED").length}/{fieldLabels.length}
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Fields */}
          <div className="flex-1 overflow-auto">
            {extraction ? (
              <FieldsTable
                fields={extraction.fields}
                labels={fieldLabels}
                onConfirm={handleConfirmField}
                onUnverifiable={handleUnverifiableField}
                onEditTruth={handleEditTruth}
                onQuoteClick={handleQuoteClick}
                docType={doc.doc_type}
                runId={extraction.run.run_id}
              />
            ) : (
              <div className="p-4 text-gray-500">
                No extraction results available
              </div>
            )}
          </div>

          {/* Doc-level labels & reviewer */}
          <div className="border-t p-4 space-y-3 bg-gray-50">
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={docLabels.doc_type_correct}
                  onChange={(e) =>
                    setDocLabels((prev) => ({
                      ...prev,
                      doc_type_correct: e.target.checked,
                    }))
                  }
                  className="rounded border-gray-300"
                />
                <span className="text-sm text-gray-700">Doc type correct</span>
              </label>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Reviewer name"
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
                className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm bg-white"
              />
              <input
                type="text"
                placeholder="Notes (optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="flex-1 border border-gray-300 rounded px-3 py-2 text-sm bg-white"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function QualityBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pass: "bg-green-100 text-green-700",
    warn: "bg-yellow-100 text-yellow-700",
    fail: "bg-red-100 text-red-700",
  };

  return (
    <span className={cn("px-3 py-1 rounded-full text-sm font-medium", styles[status])}>
      Gate: {status.toUpperCase()}
    </span>
  );
}
