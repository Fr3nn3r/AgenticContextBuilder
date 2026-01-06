import { useState, useEffect } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { getClaimReview, getDoc, saveLabels, getDocSourceUrl } from "../api/client";
import type { ClaimReviewPayload, DocPayload, FieldLabel, DocLabels } from "../types";
import { DocumentViewer } from "./DocumentViewer";
import { FieldsTable } from "./FieldsTable";
import { cn } from "../lib/utils";

interface ClaimReviewProps {
  onSaved: () => void;
}

export function ClaimReview({ onSaved }: ClaimReviewProps) {
  const { claimId } = useParams<{ claimId: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const [claimData, setClaimData] = useState<ClaimReviewPayload | null>(null);
  const [currentDoc, setCurrentDoc] = useState<DocPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [docLoading, setDocLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Doc-level review state
  const [docTypeCorrect, setDocTypeCorrect] = useState<boolean>(true);
  const [textReadable, setTextReadable] = useState<"good" | "warn" | "poor">("good");
  const [reviewer, setReviewer] = useState("");
  const [notes, setNotes] = useState("");

  // Field-level labels state
  const [fieldLabels, setFieldLabels] = useState<FieldLabel[]>([]);

  // Highlight state for evidence
  const [highlightQuote, setHighlightQuote] = useState<string | undefined>();
  const [highlightPage, setHighlightPage] = useState<number | undefined>();
  const [highlightCharStart, setHighlightCharStart] = useState<number | undefined>();
  const [highlightCharEnd, setHighlightCharEnd] = useState<number | undefined>();

  // Active doc ID from URL or auto-selected
  const activeDocId = searchParams.get("doc") || claimData?.default_doc_id;

  // Load claim data on mount
  useEffect(() => {
    if (claimId) {
      loadClaimData();
    }
  }, [claimId]);

  // Load document when activeDocId changes
  useEffect(() => {
    if (activeDocId && claimId) {
      loadDocument(activeDocId);
    }
  }, [activeDocId, claimId]);

  async function loadClaimData() {
    if (!claimId) return;
    try {
      setLoading(true);
      setError(null);
      const data = await getClaimReview(claimId);
      setClaimData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load claim");
    } finally {
      setLoading(false);
    }
  }

  async function loadDocument(docId: string) {
    if (!claimId) return;
    try {
      setDocLoading(true);
      const data = await getDoc(docId, claimId);
      setCurrentDoc(data);

      // Initialize review state from existing labels or extraction fields
      if (data.labels) {
        setFieldLabels(data.labels.field_labels || []);
        setDocTypeCorrect(data.labels.doc_labels.doc_type_correct ?? true);
        setTextReadable(data.labels.doc_labels.text_readable || "good");
        setReviewer(data.labels.review.reviewer || "");
        setNotes(data.labels.review.notes || "");
      } else if (data.extraction) {
        // Initialize field labels from extraction fields with "unknown" judgement
        setFieldLabels(
          data.extraction.fields.map((f) => ({
            field_name: f.name,
            judgement: "unknown" as const,
            notes: "",
          }))
        );
        setDocTypeCorrect(true);
        setTextReadable("good");
        setReviewer("");
        setNotes("");
      } else {
        setFieldLabels([]);
        setDocTypeCorrect(true);
        setTextReadable("good");
        setReviewer("");
        setNotes("");
      }
    } catch (err) {
      console.error("Failed to load document:", err);
    } finally {
      setDocLoading(false);
    }
  }

  function handleSelectDoc(docId: string) {
    setSearchParams({ doc: docId });
  }

  function handleQuoteClick(quote: string, page: number, charStart?: number, charEnd?: number) {
    setHighlightQuote(quote);
    setHighlightPage(page);
    setHighlightCharStart(charStart);
    setHighlightCharEnd(charEnd);
  }

  function handleFieldLabelChange(
    fieldName: string,
    judgement: "correct" | "incorrect" | "unknown"
  ) {
    setFieldLabels((prev) =>
      prev.map((l) =>
        l.field_name === fieldName ? { ...l, judgement } : l
      )
    );
  }

  async function handleSaveReview() {
    if (!activeDocId || !claimId) return;

    if (!reviewer.trim()) {
      alert("Please enter your name as reviewer");
      return;
    }

    try {
      setSaving(true);
      const docLabels: DocLabels = {
        doc_type_correct: docTypeCorrect,
        text_readable: textReadable,
      };
      await saveLabels(activeDocId, reviewer, notes, fieldLabels, docLabels);
      onSaved();
      alert("Labels saved successfully!");

      // Move to next unlabeled doc if available
      if (claimData) {
        const currentIndex = claimData.docs.findIndex(d => d.doc_id === activeDocId);
        const nextUnlabeled = claimData.docs.find((d, i) => i > currentIndex && !d.has_labels);
        if (nextUnlabeled) {
          handleSelectDoc(nextUnlabeled.doc_id);
        }
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save review");
    } finally {
      setSaving(false);
    }
  }

  function handlePrevClaim() {
    if (claimData?.prev_claim_id) {
      navigate(`/claims/${claimData.prev_claim_id}/review`);
    }
  }

  function handleNextClaim() {
    if (claimData?.next_claim_id) {
      navigate(`/claims/${claimData.next_claim_id}/review`);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">Loading claim...</div>
      </div>
    );
  }

  if (error || !claimData) {
    return (
      <div className="flex flex-col items-center justify-center h-full">
        <p className="text-red-600 mb-4">{error || "Claim not found"}</p>
        <button
          onClick={() => navigate("/claims")}
          className="px-4 py-2 bg-gray-900 text-white rounded-md hover:bg-gray-800"
        >
          Back to Claims
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Top navigation: Back + Prev/Next claim */}
      <div className="flex items-center justify-between px-6 py-3 bg-white border-b">
        <button
          onClick={() => navigate("/claims")}
          className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Back to Claims
        </button>
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrevClaim}
            disabled={!claimData.prev_claim_id}
            className={cn(
              "px-3 py-1.5 text-sm rounded border transition-colors",
              claimData.prev_claim_id
                ? "text-gray-700 hover:bg-gray-50"
                : "text-gray-300 cursor-not-allowed"
            )}
          >
            <span className="flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Prev Claim
            </span>
          </button>
          <button
            onClick={handleNextClaim}
            disabled={!claimData.next_claim_id}
            className={cn(
              "px-3 py-1.5 text-sm rounded border transition-colors",
              claimData.next_claim_id
                ? "text-gray-700 hover:bg-gray-50"
                : "text-gray-300 cursor-not-allowed"
            )}
          >
            <span className="flex items-center gap-1">
              Next Claim
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </span>
          </button>
        </div>
      </div>

      {/* Claim header */}
      <div className="px-6 py-4 bg-white border-b">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              {claimData.claim_id}
            </h2>
            <div className="text-sm text-gray-500">
              {claimData.lob} &middot; {claimData.doc_count} docs &middot; {claimData.unlabeled_count} unlabeled
            </div>
            <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
              <GateCounts counts={claimData.gate_counts} />
              {claimData.run_metadata && (
                <span>&middot; Run: {claimData.run_metadata.run_id}</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Doc header with Gate badge and Save button */}
      <div className="px-6 py-3 bg-white border-b flex items-center justify-between">
        <div>
          {currentDoc && (
            <>
              <div className="font-medium text-gray-900">{currentDoc.filename}</div>
              <div className="text-sm text-gray-500">
                {currentDoc.claim_id} &middot; {currentDoc.doc_type}
                {currentDoc.extraction && ` (${Math.round(currentDoc.extraction.doc.doc_type_confidence * 100)}%)`}
                {" "}&middot; {currentDoc.language.toUpperCase()} &middot; {currentDoc.pages.length} pages
              </div>
              {currentDoc.extraction && (
                <div className="text-xs text-gray-400 mt-1">
                  Run: {currentDoc.extraction.run.run_id} &middot; Extractor v{currentDoc.extraction.run.extractor_version}
                </div>
              )}
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          {currentDoc?.extraction?.quality_gate && (
            <QualityBadge status={currentDoc.extraction.quality_gate.status} />
          )}
          <button
            onClick={handleSaveReview}
            disabled={saving || !activeDocId}
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

      {/* Doc navigation strip */}
      <div className="px-6 py-2 bg-white border-b overflow-x-auto">
        <div className="flex gap-2">
          {claimData.docs.map((doc) => (
            <button
              key={doc.doc_id}
              onClick={() => handleSelectDoc(doc.doc_id)}
              className={cn(
                "flex items-center gap-2 px-3 py-2 rounded-lg text-sm whitespace-nowrap transition-colors",
                activeDocId === doc.doc_id
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              )}
            >
              <GateDot status={doc.quality_status} />
              <span className="font-medium">{doc.doc_type}</span>
              {doc.needs_vision && (
                <svg className="w-3.5 h-3.5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                </svg>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Main content: split view */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-0 overflow-hidden">
        {/* Left: Document viewer */}
        <div className="border-r overflow-hidden flex flex-col">
          <div className="flex-1 overflow-hidden">
            {docLoading ? (
              <div className="flex items-center justify-center h-full text-gray-500">
                Loading document...
              </div>
            ) : currentDoc ? (
              <DocumentViewer
                pages={currentDoc.pages}
                sourceUrl={claimId ? getDocSourceUrl(currentDoc.doc_id, claimId) : undefined}
                hasPdf={currentDoc.has_pdf}
                hasImage={currentDoc.has_image}
                extraction={currentDoc.extraction}
                highlightQuote={highlightQuote}
                highlightPage={highlightPage}
                highlightCharStart={highlightCharStart}
                highlightCharEnd={highlightCharEnd}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                Select a document
              </div>
            )}
          </div>
        </div>

        {/* Right: Extracted fields + Doc labels */}
        <div className="overflow-hidden flex flex-col">
          <div className="p-3 border-b bg-gray-50">
            <h3 className="font-medium text-gray-900">Extracted Fields</h3>
          </div>
          <div className="flex-1 overflow-auto">
            {currentDoc?.extraction ? (
              <FieldsTable
                fields={currentDoc.extraction.fields}
                labels={fieldLabels}
                onLabelChange={handleFieldLabelChange}
                onQuoteClick={handleQuoteClick}
              />
            ) : (
              <div className="p-4 text-gray-500">
                {docLoading ? "Loading..." : "No extraction results available"}
              </div>
            )}
          </div>

          {/* Doc-level labels & reviewer */}
          <div className="border-t p-4 space-y-3 bg-gray-50">
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={docTypeCorrect}
                  onChange={(e) => setDocTypeCorrect(e.target.checked)}
                  className="rounded border-gray-300"
                />
                <span className="text-sm text-gray-700">Doc type correct</span>
              </label>

              <select
                value={textReadable}
                onChange={(e) =>
                  setTextReadable(e.target.value as "good" | "warn" | "poor")
                }
                className="text-sm border border-gray-300 rounded px-2 py-1 bg-white"
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

function GateCounts({ counts }: { counts: { pass: number; warn: number; fail: number } }) {
  return (
    <span className="flex items-center gap-1">
      {counts.pass > 0 && <span className="text-green-600">{counts.pass} PASS</span>}
      {counts.warn > 0 && <span className="text-yellow-600">{counts.warn} WARN</span>}
      {counts.fail > 0 && <span className="text-red-600">{counts.fail} FAIL</span>}
    </span>
  );
}

function GateDot({ status }: { status: string | null }) {
  const colors: Record<string, string> = {
    pass: "bg-green-500",
    warn: "bg-yellow-500",
    fail: "bg-red-500",
  };
  return (
    <span className={cn("w-2 h-2 rounded-full", status ? colors[status] : "bg-gray-300")} />
  );
}

function QualityBadge({ status }: { status: "pass" | "warn" | "fail" }) {
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
