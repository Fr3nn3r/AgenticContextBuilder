import { useEffect, useState, useCallback } from "react";
import {
  listAllDocuments,
  getDoc,
  getDocSourceUrl,
} from "../api/client";
import type { DocumentListItem } from "../api/client";
import type { DocPayload } from "../types";
import { DocumentViewer } from "../components/DocumentViewer";
import { JsonTreeViewer } from "../components/JsonTreeViewer";
import { cn } from "../lib/utils";

interface Provenance {
  page?: number;
  char_start?: number;
  char_end?: number;
  text_quote?: string;
}

/**
 * Cost Estimates Review Page
 *
 * A temporary review screen to browse all cost estimate documents,
 * view PDFs, and inspect raw extraction output with click-to-highlight navigation.
 *
 * Layout: 3-panel (Doc List | Document Viewer | Extraction JSON Tree)
 */
export function CostEstimatesReviewPage() {
  // Document list state
  const [documents, setDocuments] = useState<DocumentListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selection state
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);

  // Document detail state
  const [docPayload, setDocPayload] = useState<DocPayload | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Highlight state for provenance
  const [highlightPage, setHighlightPage] = useState<number | undefined>();
  const [highlightCharStart, setHighlightCharStart] = useState<number | undefined>();
  const [highlightCharEnd, setHighlightCharEnd] = useState<number | undefined>();
  const [highlightQuote, setHighlightQuote] = useState<string | undefined>();

  // Load cost estimate documents
  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await listAllDocuments({
        doc_type: "cost_estimate",
        limit: 500,
      });

      setDocuments(response.documents);

      // Auto-select first document if available
      if (response.documents.length > 0 && !selectedDocId) {
        setSelectedDocId(response.documents[0].doc_id);
        setSelectedClaimId(response.documents[0].claim_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  // Load document detail when selection changes
  const loadDetail = useCallback(async () => {
    if (!selectedDocId || !selectedClaimId) {
      setDocPayload(null);
      return;
    }

    try {
      setDetailLoading(true);
      const payload = await getDoc(selectedDocId, selectedClaimId);
      setDocPayload(payload);

      // Clear highlights when switching documents
      setHighlightPage(undefined);
      setHighlightCharStart(undefined);
      setHighlightCharEnd(undefined);
      setHighlightQuote(undefined);
    } catch (err) {
      console.error("Failed to load document detail:", err);
      setDocPayload(null);
    } finally {
      setDetailLoading(false);
    }
  }, [selectedDocId, selectedClaimId]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  // Handle document selection
  const handleSelectDoc = (docId: string, docClaimId: string) => {
    if (docId !== selectedDocId) {
      setSelectedDocId(docId);
      setSelectedClaimId(docClaimId);
    }
  };

  // Handle field click from JSON tree - extract provenance and highlight
  const handleFieldClick = useCallback((provenance: Provenance) => {
    setHighlightPage(provenance.page);
    setHighlightCharStart(provenance.char_start);
    setHighlightCharEnd(provenance.char_end);
    setHighlightQuote(provenance.text_quote);
  }, []);

  // Build extraction data for JSON tree
  const extractionData = docPayload?.extraction || null;

  const selectedDoc = documents.find((d) => d.doc_id === selectedDocId);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="bg-card border-b px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h2 className="font-semibold text-foreground">Cost Estimates Review</h2>
          <span className="text-sm text-muted-foreground">
            {documents.length} documents
          </span>
        </div>
        <button
          onClick={loadDocuments}
          disabled={loading}
          className="px-3 py-1.5 text-sm border rounded-md bg-background text-foreground hover:bg-muted transition-colors disabled:opacity-50"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Main 3-panel layout */}
      <div className="flex-1 flex min-h-0">
        {/* Left: Document list (w-72) */}
        <div className="w-72 border-r overflow-auto bg-card flex-shrink-0">
          {loading ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              Loading...
            </div>
          ) : documents.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm p-4 text-center">
              No cost estimate documents found.
              <br />
              Run the pipeline on claims with cost estimates.
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
                    <QualityBadge status={doc.quality_status} />
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground truncate">
                      {doc.claim_id}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Center: Document viewer (flex-1) */}
        {selectedDoc && docPayload ? (
          <>
            <div className="flex-1 border-r bg-card min-w-0">
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
              />
            </div>

            {/* Right: Extraction JSON Tree (w-[420px]) */}
            <div className="w-[420px] flex-shrink-0 flex flex-col bg-muted/30">
              {/* Header */}
              <div className="px-4 py-2.5 border-b bg-card flex items-center justify-between">
                <h3 className="font-medium text-foreground">Extraction Output</h3>
                <span className="text-xs text-muted-foreground">
                  {extractionData?.fields?.length || 0} fields
                </span>
              </div>

              {/* JSON Tree */}
              <div className="flex-1 overflow-auto">
                {extractionData ? (
                  <JsonTreeViewer
                    data={extractionData}
                    onFieldClick={handleFieldClick}
                    defaultExpandDepth={2}
                    className="h-full"
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
                    No extraction data available
                  </div>
                )}
              </div>

              {/* Metadata footer */}
              {docPayload && (
                <div className="px-4 py-2 border-t bg-card text-xs text-muted-foreground">
                  <div className="flex items-center gap-4">
                    <span>Doc Type: {docPayload.doc_type}</span>
                    <span>Language: {docPayload.language || "N/A"}</span>
                  </div>
                </div>
              )}
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

// Quality status badge component
function QualityBadge({ status }: { status: string | null }) {
  if (!status) return null;
  const styles: Record<string, string> = {
    pass: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
    warn: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    fail: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  };
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs flex-shrink-0 ${styles[status] || ""}`}>
      {status}
    </span>
  );
}

export default CostEstimatesReviewPage;
