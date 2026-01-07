import { useState, useEffect } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { getClaimReview, getDoc, saveLabels, getDocSourceUrl } from "../api/client";
import type { ClaimReviewPayload, DocPayload, FieldLabel, DocLabels, DocSummary } from "../types";
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
  const [savingDocId, setSavingDocId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Review state
  const [notes, setNotes] = useState("");
  const [docTypeCorrect, setDocTypeCorrect] = useState<"yes" | "no" | "unsure">("yes");

  // Field-level labels state
  const [fieldLabels, setFieldLabels] = useState<FieldLabel[]>([]);

  // Highlight state for evidence
  const [highlightQuote, setHighlightQuote] = useState<string | undefined>();
  const [highlightPage, setHighlightPage] = useState<number | undefined>();
  const [highlightCharStart, setHighlightCharStart] = useState<number | undefined>();
  const [highlightCharEnd, setHighlightCharEnd] = useState<number | undefined>();
  const [highlightValue, setHighlightValue] = useState<string | undefined>();

  // Active doc ID from URL or auto-selected
  const activeDocId = searchParams.get("doc") || claimData?.default_doc_id;

  // Current doc index for navigation
  const currentDocIndex = claimData?.docs.findIndex(d => d.doc_id === activeDocId) ?? -1;

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
        setNotes(data.labels.review.notes || "");
        setDocTypeCorrect(data.labels.doc_labels.doc_type_correct ? "yes" : "no");
      } else if (data.extraction) {
        // Initialize field labels from extraction fields with UNLABELED state
        setFieldLabels(
          data.extraction.fields.map((f) => ({
            field_name: f.name,
            state: "UNLABELED" as const,
            notes: "",
          }))
        );
        setNotes("");
        setDocTypeCorrect("yes");
      } else {
        setFieldLabels([]);
        setNotes("");
        setDocTypeCorrect("yes");
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

  function handleQuoteClick(quote: string, page: number, charStart?: number, charEnd?: number, extractedValue?: string) {
    setHighlightQuote(quote);
    setHighlightPage(page);
    setHighlightCharStart(charStart);
    setHighlightCharEnd(charEnd);
    setHighlightValue(extractedValue);
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

  async function handleSaveReview(docId: string) {
    if (!claimId) return;

    try {
      setSavingDocId(docId);
      const docLabels: DocLabels = {
        doc_type_correct: docTypeCorrect === "yes",
      };
      // Use "system" as reviewer until accounts are implemented
      await saveLabels(docId, "system", notes, fieldLabels, docLabels);
      onSaved();
      // Reload claim data to update doc statuses
      await loadClaimData();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to save review");
    } finally {
      setSavingDocId(null);
    }
  }

  function handlePrevDoc() {
    if (claimData && currentDocIndex > 0) {
      handleSelectDoc(claimData.docs[currentDocIndex - 1].doc_id);
    }
  }

  function handleNextDoc() {
    if (claimData && currentDocIndex < claimData.docs.length - 1) {
      handleSelectDoc(claimData.docs[currentDocIndex + 1].doc_id);
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
      {/* Header: Back to Claims | Claim ID with nav | Doc navigation */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-b">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate("/claims")}
            className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Claims
          </button>

          {/* Claim navigation */}
          <div className="flex items-center gap-1">
            <span className="text-sm font-medium text-gray-900">Claim {claimData.claim_id}</span>
            <button
              data-testid="prev-claim"
              onClick={() => claimData.prev_claim_id && navigate(`/claims/${claimData.prev_claim_id}/review`)}
              disabled={!claimData.prev_claim_id}
              className={cn(
                "p-1 rounded transition-colors",
                claimData.prev_claim_id
                  ? "text-gray-600 hover:bg-gray-100"
                  : "text-gray-300 cursor-not-allowed"
              )}
              title="Previous claim"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <button
              data-testid="next-claim"
              onClick={() => claimData.next_claim_id && navigate(`/claims/${claimData.next_claim_id}/review`)}
              disabled={!claimData.next_claim_id}
              className={cn(
                "p-1 rounded transition-colors",
                claimData.next_claim_id
                  ? "text-gray-600 hover:bg-gray-100"
                  : "text-gray-300 cursor-not-allowed"
              )}
              title="Next claim"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Doc navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrevDoc}
            disabled={currentDocIndex <= 0}
            className={cn(
              "p-1 rounded transition-colors",
              currentDocIndex > 0
                ? "text-gray-700 hover:bg-gray-100"
                : "text-gray-300 cursor-not-allowed"
            )}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <span className="text-sm text-gray-600">
            {currentDocIndex + 1}/{claimData.docs.length}
          </span>
          <button
            onClick={handleNextDoc}
            disabled={currentDocIndex >= claimData.docs.length - 1}
            className={cn(
              "p-1 rounded transition-colors",
              currentDocIndex < claimData.docs.length - 1
                ? "text-gray-700 hover:bg-gray-100"
                : "text-gray-300 cursor-not-allowed"
            )}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Main content: 3-column layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Document list */}
        <div className="w-80 border-r bg-gray-50 flex flex-col overflow-hidden">
          <div className="p-3 border-b bg-white">
            <h2 className="font-semibold text-gray-900">Document Pack Review</h2>
            <div className="text-xs text-gray-500 mt-0.5">
              {claimData.doc_count} documents &middot; {claimData.unlabeled_count} to review
            </div>
          </div>
          <div className="flex-1 overflow-auto">
            {claimData.docs.map((doc) => (
              <DocListItem
                key={doc.doc_id}
                doc={doc}
                isActive={activeDocId === doc.doc_id}
                isSaving={savingDocId === doc.doc_id}
                onSelect={() => handleSelectDoc(doc.doc_id)}
                onSave={() => handleSaveReview(doc.doc_id)}
              />
            ))}
          </div>
        </div>

        {/* Center: Document viewer */}
        <div className="flex-1 overflow-hidden flex flex-col">
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
                highlightValue={highlightValue}
                claimId={claimId}
                docId={currentDoc.doc_id}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                Select a document
              </div>
            )}
          </div>
        </div>

        {/* Right: Extracted fields + Review controls */}
        <div className="w-96 border-l overflow-hidden flex flex-col">
          <div className="p-3 border-b bg-white">
            <h3 className="font-medium text-gray-900">Field Extraction</h3>
            {currentDoc && (
              <>
                <div className="text-xs text-gray-500 mt-0.5">
                  {currentDoc.filename}
                </div>
                {currentDoc.extraction && (
                  <div className="text-xs text-gray-400 mt-0.5">
                    Run: {currentDoc.extraction.run.run_id}
                  </div>
                )}
              </>
            )}
          </div>
          <div className="flex-1 overflow-auto">
            {currentDoc?.extraction ? (
              <FieldsTable
                fields={currentDoc.extraction.fields}
                labels={fieldLabels}
                onConfirm={handleConfirmField}
                onUnverifiable={handleUnverifiableField}
                onEditTruth={handleEditTruth}
                onQuoteClick={handleQuoteClick}
                docType={currentDoc.doc_type}
              />
            ) : (
              <div className="p-4 text-gray-500">
                {docLoading ? "Loading..." : "No extraction results available"}
              </div>
            )}
          </div>

          {/* Bottom: Review controls */}
          {currentDoc && (
            <div className="border-t p-3 bg-gray-50 space-y-3">
              {/* Doc type correct */}
              <div>
                <div className="text-sm text-gray-700 mb-1">
                  Document type "<span className="font-medium">{currentDoc.doc_type}</span>" correct?
                </div>
                <div className="flex gap-2">
                  {(["yes", "no", "unsure"] as const).map((option) => (
                    <button
                      key={option}
                      onClick={() => setDocTypeCorrect(option)}
                      className={cn(
                        "px-3 py-1 text-sm rounded border transition-colors",
                        docTypeCorrect === option
                          ? option === "yes"
                            ? "bg-green-100 border-green-500 text-green-700"
                            : option === "no"
                            ? "bg-red-100 border-red-500 text-red-700"
                            : "bg-yellow-100 border-yellow-500 text-yellow-700"
                          : "bg-white border-gray-300 text-gray-600 hover:bg-gray-50"
                      )}
                    >
                      {option.charAt(0).toUpperCase() + option.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              {/* Notes */}
              <input
                type="text"
                placeholder="Notes (optional)"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm bg-white"
              />

              {/* Save button */}
              <button
                data-testid="save-labels-btn"
                onClick={() => activeDocId && handleSaveReview(activeDocId)}
                disabled={savingDocId === activeDocId || !activeDocId}
                className={cn(
                  "w-full px-4 py-2 rounded-md font-medium transition-colors",
                  savingDocId === activeDocId
                    ? "bg-gray-200 text-gray-500 cursor-not-allowed"
                    : "bg-gray-900 text-white hover:bg-gray-800"
                )}
              >
                {savingDocId === activeDocId ? "Saving..." : "Save Labels"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface DocListItemProps {
  doc: DocSummary;
  isActive: boolean;
  isSaving: boolean;
  onSelect: () => void;
  onSave: () => void;
}

function DocListItem({ doc, isActive, isSaving, onSelect, onSave }: DocListItemProps) {
  return (
    <div
      data-testid="doc-strip-item"
      className={cn(
        "flex items-center gap-2 px-3 py-2 border-b cursor-pointer transition-colors",
        isActive ? "bg-blue-50 border-l-2 border-l-blue-500" : "hover:bg-gray-100"
      )}
      onClick={onSelect}
    >
      {/* Status dot */}
      <GateDot status={doc.quality_status} />

      {/* Doc info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={cn("text-sm font-medium truncate", isActive ? "text-blue-900" : "text-gray-900")}>
            {doc.doc_type}
          </span>
          {doc.has_labels && (
            <svg className="w-3.5 h-3.5 text-green-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          )}
        </div>
        <div className="text-xs text-gray-500 truncate">
          {doc.filename}
        </div>
      </div>

      {/* Confidence */}
      <div className="text-xs text-gray-400 flex-shrink-0">
        {Math.round(doc.confidence * 100)}%
      </div>

      {/* Save button */}
      <button
        onClick={(e) => {
          e.stopPropagation();
          onSave();
        }}
        disabled={isSaving || doc.has_labels}
        className={cn(
          "px-2 py-1 text-xs rounded transition-colors flex-shrink-0",
          doc.has_labels
            ? "bg-gray-100 text-gray-400 cursor-default"
            : isSaving
            ? "bg-gray-200 text-gray-500"
            : "bg-gray-900 text-white hover:bg-gray-800"
        )}
      >
        {isSaving ? "..." : doc.has_labels ? "Saved" : "Save"}
      </button>
    </div>
  );
}

function GateDot({ status }: { status: string | null }) {
  const colors: Record<string, string> = {
    pass: "bg-green-500",
    warn: "bg-yellow-500",
    fail: "bg-red-500",
  };
  return (
    <span className={cn("w-2 h-2 rounded-full flex-shrink-0", status ? colors[status] : "bg-gray-300")} />
  );
}
