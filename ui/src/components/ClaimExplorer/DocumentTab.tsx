import { useState, useEffect } from "react";
import {
  ChevronDown,
  Loader2,
  Download,
  PanelRightClose,
  PanelRightOpen,
  FileText,
} from "lucide-react";
import { getDoc, getDocSourceUrl } from "../../api/client";
import { DocumentViewer } from "../DocumentViewer";
import type { DocSummary, DocPayload, ExtractedField } from "../../types";
import { cn } from "../../lib/utils";

interface DocumentTabProps {
  docSummary: DocSummary;
  claimId: string;
  initialHighlightPage?: number;
  initialHighlightCharStart?: number;
  initialHighlightCharEnd?: number;
}

interface EvidenceClickData {
  page: number;
  quote: string | null;
  charStart: number | null;
  charEnd: number | null;
  value: string | null;
}

// Clean field row - single line, consistent height
function FieldRow({
  field,
  onEvidenceClick,
}: {
  field: ExtractedField;
  onEvidenceClick?: (data: EvidenceClickData) => void;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const provenance = field.provenance?.[0];

  const formatFieldName = (name: string) => {
    return name
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  return (
    <div className="border-b border-border last:border-b-0">
      <div
        className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-muted/30 transition-colors"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* Field name - fixed width, no wrap */}
        <span className="text-sm font-medium text-foreground w-40 flex-shrink-0 truncate">
          {formatFieldName(field.name)}
        </span>
        {/* Value - fills remaining space, truncated */}
        <span className="text-sm text-muted-foreground font-mono flex-1 truncate min-w-0">
          {field.value || "—"}
        </span>
        {/* Chevron */}
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground flex-shrink-0 transition-transform",
            isExpanded && "rotate-180"
          )}
        />
      </div>

      {isExpanded && (
        <div className="px-4 pb-3 bg-muted/20 space-y-2">
          {/* Full value */}
          {field.value && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">Full Value</p>
              <code className="text-sm bg-background px-2 py-1 rounded border border-border font-mono block break-all">
                {field.value}
              </code>
            </div>
          )}

          {/* Source link */}
          {provenance && (
            <div>
              <p className="text-xs text-muted-foreground mb-1">Source</p>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onEvidenceClick?.({
                    page: provenance.page,
                    quote: provenance.text_quote || null,
                    charStart: provenance.char_start ?? null,
                    charEnd: provenance.char_end ?? null,
                    value: field.value,
                  });
                }}
                className="text-sm text-primary hover:underline"
              >
                Page {provenance.page}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function DocumentTab({
  docSummary,
  claimId,
  initialHighlightPage,
  initialHighlightCharStart,
  initialHighlightCharEnd,
}: DocumentTabProps) {
  const [docPayload, setDocPayload] = useState<DocPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPanelOpen, setIsPanelOpen] = useState(true);

  const [highlightPage, setHighlightPage] = useState<number | undefined>(initialHighlightPage);
  const [highlightQuote, setHighlightQuote] = useState<string | undefined>();
  const [highlightCharStart, setHighlightCharStart] = useState<number | undefined>(initialHighlightCharStart);
  const [highlightCharEnd, setHighlightCharEnd] = useState<number | undefined>(initialHighlightCharEnd);
  const [highlightValue, setHighlightValue] = useState<string | undefined>();

  const handleEvidenceClick = (data: EvidenceClickData) => {
    setHighlightPage(data.page);
    setHighlightQuote(data.quote ?? undefined);
    setHighlightCharStart(data.charStart ?? undefined);
    setHighlightCharEnd(data.charEnd ?? undefined);
    setHighlightValue(data.value ?? undefined);
  };

  useEffect(() => {
    loadDocument();
  }, [docSummary.doc_id, claimId]);

  const loadDocument = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDoc(docSummary.doc_id, claimId);
      setDocPayload(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load document");
    } finally {
      setLoading(false);
    }
  };

  const formatDocType = (docType: string) => {
    return docType
      .split("_")
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  };

  const fields = docPayload?.extraction?.fields || [];

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <p className="text-destructive mb-2">{error}</p>
          <button onClick={loadDocument} className="text-sm text-primary hover:underline">
            Try again
          </button>
        </div>
      </div>
    );
  }

  const sourceUrl = getDocSourceUrl(docSummary.doc_id, claimId);

  return (
    <div className="h-full flex">
      {/* Document Viewer */}
      <div className="flex-1 flex flex-col min-w-0 border-r border-border">
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-background">
          <div className="flex items-center gap-3 min-w-0">
            <FileText className="h-4 w-4 text-muted-foreground flex-shrink-0" />
            <div className="min-w-0">
              <h2 className="text-sm font-medium text-foreground truncate">
                {docPayload?.filename || docSummary.filename}
              </h2>
              <p className="text-xs text-muted-foreground">
                {formatDocType(docPayload?.doc_type || docSummary.doc_type)} · {docPayload?.pages?.length || docSummary.page_count} pages
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={sourceUrl}
              download
              className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
              title="Download"
            >
              <Download className="h-4 w-4" />
            </a>
            <button
              onClick={() => setIsPanelOpen(!isPanelOpen)}
              className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
              title={isPanelOpen ? "Hide fields" : "Show fields"}
            >
              {isPanelOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <div className="flex-1 min-h-0">
          {docPayload && (
            <DocumentViewer
              pages={docPayload.pages}
              sourceUrl={sourceUrl}
              hasPdf={docPayload.has_pdf}
              hasImage={docPayload.has_image}
              extraction={docPayload.extraction}
              claimId={claimId}
              docId={docSummary.doc_id}
              highlightPage={highlightPage}
              highlightQuote={highlightQuote}
              highlightCharStart={highlightCharStart}
              highlightCharEnd={highlightCharEnd}
              highlightValue={highlightValue}
            />
          )}
        </div>
      </div>

      {/* Extracted Fields Panel - Clean Design */}
      {isPanelOpen && (
        <div className="w-96 flex flex-col bg-background">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="text-sm font-semibold text-foreground">Extracted Fields</h3>
            <p className="text-xs text-muted-foreground">{fields.length} fields</p>
          </div>

          <div className="flex-1 overflow-y-auto">
            {fields.length > 0 ? (
              fields.map((field) => (
                <FieldRow
                  key={field.name}
                  field={field}
                  onEvidenceClick={handleEvidenceClick}
                />
              ))
            ) : (
              <div className="flex flex-col items-center justify-center h-full text-center p-4">
                <p className="text-sm text-muted-foreground">No fields extracted</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
