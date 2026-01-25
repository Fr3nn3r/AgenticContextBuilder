import { useState, useEffect } from "react";
import { X, Loader2, FileText, ExternalLink, ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "../../lib/utils";
import { getDoc, getDocSourceUrl } from "../../api/client";
import { DocumentViewer } from "../DocumentViewer";
import type { DocPayload, DocSummary } from "../../types";

export interface EvidenceLocation {
  docId: string;
  page: number | null;
  charStart: number | null;
  charEnd: number | null;
  highlightText?: string;
}

interface DocumentSlidePanelProps {
  claimId: string;
  evidence: EvidenceLocation | null;
  documents: DocSummary[];
  onClose: () => void;
}

/**
 * Sliding panel that displays a document with evidence highlighting.
 * Slides in from the right when evidence or document is clicked.
 */
export function DocumentSlidePanel({
  claimId,
  evidence,
  documents,
  onClose,
}: DocumentSlidePanelProps) {
  const [docData, setDocData] = useState<DocPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isOpen = evidence !== null;
  const currentDocId = evidence?.docId;

  // Find current document in the list
  const currentDocIndex = documents.findIndex((d) => d.doc_id === currentDocId);
  const currentDocSummary = currentDocIndex >= 0 ? documents[currentDocIndex] : null;

  // Load document data when evidence changes
  useEffect(() => {
    if (!currentDocId) {
      setDocData(null);
      return;
    }

    async function loadDoc() {
      setLoading(true);
      setError(null);
      try {
        const data = await getDoc(currentDocId!, claimId);
        setDocData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load document");
        setDocData(null);
      } finally {
        setLoading(false);
      }
    }

    loadDoc();
  }, [currentDocId, claimId]);

  // Navigate to previous/next document
  const goToDocument = (docId: string) => {
    if (evidence) {
      // Create new evidence with just the docId (no specific highlight)
      const newEvidence: EvidenceLocation = {
        docId,
        page: 1,
        charStart: null,
        charEnd: null,
      };
      // We need to update the parent - for now just reload
      window.history.replaceState(null, "", `?doc=${docId}`);
      setDocData(null);
    }
  };

  const canGoPrev = currentDocIndex > 0;
  const canGoNext = currentDocIndex < documents.length - 1 && currentDocIndex >= 0;

  // Get source URL for PDF/image viewing
  const sourceUrl = currentDocId ? getDocSourceUrl(currentDocId, claimId) : undefined;

  return (
    <>
      {/* Backdrop */}
      <div
        className={cn(
          "fixed inset-0 bg-black/30 z-40 transition-opacity duration-300",
          isOpen ? "opacity-100" : "opacity-0 pointer-events-none"
        )}
        onClick={onClose}
      />

      {/* Slide Panel */}
      <div
        className={cn(
          "fixed top-0 right-0 h-full w-full max-w-3xl bg-white dark:bg-slate-900 shadow-2xl z-50",
          "transform transition-transform duration-300 ease-out",
          "flex flex-col",
          isOpen ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={onClose}
              className="p-2 -ml-2 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
            >
              <X className="h-5 w-5" />
            </button>

            {currentDocSummary && (
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-slate-700 dark:text-slate-200 truncate">
                  {currentDocSummary.filename}
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  {formatDocType(currentDocSummary.doc_type)}
                  {currentDocSummary.page_count > 0 && ` · ${currentDocSummary.page_count} pages`}
                </p>
              </div>
            )}
          </div>

          {/* Document navigation */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => canGoPrev && goToDocument(documents[currentDocIndex - 1].doc_id)}
              disabled={!canGoPrev}
              className={cn(
                "p-2 rounded-lg transition-colors",
                canGoPrev
                  ? "hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  : "text-slate-300 dark:text-slate-600 cursor-not-allowed"
              )}
              title="Previous document"
            >
              <ChevronLeft className="h-5 w-5" />
            </button>
            <span className="text-xs text-slate-500 dark:text-slate-400 min-w-[60px] text-center">
              {currentDocIndex >= 0 ? `${currentDocIndex + 1} / ${documents.length}` : "—"}
            </span>
            <button
              onClick={() => canGoNext && goToDocument(documents[currentDocIndex + 1].doc_id)}
              disabled={!canGoNext}
              className={cn(
                "p-2 rounded-lg transition-colors",
                canGoNext
                  ? "hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200"
                  : "text-slate-300 dark:text-slate-600 cursor-not-allowed"
              )}
              title="Next document"
            >
              <ChevronRight className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Evidence highlight banner */}
        {evidence && (evidence.page || evidence.highlightText) && (
          <div className="px-4 py-2 bg-amber-50 dark:bg-amber-900/20 border-b border-amber-200 dark:border-amber-800">
            <div className="flex items-center gap-2 text-sm text-amber-700 dark:text-amber-300">
              <FileText className="h-4 w-4 flex-shrink-0" />
              <span>
                {evidence.page && `Page ${evidence.page}`}
                {evidence.highlightText && (
                  <span className="ml-2 text-amber-600 dark:text-amber-400">
                    "{evidence.highlightText.slice(0, 50)}
                    {evidence.highlightText.length > 50 ? "..." : ""}"
                  </span>
                )}
              </span>
            </div>
          </div>
        )}

        {/* Content */}
        <div className="flex-1 overflow-hidden">
          {loading && (
            <div className="flex items-center justify-center h-full">
              <div className="flex flex-col items-center gap-3">
                <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
                <p className="text-sm text-slate-500">Loading document...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-center justify-center h-full p-4">
              <div className="bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800 p-6 text-center max-w-md">
                <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              </div>
            </div>
          )}

          {!loading && !error && docData && (
            <DocumentViewer
              pages={docData.pages || []}
              sourceUrl={sourceUrl}
              hasPdf={docData.has_pdf}
              hasImage={docData.has_image}
              extraction={docData.extraction}
              highlightPage={evidence?.page ?? undefined}
              highlightCharStart={evidence?.charStart ?? undefined}
              highlightCharEnd={evidence?.charEnd ?? undefined}
              highlightQuote={evidence?.highlightText}
              claimId={claimId}
              docId={currentDocId}
            />
          )}

          {!loading && !error && !docData && !currentDocId && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <FileText className="h-12 w-12 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                <p className="text-sm text-slate-500 dark:text-slate-400">
                  Select a document or evidence to view
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function formatDocType(docType: string): string {
  return docType
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
