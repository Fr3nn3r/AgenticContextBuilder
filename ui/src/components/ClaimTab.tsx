import { useState, useEffect, useCallback } from "react";
import type { DocSummary, DocPayload } from "../types";
import type { DocRunInfo } from "../api/client";
import { listDocs, getDoc, getDocRuns, getDocSourceUrl } from "../api/client";
import { ClaimDocList } from "./ClaimDocList";
import { DocumentViewer } from "./DocumentViewer";
import { ExtractedFieldsPanel } from "./ExtractedFieldsPanel";

interface ClaimTabProps {
  claimId: string;
}

interface HighlightState {
  page?: number;
  charStart?: number;
  charEnd?: number;
  quote?: string;
  value?: string;
}

export function ClaimTab({ claimId }: ClaimTabProps) {
  // Document list state
  const [documents, setDocuments] = useState<DocSummary[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);

  // Selected document state
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [docPayload, setDocPayload] = useState<DocPayload | null>(null);
  const [docLoading, setDocLoading] = useState(false);

  // Run selection state
  const [runs, setRuns] = useState<DocRunInfo[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);

  // Highlight state for evidence
  const [highlight, setHighlight] = useState<HighlightState>({});

  // Reset all state when claimId changes (in case component is reused)
  useEffect(() => {
    setDocuments([]);
    setDocumentsLoading(true);
    setSelectedDocId(null);
    setDocPayload(null);
    setDocLoading(false);
    setRuns([]);
    setSelectedRunId(null);
    setHighlight({});
  }, [claimId]);

  // Load documents for the claim
  useEffect(() => {
    let cancelled = false;

    async function loadDocuments() {
      setDocumentsLoading(true);
      try {
        const docs = await listDocs(claimId);
        if (!cancelled) {
          setDocuments(docs);
          // Auto-select first document if available
          if (docs.length > 0) {
            setSelectedDocId(docs[0].doc_id);
          }
        }
      } catch (err) {
        console.error("Failed to load documents:", err);
      } finally {
        if (!cancelled) {
          setDocumentsLoading(false);
        }
      }
    }

    loadDocuments();

    return () => {
      cancelled = true;
    };
  }, [claimId]);

  // Load runs and document when selection changes
  useEffect(() => {
    if (!selectedDocId) {
      setRuns([]);
      setSelectedRunId(null);
      setDocPayload(null);
      return;
    }

    let cancelled = false;

    async function loadDocumentData() {
      setDocLoading(true);
      setHighlight({}); // Clear highlights when document changes

      try {
        // Load runs for the document
        const docRuns = await getDocRuns(selectedDocId!, claimId);
        if (cancelled) return;

        setRuns(docRuns);

        // Default to latest run (first in list)
        const latestRunId = docRuns.length > 0 ? docRuns[0].run_id : null;
        setSelectedRunId(latestRunId);

        // Load document with extraction from latest run
        const payload = await getDoc(selectedDocId!, claimId, latestRunId || undefined);
        if (cancelled) return;

        setDocPayload(payload);
      } catch (err) {
        console.error("Failed to load document:", err);
      } finally {
        if (!cancelled) {
          setDocLoading(false);
        }
      }
    }

    loadDocumentData();

    return () => {
      cancelled = true;
    };
  }, [selectedDocId, claimId]);

  // Handle run change
  const handleRunChange = useCallback(
    async (runId: string) => {
      if (!selectedDocId || runId === selectedRunId) return;

      setSelectedRunId(runId);
      setDocLoading(true);
      setHighlight({}); // Clear highlights when run changes

      try {
        const payload = await getDoc(selectedDocId, claimId, runId);
        setDocPayload(payload);
      } catch (err) {
        console.error("Failed to load document for run:", err);
      } finally {
        setDocLoading(false);
      }
    },
    [selectedDocId, claimId, selectedRunId]
  );

  // Handle document selection
  const handleSelectDoc = useCallback((docId: string) => {
    setSelectedDocId(docId);
  }, []);

  // Handle evidence click
  const handleEvidenceClick = useCallback(
    (page: number, charStart: number, charEnd: number, quote: string, value: string | null) => {
      setHighlight({
        page,
        charStart,
        charEnd,
        quote,
        value: value || undefined,
      });
    },
    []
  );

  // Get source URL for the selected document
  const sourceUrl = selectedDocId && claimId
    ? getDocSourceUrl(selectedDocId, claimId)
    : undefined;

  return (
    <div className="flex h-full">
      {/* Left panel: Document list */}
      <div className="w-52 flex-shrink-0 border-r border-border bg-card">
        {documentsLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-sm text-muted-foreground">Loading...</div>
          </div>
        ) : (
          <ClaimDocList
            documents={documents}
            selectedDocId={selectedDocId}
            onSelectDoc={handleSelectDoc}
          />
        )}
      </div>

      {/* Center panel: Document viewer */}
      <div className="flex-1 overflow-hidden">
        {docLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-sm text-muted-foreground">Loading document...</div>
          </div>
        ) : !docPayload ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-sm text-muted-foreground">
              Select a document to view
            </div>
          </div>
        ) : (
          <DocumentViewer
            pages={docPayload.pages}
            sourceUrl={sourceUrl}
            hasPdf={docPayload.has_pdf}
            hasImage={docPayload.has_image}
            extraction={docPayload.extraction}
            highlightQuote={highlight.quote}
            highlightPage={highlight.page}
            highlightCharStart={highlight.charStart}
            highlightCharEnd={highlight.charEnd}
            highlightValue={highlight.value}
            claimId={claimId}
            docId={selectedDocId || undefined}
          />
        )}
      </div>

      {/* Right panel: Extracted fields */}
      <div className="w-[350px] flex-shrink-0">
        <ExtractedFieldsPanel
          extraction={docPayload?.extraction || null}
          runs={runs}
          selectedRunId={selectedRunId}
          onRunChange={handleRunChange}
          onEvidenceClick={handleEvidenceClick}
          hasSelectedDoc={!!selectedDocId && !!docPayload}
        />
      </div>
    </div>
  );
}
