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
    text_readable: "good",
  });
  const [reviewer, setReviewer] = useState("");
  const [notes, setNotes] = useState("");

  // Highlight state
  const [highlightQuote, setHighlightQuote] = useState<string | undefined>();
  const [highlightPage, setHighlightPage] = useState<number | undefined>();

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
        // Initialize field labels from extraction fields
        setFieldLabels(
          data.extraction.fields.map((f) => ({
            field_name: f.name,
            judgement: "unknown" as const,
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

  function handleLabelChange(
    fieldName: string,
    judgement: "correct" | "incorrect" | "unknown"
  ) {
    setFieldLabels((prev) =>
      prev.map((l) =>
        l.field_name === fieldName ? { ...l, judgement } : l
      )
    );
  }

  function handleQuoteClick(quote: string, page: number) {
    setHighlightQuote(quote);
    setHighlightPage(page);
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
    <div className="space-y-4">
      {/* Document header */}
      <div className="bg-card rounded-lg border p-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">{doc.filename}</h2>
            <div className="text-sm text-muted-foreground">
              {doc.doc_type} &middot; {doc.language} &middot; {doc.pages.length} pages
            </div>
          </div>
          <div className="flex items-center gap-4">
            {qualityStatus && (
              <QualityBadge status={qualityStatus} />
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className={cn(
                "px-4 py-2 rounded-md font-medium transition-colors",
                saving
                  ? "bg-secondary text-muted-foreground"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
              )}
            >
              {saving ? "Saving..." : "Save Labels"}
            </button>
          </div>
        </div>
      </div>

      {/* Main content: split view */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4" style={{ height: "calc(100vh - 280px)" }}>
        {/* Left: Page viewer */}
        <div className="bg-card rounded-lg border overflow-hidden">
          <div className="p-2 border-b bg-secondary/30">
            <h3 className="font-medium">Document Text</h3>
          </div>
          <div className="h-full overflow-hidden" style={{ height: "calc(100% - 40px)" }}>
            <PageViewer
              pages={doc.pages}
              highlightQuote={highlightQuote}
              highlightPage={highlightPage}
            />
          </div>
        </div>

        {/* Right: Fields + Labels */}
        <div className="bg-card rounded-lg border overflow-hidden flex flex-col">
          <div className="p-2 border-b bg-secondary/30">
            <h3 className="font-medium">Extracted Fields</h3>
          </div>

          {/* Fields */}
          <div className="flex-1 overflow-auto">
            {extraction ? (
              <FieldsTable
                fields={extraction.fields}
                labels={fieldLabels}
                onLabelChange={handleLabelChange}
                onQuoteClick={handleQuoteClick}
              />
            ) : (
              <div className="p-4 text-muted-foreground">
                No extraction results available
              </div>
            )}
          </div>

          {/* Doc-level labels & reviewer */}
          <div className="border-t p-4 space-y-3">
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
                  className="rounded"
                />
                <span className="text-sm">Doc type correct</span>
              </label>

              <select
                value={docLabels.text_readable}
                onChange={(e) =>
                  setDocLabels((prev) => ({
                    ...prev,
                    text_readable: e.target.value as "good" | "warn" | "poor",
                  }))
                }
                className="text-sm border rounded px-2 py-1"
              >
                <option value="good">Text: Good</option>
                <option value="warn">Text: Warn</option>
                <option value="poor">Text: Poor</option>
              </select>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Reviewer name"
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
                className="flex-1 border rounded px-2 py-1 text-sm"
              />
              <input
                type="text"
                placeholder="Notes (optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="flex-1 border rounded px-2 py-1 text-sm"
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
      {status.toUpperCase()}
    </span>
  );
}
